"""
Build a local ChromaDB semantic index from representative GDELT events.

This script intentionally avoids crawling news websites. It turns the existing
MySQL event metadata into compact text documents that the chat agent can use
for RAG context.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import chromadb
import mysql.connector
from chromadb.utils import embedding_functions


COLLECTION_NAME = "gdelt_news_collection"

QUAD_CLASS_LABELS = {
    1: "verbal cooperation",
    2: "material cooperation",
    3: "verbal conflict",
    4: "material conflict",
}

EVENT_ROOT_LABELS = {
    "01": "make public statement",
    "02": "appeal",
    "03": "express intent to cooperate",
    "04": "consult",
    "05": "engage in diplomatic cooperation",
    "06": "engage in material cooperation",
    "07": "provide aid",
    "08": "yield",
    "09": "investigate",
    "10": "demand",
    "11": "disapprove",
    "12": "reject",
    "13": "threaten",
    "14": "protest",
    "15": "exhibit force posture",
    "16": "reduce relations",
    "17": "coerce",
    "18": "assault",
    "19": "fight",
    "20": "use unconventional mass violence",
}


def clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def url_keywords(source_url: str) -> str:
    if not source_url:
        return ""
    parsed = urlparse(source_url)
    raw = f"{parsed.netloc} {parsed.path}"
    raw = re.sub(r"\.[a-zA-Z0-9]{2,5}$", " ", raw)
    raw = re.sub(r"[^A-Za-z0-9]+", " ", raw)
    words = [w for w in raw.split() if len(w) > 2]
    return " ".join(words[:40])


def event_document(row: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    event_id = clean_text(row.get("GlobalEventID"))
    date = clean_text(row.get("SQLDATE"))
    actor1 = clean_text(row.get("Actor1Name"), "Actor not coded")
    actor2 = clean_text(row.get("Actor2Name"), "No second actor coded")
    location = clean_text(row.get("ActionGeo_FullName"), "Location not coded")
    country = clean_text(row.get("ActionGeo_CountryCode"))
    root = clean_text(row.get("EventRootCode"))
    event_type = EVENT_ROOT_LABELS.get(root.zfill(2), f"CAMEO root {root}" if root else "event")
    quad = QUAD_CLASS_LABELS.get(int(row.get("QuadClass") or 0), "event")
    goldstein = safe_float(row.get("GoldsteinScale"))
    tone = safe_float(row.get("AvgTone"))
    articles = int(row.get("NumArticles") or 0)
    sources = int(row.get("NumSources") or 0)
    source_url = clean_text(row.get("SOURCEURL"))
    keywords = url_keywords(source_url)

    doc = (
        f"Date: {date}. "
        f"Actors: {actor1} / {actor2}. "
        f"Location: {location}. "
        f"Country code: {country}. "
        f"Event category: {quad}; {event_type}; EventRootCode {root}. "
        f"Goldstein score: {goldstein:.2f}. Average tone: {tone:.2f}. "
        f"Coverage: {articles} articles from {sources} sources. "
        f"News URL keywords: {keywords}. "
        f"Source URL: {source_url}."
    )

    metadata = {
        "date": date,
        "source_url": source_url,
        "actor1": actor1,
        "actor2": actor2,
        "location": location,
        "country": country,
        "event_root_code": root,
        "event_type": event_type,
        "quad_class": int(row.get("QuadClass") or 0),
        "goldstein": goldstein,
        "avg_tone": tone,
        "num_articles": articles,
        "num_sources": sources,
    }
    return event_id, metadata, doc


def connect_mysql(args: argparse.Namespace):
    return mysql.connector.connect(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        database=args.db_name,
    )


def fetch_representative_events(args: argparse.Namespace) -> list[dict[str, Any]]:
    sql = """
        SELECT
            r.GlobalEventID,
            CAST(r.SQLDATE AS CHAR) AS SQLDATE,
            r.Actor1Name,
            r.Actor2Name,
            r.ActionGeo_FullName,
            r.ActionGeo_CountryCode,
            r.EventRootCode,
            e.QuadClass,
            r.GoldsteinScale,
            r.NumArticles,
            r.NumSources,
            r.AvgTone,
            r.SOURCEURL
        FROM representative_events_daily r
        LEFT JOIN events_table e ON e.GlobalEventID = r.GlobalEventID
        WHERE r.SQLDATE BETWEEN %s AND %s
        ORDER BY r.SQLDATE ASC, r.rank_num ASC
        LIMIT %s
    """
    with connect_mysql(args) as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql, (args.start_date, args.end_date, args.limit))
            return list(cursor.fetchall())


def build_index(args: argparse.Namespace) -> None:
    project_root = Path(__file__).resolve().parents[1]
    chroma_path = Path(args.chroma_path or os.getenv("CHROMA_DB_PATH") or project_root / "chroma_db")
    chroma_path.mkdir(parents=True, exist_ok=True)

    print(f"Loading representative events from MySQL {args.db_host}:{args.db_port}/{args.db_name}...")
    rows = fetch_representative_events(args)
    if not rows:
        raise RuntimeError("No representative events found. Run dashboard precompute first.")

    print(f"Building ChromaDB index at {chroma_path} with {len(rows):,} documents...")
    client = chromadb.PersistentClient(path=str(chroma_path))
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=args.embedding_model
    )

    if args.reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"Deleted existing collection: {COLLECTION_NAME}")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"description": "Representative GDELT event metadata for chat RAG"},
    )

    batch_ids: list[str] = []
    batch_docs: list[str] = []
    batch_meta: list[dict[str, Any]] = []

    for index, row in enumerate(rows, start=1):
        event_id, metadata, doc = event_document(row)
        batch_ids.append(f"gdelt_{event_id}")
        batch_docs.append(doc)
        batch_meta.append(metadata)

        if len(batch_ids) >= args.batch_size:
            collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_meta)
            print(f"Indexed {index:,}/{len(rows):,} documents")
            batch_ids.clear()
            batch_docs.clear()
            batch_meta.clear()

    if batch_ids:
        collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_meta)

    print(f"Done. Collection '{COLLECTION_NAME}' now has {collection.count():,} documents.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ChromaDB RAG index from GDELT MySQL data.")
    parser.add_argument("--db-host", default=os.getenv("DB_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.getenv("DB_PORT", "3307")))
    parser.add_argument("--db-user", default=os.getenv("DB_USER", "root"))
    parser.add_argument("--db-password", default=os.getenv("DB_PASSWORD", "rootpassword"))
    parser.add_argument("--db-name", default=os.getenv("DB_NAME", "gdelt"))
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--embedding-model", default="all-MiniLM-L6-v2")
    parser.add_argument("--chroma-path", default=None)
    parser.add_argument("--reset", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    build_index(parse_args())
