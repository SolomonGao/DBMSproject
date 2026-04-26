"""
Core Queries — Shared SQL layer for MCP tools and FastAPI DataService.

All data-fetching logic lives here. Callers (core_tools_v2, DataService) handle
formatting only (markdown for LLM, JSON for Dashboard).
"""

import asyncio
import calendar
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .query_utils import parse_time_hint, parse_region_input, sanitize_text

DEFAULT_TABLE = "events_table"

_CHROMA_CLIENT_CACHE: Dict[str, Any] = {}
_CHROMA_EMBEDDING_CACHE: Dict[str, Any] = {}
_CHROMA_COLLECTION_CACHE: Dict[str, Any] = {}

MONTH_NAME_TO_NUMBER = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

COUNTRY_CODE_ALIASES = {
    "united states": "US",
    "usa": "US",
    "u.s.": "US",
    "us": "US",
    "america": "US",
    "canada": "CA",
    "can": "CA",
    "ca": "CA",
    "mexico": "MX",
    "mex": "MX",
    "mx": "MX",
    "china": "CH",
    "chn": "CH",
    "russia": "RS",
    "rus": "RS",
    "ukraine": "UP",
    "ukr": "UP",
    "israel": "IS",
    "isr": "IS",
}

ACTOR_COUNTRY_CODE_ALIASES = {
    "united states": "USA",
    "usa": "USA",
    "u.s.": "USA",
    "us": "USA",
    "america": "USA",
    "canada": "CAN",
    "can": "CAN",
    "ca": "CAN",
    "mexico": "MEX",
    "mex": "MEX",
    "mx": "MEX",
    "china": "CHN",
    "chn": "CHN",
    "russia": "RUS",
    "rus": "RUS",
    "ukraine": "UKR",
    "ukr": "UKR",
    "israel": "ISR",
    "isr": "ISR",
    "palestine": "PSE",
    "palestinian": "PSE",
    "pse": "PSE",
    "united kingdom": "GBR",
    "uk": "GBR",
    "britain": "GBR",
    "gbr": "GBR",
}

ACTION_TO_ACTOR_COUNTRY_CODE = {
    "US": "USA",
    "CA": "CAN",
    "MX": "MEX",
    "CH": "CHN",
    "RS": "RUS",
    "UP": "UKR",
    "IS": "ISR",
}


def country_code_for(term: str) -> Optional[str]:
    return COUNTRY_CODE_ALIASES.get(sanitize_text(term).lower())


def actor_country_code_for(term: str) -> Optional[str]:
    cleaned = sanitize_text(term).lower()
    direct = ACTOR_COUNTRY_CODE_ALIASES.get(cleaned)
    if direct:
        return direct

    raw = sanitize_text(term).upper()
    if len(raw) == 3 and raw.isalpha():
        return raw

    geo_code = country_code_for(term)
    if geo_code:
        return ACTION_TO_ACTOR_COUNTRY_CODE.get(geo_code)

    return None


def actor_focus_terms(focus: Optional[str]) -> List[str]:
    cleaned = sanitize_text(focus or "").strip()
    if not cleaned:
        return []
    try:
        from backend.services.actor_normalization import actor_alias_terms
        terms = actor_alias_terms(cleaned)[:8]
    except Exception:
        terms = [cleaned.upper()]
    return [term for term in terms if term]


def actor_events_cte(
    start_date: str,
    end_date: str,
    actor_terms: List[str],
    event_type: Optional[str] = None,
) -> tuple[str, List[Any]]:
    placeholders = ",".join(["%s"] * len(actor_terms))
    type_condition = event_type_condition(event_type)
    filtered_where = f"WHERE {type_condition}" if type_condition else ""
    cte = f"""
    WITH actor_events AS (
        SELECT
            GlobalEventID, SQLDATE, Actor1Name, Actor2Name,
            ActionGeo_FullName, ActionGeo_CountryCode,
            ActionGeo_Lat, ActionGeo_Long, EventRootCode,
            GoldsteinScale, AvgTone, NumArticles, NumSources, SOURCEURL
        FROM {DEFAULT_TABLE} FORCE INDEX (idx_thp_actor1_training)
        WHERE SQLDATE BETWEEN %s AND %s
          AND Actor1Name IN ({placeholders})
        UNION
        SELECT
            GlobalEventID, SQLDATE, Actor1Name, Actor2Name,
            ActionGeo_FullName, ActionGeo_CountryCode,
            ActionGeo_Lat, ActionGeo_Long, EventRootCode,
            GoldsteinScale, AvgTone, NumArticles, NumSources, SOURCEURL
        FROM {DEFAULT_TABLE} FORCE INDEX (idx_thp_actor2_training)
        WHERE SQLDATE BETWEEN %s AND %s
          AND Actor2Name IN ({placeholders})
    ),
    filtered_events AS (
        SELECT * FROM actor_events
        {filtered_where}
    )
    """
    return cte, [start_date, end_date, *actor_terms, start_date, end_date, *actor_terms]


def country_codes_in_text(text: str) -> List[str]:
    lowered = sanitize_text(text or "").lower()
    codes = []
    for alias, code in COUNTRY_CODE_ALIASES.items():
        if alias and alias in lowered and code not in codes:
            codes.append(code)
    return codes


async def table_exists(pool, table_name: str) -> bool:
    row = await pool.fetchone(
        """
        SELECT COUNT(*) AS table_count
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
        """,
        (table_name,),
    )
    return bool(row and row.get("table_count"))


async def column_exists(pool, table_name: str, column_name: str) -> bool:
    row = await pool.fetchone(
        """
        SELECT COUNT(*) AS column_count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table_name, column_name),
    )
    return bool(row and row.get("column_count"))


def event_type_condition(event_type: Optional[str], alias: str = "") -> Optional[str]:
    prefix = f"{alias}." if alias else ""
    normalized = (event_type or "any").lower()
    if normalized == "conflict":
        return f"{prefix}GoldsteinScale < 0"
    if normalized == "cooperation":
        return f"{prefix}GoldsteinScale > 0"
    if normalized == "protest":
        return f"{prefix}EventRootCode = '14'"
    return None


def focus_filter_condition(
    focus: Optional[str],
    alias: str = "",
    focus_type: str = "location",
) -> tuple[Optional[str], List[Any]]:
    cleaned = sanitize_text(focus or "").strip()
    if not cleaned:
        return None, []

    prefix = f"{alias}." if alias else ""
    clauses: List[str] = []
    params: List[Any] = []
    country_code = country_code_for(cleaned)
    mode = (focus_type or "location").lower()

    if mode == "actor":
        actor_terms = actor_focus_terms(cleaned)
        if not actor_terms:
            return None, []
        placeholders = ",".join(["%s"] * len(actor_terms))
        return (
            f"({prefix}Actor1Name IN ({placeholders}) OR {prefix}Actor2Name IN ({placeholders}))",
            [*actor_terms, *actor_terms],
        )

    # Location mode: keep country names as geographic filters, not actors.
    if country_code:
        return f"{prefix}ActionGeo_CountryCode = %s", [country_code]

    parsed_terms = parse_region_input(cleaned) or [cleaned]
    for term_value in parsed_terms[:4]:
        term = f"%{term_value}%"
        clauses.append(f"{prefix}ActionGeo_FullName LIKE %s")
        params.append(term)
        if len(term_value) <= 3 and term_value.isalpha():
            clauses.append(f"{prefix}ActionGeo_CountryCode = %s")
            params.append(term_value.upper()[:3])

    return f"({' OR '.join(clauses)})", params


# ============================================================================
# Dashboard (parallel 5-query)
# ============================================================================

async def query_actor_dashboard(
    pool,
    start_date: str,
    end_date: str,
    actor_terms: List[str],
    event_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Dashboard aggregates for Actor mode, using Actor1/Actor2 indexes separately."""
    cte, cte_params = actor_events_cte(start_date, end_date, actor_terms, event_type)
    base_params = tuple(cte_params)
    queries = [
        ("daily_trend", f"""
            {cte}
            SELECT CAST(SQLDATE AS CHAR) as SQLDATE, COUNT(*) as cnt,
                   AVG(GoldsteinScale) as goldstein,
                   SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) as conflict
            FROM filtered_events
            GROUP BY SQLDATE ORDER BY SQLDATE
        """, base_params),

        ("top_actors", f"""
            {cte}
            SELECT actor, COUNT(*) as event_count
            FROM (
                SELECT Actor1Name as actor
                FROM filtered_events
                WHERE Actor1Name IS NOT NULL AND Actor1Name <> ''
                UNION ALL
                SELECT Actor2Name as actor
                FROM filtered_events
                WHERE Actor2Name IS NOT NULL AND Actor2Name <> ''
            ) actor_mentions
            GROUP BY actor ORDER BY event_count DESC LIMIT 10
        """, base_params),

        ("geo_distribution", f"""
            {cte}
            SELECT ActionGeo_CountryCode as country_code, COUNT(*) as event_count
            FROM filtered_events
            WHERE ActionGeo_CountryCode IS NOT NULL AND ActionGeo_CountryCode <> ''
            GROUP BY ActionGeo_CountryCode ORDER BY event_count DESC LIMIT 10
        """, base_params),

        ("event_types", f"""
            {cte}
            SELECT
                CASE
                    WHEN EventRootCode BETWEEN 1 AND 9 THEN 'Public Statement'
                    WHEN EventRootCode BETWEEN 10 AND 19 THEN 'Yield'
                    WHEN EventRootCode BETWEEN 20 AND 29 THEN 'Investigate'
                    WHEN EventRootCode BETWEEN 30 AND 39 THEN 'Demand'
                    WHEN EventRootCode BETWEEN 40 AND 49 THEN 'Disapprove'
                    WHEN EventRootCode BETWEEN 50 AND 59 THEN 'Reject'
                    WHEN EventRootCode BETWEEN 60 AND 69 THEN 'Threaten'
                    WHEN EventRootCode BETWEEN 70 AND 79 THEN 'Protest'
                    ELSE 'Other'
                END as event_type,
                COUNT(*) as event_count
            FROM filtered_events
            GROUP BY event_type ORDER BY event_count DESC
        """, base_params),

        ("summary_stats", f"""
            {cte}
            SELECT
                COUNT(*) as total_events,
                (
                    SELECT COUNT(DISTINCT actor)
                    FROM (
                        SELECT Actor1Name as actor
                        FROM filtered_events
                        WHERE Actor1Name IS NOT NULL AND Actor1Name <> ''
                        UNION
                        SELECT Actor2Name as actor
                        FROM filtered_events
                        WHERE Actor2Name IS NOT NULL AND Actor2Name <> ''
                    ) distinct_actors
                ) as unique_actors,
                AVG(GoldsteinScale) as avg_goldstein,
                AVG(AvgTone) as avg_tone,
                SUM(NumArticles) as total_articles
            FROM filtered_events
        """, base_params),
    ]

    async def _run_one(name: str, sql: str, params: tuple):
        import time
        t0 = time.time()
        rows = await pool.fetchall(sql, params)
        elapsed_ms = round((time.time() - t0) * 1000, 2)
        return name, {"data": rows, "count": len(rows), "elapsed_ms": elapsed_ms}

    results = await asyncio.gather(*[_run_one(n, s, p) for n, s, p in queries])
    return {name: data for name, data in results}


async def query_dashboard(
    pool,
    start_date: str,
    end_date: str,
    region_filter: Optional[str] = None,
    event_type: Optional[str] = None,
    focus_type: str = "location",
) -> Dict[str, Any]:
    """Return raw dashboard data: daily_trend, top_actors, geo_distribution, event_types, summary_stats."""
    actor_terms = actor_focus_terms(region_filter) if (focus_type or "").lower() == "actor" else []
    if actor_terms:
        return await query_actor_dashboard(pool, start_date, end_date, actor_terms, event_type)

    has_filters = bool((region_filter or "").strip()) or (event_type or "any").lower() not in {"any", "all", ""}
    has_total_articles = await column_exists(pool, "daily_summary", "total_articles") if not has_filters else False
    total_articles_expr = ", total_articles" if has_total_articles else ""
    # firsttryuseprecomputetabledaily_summary
    ds_rows = [] if has_filters else await pool.fetchall(
            "SELECT CAST(date AS CHAR) as date, total_events, conflict_events, "
            f"avg_goldstein, avg_tone, top_actors, top_locations, event_type_distribution{total_articles_expr} "
            "FROM daily_summary WHERE date BETWEEN %s AND %s ORDER BY date",
            (start_date, end_date)
        )
    if ds_rows and len(ds_rows) >= 10:
        import json
        daily_trend = []
        all_actors = {}
        all_countries = {}
        all_event_types = {}
        total_events = 0
        total_articles = 0
        goldstein_sum = 0
        tone_sum = 0
        unique_actors_set = set()
        for r in ds_rows:
            daily_trend.append({
                'SQLDATE': r['date'],
                'cnt': r['total_events'],
                'goldstein': r['avg_goldstein'],
                'conflict': r['conflict_events'],
            })
            total_events += r['total_events']
            if has_total_articles:
                total_articles += int(r.get('total_articles') or 0)
            goldstein_sum += (r['avg_goldstein'] or 0) * r['total_events']
            tone_sum += (r['avg_tone'] or 0) * r['total_events']
            # mergeactors
            for a in json.loads(r['top_actors'] or '[]'):
                all_actors[a['name']] = all_actors.get(a['name'], 0) + a['count']
                unique_actors_set.add(a['name'])
            # mergecountries
            for loc in json.loads(r['top_locations'] or '[]'):
                all_countries[loc['name']] = all_countries.get(loc['name'], 0) + loc['count']
            # mergeeventtypes
            for et, ec in json.loads(r['event_type_distribution'] or '{}').items():
                all_event_types[et] = all_event_types.get(et, 0) + ec
        top_actors = sorted([{'actor': k, 'event_count': v} for k, v in all_actors.items()], key=lambda x: x['event_count'], reverse=True)[:10]
        geo_distribution = sorted([{'country_code': k, 'event_count': v} for k, v in all_countries.items()], key=lambda x: x['event_count'], reverse=True)[:10]
        event_types = sorted([{'event_type': k, 'event_count': v} for k, v in all_event_types.items()], key=lambda x: x['event_count'], reverse=True)
        if not has_total_articles:
            articles_result = await pool.fetchone(
                f"SELECT SUM(NumArticles) as total_articles FROM {DEFAULT_TABLE} WHERE SQLDATE BETWEEN %s AND %s",
                (start_date, end_date)
            )
            total_articles = articles_result['total_articles'] if articles_result else None
        return {
            'daily_trend': {'data': daily_trend},
            'top_actors': {'data': top_actors},
            'geo_distribution': {'data': geo_distribution},
            'event_types': {'data': event_types},
            'summary_stats': {'data': [{
                'total_events': total_events,
                'unique_actors': len(unique_actors_set),
                'avg_goldstein': round(goldstein_sum / total_events, 2) if total_events else 0,
                'avg_tone': round(tone_sum / total_events, 2) if total_events else 0,
                'total_articles': total_articles,
            }]}
        }

    conditions = ["SQLDATE BETWEEN %s AND %s"]
    params: List[Any] = [start_date, end_date]
    focus_condition, focus_params = focus_filter_condition(region_filter, focus_type=focus_type)
    if focus_condition:
        conditions.append(focus_condition)
        params.extend(focus_params)
    type_condition = event_type_condition(event_type)
    if type_condition:
        conditions.append(type_condition)
    where_clause = " AND ".join(f"({condition})" for condition in conditions)
    base_params = tuple(params)

    # fallbackto originalparallelquery
    queries = [
        ("daily_trend", f"""
            SELECT CAST(SQLDATE AS CHAR) as SQLDATE, COUNT(*) as cnt,
                   AVG(GoldsteinScale) as goldstein,
                   SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) as conflict
            FROM {DEFAULT_TABLE}
            FORCE INDEX (idx_date_country)
            WHERE {where_clause}
            GROUP BY SQLDATE ORDER BY SQLDATE
        """, base_params),

        ("top_actors", f"""
            SELECT Actor1Name as actor, COUNT(*) as event_count
            FROM {DEFAULT_TABLE}
            WHERE {where_clause} AND Actor1Name IS NOT NULL AND Actor1Name <> ''
            GROUP BY Actor1Name ORDER BY event_count DESC LIMIT 10
        """, base_params),

        ("geo_distribution", f"""
            SELECT ActionGeo_CountryCode as country_code, COUNT(*) as event_count
            FROM {DEFAULT_TABLE}
            WHERE {where_clause}
              AND ActionGeo_CountryCode IS NOT NULL
            GROUP BY ActionGeo_CountryCode ORDER BY event_count DESC LIMIT 10
        """, base_params),

        ("event_types", f"""
            SELECT
                CASE
                    WHEN EventRootCode BETWEEN 1 AND 9 THEN 'Public Statement'
                    WHEN EventRootCode BETWEEN 10 AND 19 THEN 'Yield'
                    WHEN EventRootCode BETWEEN 20 AND 29 THEN 'Investigate'
                    WHEN EventRootCode BETWEEN 30 AND 39 THEN 'Demand'
                    WHEN EventRootCode BETWEEN 40 AND 49 THEN 'Disapprove'
                    WHEN EventRootCode BETWEEN 50 AND 59 THEN 'Reject'
                    WHEN EventRootCode BETWEEN 60 AND 69 THEN 'Threaten'
                    WHEN EventRootCode BETWEEN 70 AND 79 THEN 'Protest'
                    ELSE 'Other'
                END as event_type,
                COUNT(*) as event_count
            FROM {DEFAULT_TABLE}
            WHERE {where_clause}
            GROUP BY event_type ORDER BY event_count DESC
        """, base_params),

        ("summary_stats", f"""
            SELECT
                COUNT(*) as total_events,
                COUNT(DISTINCT Actor1Name) as unique_actors,
                AVG(GoldsteinScale) as avg_goldstein,
                AVG(AvgTone) as avg_tone,
                SUM(NumArticles) as total_articles
            FROM {DEFAULT_TABLE}
            WHERE {where_clause}
        """, base_params),
    ]

    async def _run_one(name: str, sql: str, params: tuple):
        import time
        t0 = time.time()
        rows = await pool.fetchall(sql, params)
        elapsed_ms = round((time.time() - t0) * 1000, 2)
        return name, {"data": rows, "count": len(rows), "elapsed_ms": elapsed_ms}

    results = await asyncio.gather(*[_run_one(n, s, p) for n, s, p in queries])
    return {name: data for name, data in results}


# ============================================================================
# Time Series
# ============================================================================

async def query_time_series(pool, start_date: str, end_date: str, granularity: str = "day") -> List[Dict[str, Any]]:
    # firsttryuseprecomputetabledaily_summary（ifETLalreadyran）
    ds_rows = await pool.fetchall(
        "SELECT CAST(date AS CHAR) as period, total_events as event_count, conflict_events, cooperation_events, "
        "avg_goldstein, avg_tone FROM daily_summary WHERE date BETWEEN %s AND %s ORDER BY date",
        (start_date, end_date)
    )
    if ds_rows and len(ds_rows) >= 20:
        result = []
        for r in ds_rows:
            total = r['event_count'] or 1
            result.append({
                'period': r['period'],
                'event_count': r['event_count'],
                'conflict_pct': round(r['conflict_events'] * 100.0 / total, 2) if r['conflict_events'] else 0,
                'cooperation_pct': round(r['cooperation_events'] * 100.0 / total, 2) if r['cooperation_events'] else 0,
                'avg_goldstein': r['avg_goldstein'],
                'std_goldstein': None,
                'avg_tone': r['avg_tone'],
                'std_tone': None,
                'top_actors_json': None,
            })
        return result

    # fallbackto originalSQL（forweek/monthorlackdaily_summary）
    if granularity == "week":
        period_expr = "STR_TO_DATE(CONCAT(YEARWEEK(SQLDATE), ' Sunday'), '%%X%%V %%W')"
    elif granularity == "month":
        period_expr = "DATE_FORMAT(SQLDATE, '%%Y-%%m-01')"
    else:
        period_expr = "SQLDATE"

    sql = f"""
    SELECT
        CAST({period_expr} AS CHAR) as period,
        COUNT(*) as event_count,
        ROUND(SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as conflict_pct,
        ROUND(SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as cooperation_pct,
        ROUND(AVG(GoldsteinScale), 2) as avg_goldstein,
        ROUND(STDDEV(GoldsteinScale), 2) as std_goldstein,
        ROUND(AVG(AvgTone), 2) as avg_tone,
        ROUND(STDDEV(AvgTone), 2) as std_tone,
        NULL as top_actors_json
    FROM {DEFAULT_TABLE}
    WHERE SQLDATE BETWEEN %s AND %s
    GROUP BY {period_expr}
    ORDER BY {period_expr}
    """
    return await pool.fetchall(sql, (start_date, end_date))


async def query_time_series(
    pool,
    start_date: str,
    end_date: str,
    granularity: str = "day",
    region_filter: Optional[str] = None,
    event_type: Optional[str] = None,
    focus_type: str = "location",
) -> List[Dict[str, Any]]:
    """Return time series data, optionally filtered by dashboard focus controls."""
    has_filters = bool((region_filter or "").strip()) or (event_type or "any").lower() not in {"any", "all", ""}
    if not has_filters:
        ds_rows = await pool.fetchall(
            "SELECT CAST(date AS CHAR) as period, total_events as event_count, conflict_events, cooperation_events, "
            "avg_goldstein, avg_tone FROM daily_summary WHERE date BETWEEN %s AND %s ORDER BY date",
            (start_date, end_date),
        )
        if ds_rows and len(ds_rows) >= 20:
            result = []
            for r in ds_rows:
                total = r["event_count"] or 1
                result.append({
                    "period": r["period"],
                    "event_count": r["event_count"],
                    "conflict_pct": round(r["conflict_events"] * 100.0 / total, 2) if r["conflict_events"] else 0,
                    "cooperation_pct": round(r["cooperation_events"] * 100.0 / total, 2) if r["cooperation_events"] else 0,
                    "avg_goldstein": r["avg_goldstein"],
                    "std_goldstein": None,
                    "avg_tone": r["avg_tone"],
                    "std_tone": None,
                    "top_actors_json": None,
                })
            return result

    if granularity == "week":
        period_expr = "STR_TO_DATE(CONCAT(YEARWEEK(SQLDATE), ' Sunday'), '%%X%%V %%W')"
    elif granularity == "month":
        period_expr = "DATE_FORMAT(SQLDATE, '%%Y-%%m-01')"
    else:
        period_expr = "SQLDATE"

    actor_terms = actor_focus_terms(region_filter) if (focus_type or "").lower() == "actor" else []
    if actor_terms:
        cte, cte_params = actor_events_cte(start_date, end_date, actor_terms, event_type)
        sql = f"""
        {cte}
        SELECT
            CAST({period_expr} AS CHAR) as period,
            COUNT(*) as event_count,
            ROUND(SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as conflict_pct,
            ROUND(SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as cooperation_pct,
            ROUND(AVG(GoldsteinScale), 2) as avg_goldstein,
            ROUND(STDDEV(GoldsteinScale), 2) as std_goldstein,
            ROUND(AVG(AvgTone), 2) as avg_tone,
            ROUND(STDDEV(AvgTone), 2) as std_tone,
            NULL as top_actors_json
        FROM filtered_events
        GROUP BY {period_expr}
        ORDER BY {period_expr}
        """
        return await pool.fetchall(sql, tuple(cte_params))

    conditions = ["SQLDATE BETWEEN %s AND %s"]
    params: List[Any] = [start_date, end_date]
    focus_condition, focus_params = focus_filter_condition(region_filter, focus_type=focus_type)
    if focus_condition:
        conditions.append(focus_condition)
        params.extend(focus_params)
    type_condition = event_type_condition(event_type)
    if type_condition:
        conditions.append(type_condition)
    where_clause = " AND ".join(f"({condition})" for condition in conditions)

    sql = f"""
    SELECT
        CAST({period_expr} AS CHAR) as period,
        COUNT(*) as event_count,
        ROUND(SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as conflict_pct,
        ROUND(SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as cooperation_pct,
        ROUND(AVG(GoldsteinScale), 2) as avg_goldstein,
        ROUND(STDDEV(GoldsteinScale), 2) as std_goldstein,
        ROUND(AVG(AvgTone), 2) as avg_tone,
        ROUND(STDDEV(AvgTone), 2) as std_tone,
        NULL as top_actors_json
    FROM {DEFAULT_TABLE}
    WHERE {where_clause}
    GROUP BY {period_expr}
    ORDER BY {period_expr}
    """
    return await pool.fetchall(sql, tuple(params))


async def query_event_sequence(
    pool,
    start_date: str,
    end_date: str,
    region: Optional[str] = None,
    actor: Optional[str] = None,
    event_type: str = "all",
) -> List[Dict[str, Any]]:
    """Return daily event sequence rows for THP-style forecasting."""
    event_type = (event_type or "all").lower()
    metric_column = {
        "all": "total_events",
        "conflict": "conflict_events",
        "cooperation": "cooperation_events",
        "protest": "protest_events",
    }.get(event_type, "total_events")

    async def fetch_precomputed_sequence(
        table_name: str,
        key_column: str,
        key_values: List[str],
    ) -> Optional[List[Dict[str, Any]]]:
        if not key_values or not await table_exists(pool, table_name):
            return None
        placeholders = ",".join(["%s"] * len(key_values))
        rows = await pool.fetchall(
            f"""
            SELECT
                CAST(event_date AS CHAR) as date,
                SUM({metric_column}) as event_count,
                SUM(conflict_events) as conflict_events,
                SUM(cooperation_events) as cooperation_events,
                AVG(avg_goldstein) as avg_goldstein,
                AVG(avg_tone) as avg_tone,
                SUM(total_articles) as total_articles
            FROM {table_name}
            WHERE event_date BETWEEN %s AND %s
              AND {key_column} IN ({placeholders})
            GROUP BY event_date
            ORDER BY event_date
            """,
            tuple([start_date, end_date, *key_values]),
        )
        return rows if rows else None

    def country_pair_key(value: str) -> Optional[str]:
        normalized = sanitize_text(value).strip()
        lowered = normalized.lower()
        for prefix in ("country_pair:", "countrypair:", "country pair:"):
            if lowered.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
                break
        lowered = normalized.lower()
        for prefix in ("actor_pair:", "actorpair:", "actor pair:"):
            if lowered.startswith(prefix):
                return None

        parts = pair_parts(normalized)
        if len(parts) != 2:
            return None
        left = actor_country_code_for(parts[0])
        right = actor_country_code_for(parts[1])
        if not left or not right or left == right:
            return None
        return "-".join(sorted((left, right)))

    def pair_parts(value: str) -> List[str]:
        normalized = sanitize_text(value).strip()
        if "-" in normalized and len(normalized) <= 15:
            return [part.strip() for part in normalized.split("-", 1)]
        lowered = normalized.lower()
        for separator in (" and ", " vs ", " versus ", "/", ","):
            if separator in lowered:
                index = lowered.find(separator)
                return [
                    normalized[:index].strip(),
                    normalized[index + len(separator):].strip(),
                ]
        return []

    def actor_pair_key(value: str) -> Optional[str]:
        normalized = sanitize_text(value).strip()
        lowered = normalized.lower()
        force_actor_pair = False
        for prefix in ("actor_pair:", "actorpair:", "actor pair:"):
            if lowered.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
                force_actor_pair = True
                break
        lowered = normalized.lower()
        for prefix in ("country_pair:", "countrypair:", "country pair:"):
            if lowered.startswith(prefix):
                return None

        parts = pair_parts(normalized)
        if len(parts) != 2:
            return None
        left_country = actor_country_code_for(parts[0])
        right_country = actor_country_code_for(parts[1])
        if left_country and right_country and not force_actor_pair:
            return None

        try:
            from backend.services.actor_normalization import normalize_actor_name
            left = normalize_actor_name(parts[0])
            right = normalize_actor_name(parts[1])
        except Exception:
            left = sanitize_text(parts[0]).upper()
            right = sanitize_text(parts[1]).upper()
        if not left or not right or left == right:
            return None
        return " :: ".join(sorted((left, right)))

    if actor and not region:
        try:
            from backend.services.actor_normalization import actor_alias_terms
            actor_terms = actor_alias_terms(actor)[:8]
        except Exception:
            actor_terms = [sanitize_text(actor).upper()]
        cached_rows = await fetch_precomputed_sequence(
            "thp_actor_daily_summary",
            "actor_name",
            actor_terms,
        )
        if cached_rows:
            return cached_rows

    if region and not actor:
        actor_pair = actor_pair_key(region)
        if actor_pair:
            cached_rows = await fetch_precomputed_sequence(
                "thp_actor_pair_daily_summary",
                "actor_pair",
                [actor_pair],
            )
            if cached_rows:
                return cached_rows

        pair_key = country_pair_key(region)
        if pair_key:
            cached_rows = await fetch_precomputed_sequence(
                "thp_country_pair_daily_summary",
                "country_pair",
                [pair_key],
            )
            if cached_rows:
                return cached_rows

        country_code = country_code_for(region)
        if country_code:
            cached_rows = await fetch_precomputed_sequence(
                "thp_country_daily_summary",
                "country",
                [country_code],
            )
            if cached_rows:
                return cached_rows

    conditions = ["SQLDATE BETWEEN %s AND %s"]
    params: List[Any] = [start_date, end_date]
    if event_type == "conflict":
        conditions.append("GoldsteinScale < 0")
    elif event_type == "cooperation":
        conditions.append("GoldsteinScale > 0")
    elif event_type == "protest":
        conditions.append("EventRootCode = '14'")

    if region:
        actor_pair = actor_pair_key(region)
        pair_key = country_pair_key(region)
        country_code = country_code_for(region)
        if actor_pair:
            left, right = actor_pair.split(" :: ", 1)
            try:
                from backend.services.actor_normalization import actor_alias_terms
                left_terms = actor_alias_terms(left)[:8] or [left]
                right_terms = actor_alias_terms(right)[:8] or [right]
            except Exception:
                left_terms = [left]
                right_terms = [right]
            left_placeholders = ",".join(["%s"] * len(left_terms))
            right_placeholders = ",".join(["%s"] * len(right_terms))
            conditions.append(
                f"("
                f"(UPPER(Actor1Name) IN ({left_placeholders}) AND UPPER(Actor2Name) IN ({right_placeholders})) "
                f"OR (UPPER(Actor1Name) IN ({right_placeholders}) AND UPPER(Actor2Name) IN ({left_placeholders}))"
                f")"
            )
            params.extend([*left_terms, *right_terms, *right_terms, *left_terms])
        elif pair_key:
            left, right = pair_key.split("-", 1)
            conditions.append(
                "LEAST(Actor1CountryCode, Actor2CountryCode) = %s "
                "AND GREATEST(Actor1CountryCode, Actor2CountryCode) = %s"
            )
            params.extend([left, right])
        elif country_code:
            conditions.append("ActionGeo_CountryCode = %s")
            params.append(country_code)
        else:
            term = f"%{sanitize_text(region)}%"
            conditions.append(
                "(Actor1Name LIKE %s OR Actor2Name LIKE %s OR ActionGeo_FullName LIKE %s)"
            )
            params.extend([term, term, term])

    if actor:
        term = f"%{sanitize_text(actor)}%"
        conditions.append("(Actor1Name LIKE %s OR Actor2Name LIKE %s)")
        params.extend([term, term])

    where_clause = " AND ".join(f"({condition})" for condition in conditions)
    rows = await pool.fetchall(
        f"""
        SELECT
            CAST(SQLDATE AS CHAR) as date,
            COUNT(*) as event_count,
            SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) as conflict_events,
            SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) as cooperation_events,
            AVG(GoldsteinScale) as avg_goldstein,
            AVG(AvgTone) as avg_tone,
            SUM(NumArticles) as total_articles
        FROM {DEFAULT_TABLE} FORCE INDEX (idx_date_metrics)
        WHERE {where_clause}
        GROUP BY SQLDATE
        ORDER BY SQLDATE
        """,
        tuple(params),
    )
    return rows


async def query_compare_entities(
    pool,
    start_date: str,
    end_date: str,
    left: str,
    right: str,
    event_type: str = "any",
) -> Dict[str, Any]:
    """Compare two actor/region terms over time for frontend compare mode."""

    def entity_condition(term: str) -> tuple[str, list]:
        cleaned = sanitize_text(term or "").strip()
        if not cleaned:
            cleaned = "Unknown"
        country_code = country_code_for(cleaned)
        if country_code:
            return (
                "ActionGeo_CountryCode = %s",
                [country_code],
            )
        parsed_terms = parse_region_input(cleaned) or [cleaned]
        clauses = []
        params = []
        for parsed in parsed_terms[:4]:
            like = f"%{parsed}%"
            clauses.extend([
                "Actor1Name LIKE %s",
                "Actor2Name LIKE %s",
                "ActionGeo_FullName LIKE %s",
            ])
            params.extend([like, like, like])
            if len(parsed) <= 3 and parsed.isalpha():
                clauses.append("ActionGeo_CountryCode = %s")
                params.append(parsed.upper()[:3])
        return f"({' OR '.join(clauses)})", params

    type_filter = ""
    if event_type == "conflict":
        type_filter = "AND GoldsteinScale < 0"
    elif event_type == "cooperation":
        type_filter = "AND GoldsteinScale > 0"
    elif event_type == "protest":
        type_filter = "AND EventRootCode = '14'"

    async def run_one(label: str):
        condition, params = entity_condition(label)
        sql = f"""
            SELECT
                CAST(SQLDATE AS CHAR) as period,
                COUNT(*) as event_count,
                ROUND(SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as conflict_pct,
                ROUND(SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as cooperation_pct,
                ROUND(AVG(GoldsteinScale), 2) as avg_goldstein
            FROM {DEFAULT_TABLE}
            WHERE SQLDATE BETWEEN %s AND %s
              AND {condition}
              {type_filter}
            GROUP BY SQLDATE
            ORDER BY SQLDATE
        """
        rows = await pool.fetchall(sql, tuple([start_date, end_date] + params))
        return {
            "label": label,
            "rows": rows,
            "total_events": sum(int(row.get("event_count") or 0) for row in rows),
            "avg_goldstein": round(
                sum(float(row.get("avg_goldstein") or 0) for row in rows) / max(1, len(rows)),
                2,
            ),
        }

    left_result, right_result = await asyncio.gather(run_one(left), run_one(right))
    return {
        "left": left_result,
        "right": right_result,
        "event_type": event_type,
        "start_date": start_date,
        "end_date": end_date,
    }


async def query_country_pair_trends(
    pool,
    start_date: str,
    end_date: str,
    country_a: str,
    country_b: str,
) -> Dict[str, Any]:
    """Return true bilateral country-pair trends using Actor country codes."""
    code_a = actor_country_code_for(country_a) or sanitize_text(country_a).upper()[:3]
    code_b = actor_country_code_for(country_b) or sanitize_text(country_b).upper()[:3]

    sql = f"""
        SELECT
            CAST(SQLDATE AS CHAR) as period,
            COUNT(*) as total_events,
            SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) as conflict_events,
            SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) as cooperation_events,
            SUM(CASE WHEN GoldsteinScale = 0 OR GoldsteinScale IS NULL THEN 1 ELSE 0 END) as neutral_events,
            ROUND(SUM(CASE WHEN GoldsteinScale < 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as conflict_pct,
            ROUND(SUM(CASE WHEN GoldsteinScale > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as cooperation_pct,
            ROUND(AVG(GoldsteinScale), 3) as avg_goldstein,
            ROUND(AVG(AvgTone), 3) as avg_tone,
            SUM(NumArticles) as total_articles
        FROM {DEFAULT_TABLE} FORCE INDEX (idx_thp_country_pair_training)
        WHERE SQLDATE BETWEEN %s AND %s
          AND (
            (Actor1CountryCode = %s AND Actor2CountryCode = %s)
            OR
            (Actor1CountryCode = %s AND Actor2CountryCode = %s)
          )
        GROUP BY SQLDATE
        ORDER BY SQLDATE
    """
    rows = await pool.fetchall(sql, (start_date, end_date, code_a, code_b, code_b, code_a))
    totals = {
        "total_events": sum(int(row.get("total_events") or 0) for row in rows),
        "conflict_events": sum(int(row.get("conflict_events") or 0) for row in rows),
        "cooperation_events": sum(int(row.get("cooperation_events") or 0) for row in rows),
        "neutral_events": sum(int(row.get("neutral_events") or 0) for row in rows),
        "total_articles": sum(int(row.get("total_articles") or 0) for row in rows),
    }
    total = max(1, totals["total_events"])
    summary = {
        **totals,
        "conflict_pct": round(totals["conflict_events"] * 100.0 / total, 2),
        "cooperation_pct": round(totals["cooperation_events"] * 100.0 / total, 2),
        "neutral_pct": round(totals["neutral_events"] * 100.0 / total, 2),
        "avg_goldstein": round(
            sum(float(row.get("avg_goldstein") or 0) * int(row.get("total_events") or 0) for row in rows) / total,
            3,
        ),
        "avg_tone": round(
            sum(float(row.get("avg_tone") or 0) * int(row.get("total_events") or 0) for row in rows) / total,
            3,
        ),
        "dominant_trend": "cooperation" if totals["cooperation_events"] >= totals["conflict_events"] else "conflict",
    }
    peak_conflict = max(rows, key=lambda row: float(row.get("conflict_pct") or 0), default=None)
    peak_cooperation = max(rows, key=lambda row: float(row.get("cooperation_pct") or 0), default=None)
    return {
        "country_a": country_a,
        "country_b": country_b,
        "code_a": code_a,
        "code_b": code_b,
        "start_date": start_date,
        "end_date": end_date,
        "source": "events_table Actor1CountryCode/Actor2CountryCode",
        "summary": summary,
        "daily": rows,
        "peak_conflict_day": peak_conflict,
        "peak_cooperation_day": peak_cooperation,
    }


# ============================================================================
# Geo Heatmap
# ============================================================================

async def query_geo_heatmap(
    pool,
    start_date: str,
    end_date: str,
    precision: int = 2,
    region_filter: Optional[str] = None,
    event_type: Optional[str] = None,
    focus_type: str = "location",
) -> List[Dict[str, Any]]:
    precision = max(1, min(4, int(precision)))
    has_filters = bool((region_filter or "").strip()) or (event_type or "any").lower() not in {"any", "all", ""}
    # firsttryuseprecomputetablegeo_heatmap_grid
    has_location_labels = await table_exists(pool, "geo_heatmap_location_labels") if not has_filters else False
    if has_filters:
        gh_rows = []
    elif has_location_labels:
        gh_rows = await pool.fetchall(
            f"""
            SELECT
                g.lat,
                g.lng,
                g.intensity,
                g.avg_conflict,
                COALESCE(l.sample_location, g.sample_location) as sample_location
            FROM (
                SELECT
                    ROUND(lat_grid, {precision}) as lat,
                    ROUND(lng_grid, {precision}) as lng,
                    SUM(event_count) as intensity,
                    AVG(avg_goldstein) as avg_conflict,
                    ANY_VALUE(NULLIF(sample_location, '')) as sample_location
                FROM geo_heatmap_grid
                WHERE date BETWEEN %s AND %s
                GROUP BY ROUND(lat_grid, {precision}), ROUND(lng_grid, {precision})
                HAVING intensity >= 5
                ORDER BY intensity DESC
                LIMIT 1000
            ) g
            LEFT JOIN geo_heatmap_location_labels l
              ON l.precision_level = %s
             AND l.lat_grid = g.lat
             AND l.lng_grid = g.lng
            ORDER BY g.intensity DESC
            """,
            (start_date, end_date, precision),
        )
    else:
        gh_rows = await pool.fetchall(
            f"SELECT ROUND(lat_grid, {precision}) as lat, ROUND(lng_grid, {precision}) as lng, "
            f"SUM(event_count) as intensity, AVG(avg_goldstein) as avg_conflict, "
            f"ANY_VALUE(NULLIF(sample_location, '')) as sample_location "
            f"FROM geo_heatmap_grid WHERE date BETWEEN %s AND %s "
            f"GROUP BY ROUND(lat_grid, {precision}), ROUND(lng_grid, {precision}) "
            f"HAVING intensity >= 5 ORDER BY intensity DESC LIMIT 1000",
            (start_date, end_date),
        )
    if gh_rows and len(gh_rows) >= 10:
        return gh_rows

    actor_terms = actor_focus_terms(region_filter) if (focus_type or "").lower() == "actor" else []
    if actor_terms:
        cte, cte_params = actor_events_cte(start_date, end_date, actor_terms, event_type)
        sql = f"""
        {cte}
        SELECT
            ROUND(ActionGeo_Lat, {precision}) as lat,
            ROUND(ActionGeo_Long, {precision}) as lng,
            COUNT(*) as intensity,
            AVG(GoldsteinScale) as avg_conflict,
            ANY_VALUE(ActionGeo_FullName) as sample_location
        FROM filtered_events
        WHERE ActionGeo_Lat IS NOT NULL
          AND ActionGeo_Long IS NOT NULL
        GROUP BY ROUND(ActionGeo_Lat, {precision}), ROUND(ActionGeo_Long, {precision})
        HAVING intensity >= 5
        ORDER BY intensity DESC
        LIMIT 1000
        """
        return await pool.fetchall(sql, tuple(cte_params))

    # fallbackto originalSQL
    conditions = [
        "SQLDATE BETWEEN %s AND %s",
        "ActionGeo_Lat IS NOT NULL",
        "ActionGeo_Long IS NOT NULL",
    ]
    params: List[Any] = [start_date, end_date]
    focus_condition, focus_params = focus_filter_condition(region_filter, focus_type=focus_type)
    if focus_condition:
        conditions.append(focus_condition)
        params.extend(focus_params)
    type_condition = event_type_condition(event_type)
    if type_condition:
        conditions.append(type_condition)
    where_clause = " AND ".join(f"({condition})" for condition in conditions)

    sql = f"""
    SELECT
        ROUND(ActionGeo_Lat, {precision}) as lat,
        ROUND(ActionGeo_Long, {precision}) as lng,
        COUNT(*) as intensity,
        AVG(GoldsteinScale) as avg_conflict,
        ANY_VALUE(ActionGeo_FullName) as sample_location
    FROM {DEFAULT_TABLE}
    WHERE {where_clause}
    GROUP BY ROUND(ActionGeo_Lat, {precision}), ROUND(ActionGeo_Long, {precision})
    HAVING intensity >= 5
    ORDER BY intensity DESC
    LIMIT 1000
    """
    return await pool.fetchall(sql, tuple(params))


# ============================================================================
# Event Search
# ============================================================================

async def query_search_events(
    pool,
    query_text: str,
    time_hint: Optional[str] = None,
    location_hint: Optional[str] = None,
    event_type: Optional[str] = None,
    max_results: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    precision: int = 2,
    focus_type: str = "location",
) -> List[Dict[str, Any]]:
    if start_date and end_date:
        date_start, date_end = start_date, end_date
    elif time_hint:
        date_start, date_end = parse_time_hint(time_hint)
    else:
        end = datetime.now().date()
        start = end - timedelta(days=30)
        date_start = start.strftime("%Y-%m-%d")
        date_end = end.strftime("%Y-%m-%d")

    has_fingerprints = await table_exists(pool, "event_fingerprints")
    inferred_country_codes = country_codes_in_text(query_text)
    location_country_code = country_code_for(location_hint or "") if location_hint else None
    has_coordinate_filter = lat is not None and lng is not None
    if has_coordinate_filter:
        index_hint = "FORCE INDEX (idx_date_geo_cover)"
    elif location_country_code or inferred_country_codes:
        index_hint = "FORCE INDEX (idx_date_country)"
    else:
        index_hint = "FORCE INDEX (idx_date_metrics)"
    if has_fingerprints:
        select_extra = "f.fingerprint, f.headline, f.summary, f.event_type_label, f.severity_score"
        join_clause = "LEFT JOIN event_fingerprints f ON e.GlobalEventID = f.global_event_id"
    else:
        select_extra = (
            "CONCAT('EVT-', CAST(e.SQLDATE AS CHAR), '-', CAST(e.GlobalEventID AS CHAR)) as fingerprint, "
            "NULL as headline, NULL as summary, NULL as event_type_label, NULL as severity_score"
        )
        join_clause = ""

    sql = f"""
    SELECT
        e.GlobalEventID, e.SQLDATE, e.Actor1Name, e.Actor2Name,
        e.EventCode, e.GoldsteinScale, e.AvgTone, e.NumArticles,
        e.ActionGeo_FullName, e.ActionGeo_CountryCode,
        e.ActionGeo_Lat, e.ActionGeo_Long,
        {select_extra}
    FROM {DEFAULT_TABLE} e {index_hint}
    {join_clause}
    WHERE e.SQLDATE BETWEEN %s AND %s
    """
    params = [date_start, date_end]

    if has_coordinate_filter:
        precision = max(1, min(4, int(precision or 2)))
        half_window = 0.5 * (10 ** -precision)
        coord_digits = max(8, precision + 4)
        sql += """
    AND e.ActionGeo_Lat BETWEEN %s AND %s
    AND e.ActionGeo_Long BETWEEN %s AND %s
    """
        params.extend([
            round(float(lat) - half_window, coord_digits),
            round(float(lat) + half_window, coord_digits),
            round(float(lng) - half_window, coord_digits),
            round(float(lng) + half_window, coord_digits),
        ])
        if query_text and query_text.strip().lower() not in ("events", "event", "gdelt"):
            cleaned_query = sanitize_text(query_text)
            if len(cleaned_query) <= 40:
                actor_terms = actor_focus_terms(cleaned_query) if (focus_type or "").lower() == "actor" else []
                if actor_terms:
                    placeholders = ",".join(["%s"] * len(actor_terms))
                    sql += f" AND (e.Actor1Name IN ({placeholders}) OR e.Actor2Name IN ({placeholders}))"
                    params.extend([*actor_terms, *actor_terms])
                else:
                    term = f"%{cleaned_query}%"
                    sql += " AND (e.Actor1Name LIKE %s OR e.Actor2Name LIKE %s OR e.ActionGeo_FullName LIKE %s)"
                    params.extend([term, term, term])
    elif location_hint:
        if location_country_code:
            sql += " AND e.ActionGeo_CountryCode = %s"
            params.append(location_country_code)
        else:
            sql += " AND (e.ActionGeo_FullName LIKE %s OR e.ActionGeo_CountryCode = %s)"
            params.extend([f"%{location_hint}%", location_hint.upper()[:3]])
    elif inferred_country_codes:
        sql += f" AND e.ActionGeo_CountryCode IN ({','.join(['%s'] * len(inferred_country_codes))})"
        params.extend(inferred_country_codes)
    elif query_text and query_text.strip().lower() not in ("events", "event", "gdelt"):
        cleaned_query = sanitize_text(query_text)
        if len(cleaned_query) <= 40:
            actor_terms = actor_focus_terms(cleaned_query) if (focus_type or "").lower() == "actor" else []
            if actor_terms:
                placeholders = ",".join(["%s"] * len(actor_terms))
                sql += f" AND (e.Actor1Name IN ({placeholders}) OR e.Actor2Name IN ({placeholders}))"
                params.extend([*actor_terms, *actor_terms])
            else:
                term = f"%{cleaned_query}%"
                sql += " AND (e.Actor1Name LIKE %s OR e.Actor2Name LIKE %s OR e.ActionGeo_FullName LIKE %s)"
                params.extend([term, term, term])

    if event_type and event_type != "any":
        type_conditions = {
            "conflict": "e.GoldsteinScale < -5",
            "cooperation": "e.GoldsteinScale > 5",
            "protest": "e.EventRootCode = '14'",
        }
        if event_type in type_conditions:
            sql += f" AND {type_conditions[event_type]}"

    if location_country_code or inferred_country_codes:
        sql += """
    ORDER BY e.SQLDATE DESC
    LIMIT %s
    """
    else:
        sql += """
    ORDER BY e.NumArticles * ABS(e.GoldsteinScale) DESC
    LIMIT %s
    """
    params.append(min(max_results, 50))

    return await pool.fetchall(sql, tuple(params))


# ============================================================================
# Event Detail
# ============================================================================

async def query_event_detail(pool, fingerprint: str) -> Optional[Dict[str, Any]]:
    """Return raw event detail data or None if not found."""
    if fingerprint.startswith('EVT-'):
        parts = fingerprint.split('-')
        if len(parts) >= 4:
            try:
                gid = int(parts[-1])
            except ValueError:
                return None
        else:
            return None

        row = await pool.fetchone(f"SELECT * FROM {DEFAULT_TABLE} WHERE GlobalEventID = %s", (gid,))
        if row:
            return dict(row)
        return None
    else:
        if not await table_exists(pool, "event_fingerprints"):
            return None
        row = await pool.fetchone("""
            SELECT global_event_id, fingerprint, headline, summary,
                   key_actors, event_type_label, severity_score,
                   location_name, location_country
            FROM event_fingerprints
            WHERE fingerprint = %s
        """, (fingerprint,))
        if not row:
            return None

        gid = int(row['global_event_id']) if row['global_event_id'] else None
        if not gid:
            return None

        event_row = await pool.fetchone(f"SELECT * FROM {DEFAULT_TABLE} WHERE GlobalEventID = %s", (gid,))
        return {
            "fingerprint": row['fingerprint'],
            "headline": row['headline'],
            "summary": row['summary'],
            "key_actors": row['key_actors'],
            "event_type_label": row['event_type_label'],
            "severity_score": row['severity_score'],
            "location_name": row['location_name'],
            "location_country": row['location_country'],
            "event_data": dict(event_row) if event_row else {},
        }


# ============================================================================
# Regional Overview
# ============================================================================

async def query_regional_overview(
    pool, region: str, time_range: str = "week"
) -> Dict[str, Any]:
    end_date = datetime.now().date()
    days_map = {'day': 1, 'week': 7, 'month': 30, 'quarter': 90, 'year': 365}
    start_date = end_date - timedelta(days=days_map.get(time_range, 7))

    # Try pre-computed stats first when the optional table exists.
    if await table_exists(pool, "region_daily_stats"):
        stats_rows = await pool.fetchall("""
            SELECT * FROM region_daily_stats
            WHERE region_code = %s AND date BETWEEN %s AND %s
            ORDER BY date DESC LIMIT 7
        """, (region.upper(), start_date, end_date))

        if stats_rows:
            return {"source": "precomputed", "rows": [dict(r) for r in stats_rows], "region": region, "start": str(start_date), "end": str(end_date)}

    # Fallback: real-time query
    row = await pool.fetchone(f"""
        SELECT
            COUNT(*) as total,
            AVG(GoldsteinScale) as avg_goldstein,
            AVG(AvgTone) as avg_tone,
            SUM(CASE WHEN GoldsteinScale < -5 THEN 1 ELSE 0 END) as conflicts,
            SUM(CASE WHEN GoldsteinScale > 5 THEN 1 ELSE 0 END) as cooperation
        FROM {DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN %s AND %s
          AND (ActionGeo_CountryCode = %s OR ActionGeo_FullName LIKE %s)
    """, (start_date, end_date, region.upper(), f'%{region}%'))

    hot_events = await pool.fetchall(f"""
        SELECT Actor1Name, Actor2Name, EventCode, GoldsteinScale,
               NumArticles, ActionGeo_FullName, SQLDATE
        FROM {DEFAULT_TABLE}
        WHERE SQLDATE BETWEEN %s AND %s
          AND (ActionGeo_CountryCode = %s OR ActionGeo_FullName LIKE %s)
        ORDER BY NumArticles * ABS(GoldsteinScale) DESC
        LIMIT 5
    """, (start_date, end_date, region.upper(), f'%{region}%'))

    return {
        "source": "realtime",
        "summary": dict(row) if row else {},
        "hot_events": [dict(r) for r in hot_events],
        "region": region,
        "start": str(start_date),
        "end": str(end_date),
    }


# ============================================================================
# Hot Events
# ============================================================================

async def query_hot_events(
    pool, query_date: Optional[str] = None, region_filter: Optional[str] = None, top_n: int = 5
) -> List[Dict[str, Any]]:
    query_date = query_date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    has_fingerprints = await table_exists(pool, "event_fingerprints")

    # Try pre-computed
    result = await pool.fetchone("""
        SELECT hot_event_fingerprints, top_actors, top_locations
        FROM daily_summary
        WHERE date = %s
    """, (query_date,))

    if has_fingerprints and result and result['hot_event_fingerprints']:
        import json
        hot_fingerprints = json.loads(result['hot_event_fingerprints']) if isinstance(result['hot_event_fingerprints'], str) else result['hot_event_fingerprints']
        events = []
        for fp in hot_fingerprints[:top_n]:
            row = await pool.fetchone("""
                SELECT f.fingerprint, f.headline, f.summary, f.severity_score,
                       f.location_name, e.SQLDATE, e.GoldsteinScale, e.NumArticles,
                       e.GlobalEventID, 'standard' as fp_type
                FROM event_fingerprints f
                JOIN events_table e ON f.global_event_id = e.GlobalEventID
                WHERE f.fingerprint = %s
            """, (fp,))
            if row:
                events.append(dict(row))
        return events

    # Fallback: real-time query
    region_condition = ""
    params = [query_date]
    if region_filter:
        region_condition = "AND (e.ActionGeo_CountryCode = %s OR e.ActionGeo_FullName LIKE %s)"
        params.extend([region_filter.upper(), f'%{region_filter}%'])

    sql = f"""
        SELECT
            COALESCE(f.fingerprint, CONCAT('EVT-', e.SQLDATE, '-', CAST(e.GlobalEventID AS CHAR))) as fingerprint,
            COALESCE(f.headline, CONCAT(COALESCE(NULLIF(e.Actor1Name, ''), '一方'), ' vs ', COALESCE(NULLIF(e.Actor2Name, ''), '另一方'))) as headline,
            COALESCE(f.summary, e.ActionGeo_FullName) as summary,
            COALESCE(f.severity_score, ABS(e.GoldsteinScale)) as severity_score,
            COALESCE(f.location_name, e.ActionGeo_FullName) as location_name,
            CAST(e.SQLDATE AS CHAR) as date,
            e.GoldsteinScale,
            e.NumArticles,
            e.GlobalEventID,
            CASE WHEN f.fingerprint IS NOT NULL THEN 'standard' ELSE 'temp' END as fp_type
        FROM {DEFAULT_TABLE} e
        LEFT JOIN event_fingerprints f ON e.GlobalEventID = f.global_event_id
        WHERE e.SQLDATE = %s {region_condition}
        ORDER BY e.NumArticles * ABS(e.GoldsteinScale) DESC
        LIMIT %s
    """
    params.append(top_n)
    return await pool.fetchall(sql, tuple(params))


async def query_hot_events(
    pool, query_date: Optional[str] = None, region_filter: Optional[str] = None, top_n: int = 5
) -> List[Dict[str, Any]]:
    """Return hot events without requiring optional fingerprint tables."""
    query_date = query_date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    region_condition = ""
    params = [query_date]
    if region_filter:
        code = country_code_for(region_filter)
        if code:
            region_condition = "AND e.ActionGeo_CountryCode = %s"
            params.append(code)
        else:
            region_condition = "AND (e.ActionGeo_CountryCode = %s OR e.ActionGeo_FullName LIKE %s)"
            params.extend([region_filter.upper()[:3], f'%{region_filter}%'])

    if await table_exists(pool, "event_fingerprints"):
        sql = f"""
            SELECT
                COALESCE(f.fingerprint, CONCAT('EVT-', e.SQLDATE, '-', CAST(e.GlobalEventID AS CHAR))) as fingerprint,
                COALESCE(f.headline, CONCAT(COALESCE(NULLIF(e.Actor1Name, ''), 'Unknown'), ' vs ', COALESCE(NULLIF(e.Actor2Name, ''), 'Unknown'))) as headline,
                COALESCE(f.summary, e.ActionGeo_FullName) as summary,
                COALESCE(f.severity_score, ABS(e.GoldsteinScale)) as severity_score,
                COALESCE(f.location_name, e.ActionGeo_FullName) as location_name,
                CAST(e.SQLDATE AS CHAR) as date,
                e.GoldsteinScale,
                e.NumArticles,
                e.GlobalEventID,
                CASE WHEN f.fingerprint IS NOT NULL THEN 'standard' ELSE 'temp' END as fp_type
            FROM {DEFAULT_TABLE} e
            LEFT JOIN event_fingerprints f ON e.GlobalEventID = f.global_event_id
            WHERE e.SQLDATE = %s {region_condition}
            ORDER BY e.NumArticles * ABS(e.GoldsteinScale) DESC
            LIMIT %s
        """
    else:
        sql = f"""
            SELECT
                CONCAT('EVT-', e.SQLDATE, '-', CAST(e.GlobalEventID AS CHAR)) as fingerprint,
                CONCAT(COALESCE(NULLIF(e.Actor1Name, ''), 'Unknown'), ' vs ', COALESCE(NULLIF(e.Actor2Name, ''), 'Unknown')) as headline,
                e.ActionGeo_FullName as summary,
                ABS(e.GoldsteinScale) as severity_score,
                e.ActionGeo_FullName as location_name,
                CAST(e.SQLDATE AS CHAR) as date,
                e.GoldsteinScale,
                e.NumArticles,
                e.GlobalEventID,
                'temp' as fp_type
            FROM {DEFAULT_TABLE} e FORCE INDEX (idx_date_metrics)
            WHERE e.SQLDATE = %s {region_condition}
            ORDER BY e.NumArticles * ABS(e.GoldsteinScale) DESC
            LIMIT %s
        """
    params.append(top_n)
    return await pool.fetchall(sql, tuple(params))


# ============================================================================
# Top Events
# ============================================================================

async def query_top_events(
    pool, start_date: str, end_date: str,
    region_filter: Optional[str] = None,
    event_type: Optional[str] = None,
    top_n: int = 10,
    focus_type: str = "location",
) -> List[Dict[str, Any]]:
    normalized_type = (event_type or "all").lower()
    if (
        not (region_filter or "").strip()
        and (focus_type or "location").lower() == "location"
        and normalized_type in {"", "any", "all"}
        and await table_exists(pool, "representative_events_daily")
    ):
        rows = await pool.fetchall(
            """
            SELECT
                GlobalEventID, CAST(SQLDATE AS CHAR) as SQLDATE, Actor1Name, Actor2Name,
                ActionGeo_FullName, ActionGeo_CountryCode,
                EventRootCode, GoldsteinScale, NumArticles,
                NumSources, AvgTone, SOURCEURL
            FROM representative_events_daily
            WHERE SQLDATE BETWEEN %s AND %s
              AND event_bucket = 'all'
            ORDER BY heat_score DESC, SQLDATE DESC, GlobalEventID DESC
            LIMIT %s
            """,
            (start_date, end_date, top_n),
        )
        if rows:
            return rows

    actor_terms = actor_focus_terms(region_filter) if (focus_type or "").lower() == "actor" else []
    if actor_terms:
        cte, cte_params = actor_events_cte(start_date, end_date, actor_terms, event_type)
        sql = f"""
            {cte}
            SELECT
                GlobalEventID, SQLDATE, Actor1Name, Actor2Name,
                ActionGeo_FullName, ActionGeo_CountryCode,
                EventRootCode, GoldsteinScale, NumArticles,
                NumSources, AvgTone, SOURCEURL
            FROM filtered_events
            ORDER BY NumArticles * ABS(GoldsteinScale) DESC
            LIMIT %s
        """
        return await pool.fetchall(sql, tuple([*cte_params, top_n]))

    conditions = ["SQLDATE BETWEEN %s AND %s"]
    params = [start_date, end_date]
    index_hint = "FORCE INDEX (idx_date_country)"

    focus_condition, focus_params = focus_filter_condition(region_filter, focus_type=focus_type)
    if focus_condition:
        conditions.append(focus_condition)
        params.extend(focus_params)

    type_condition = event_type_condition(event_type)
    if type_condition:
        conditions.append(type_condition)

    where_clause = " AND ".join(conditions)

    sql = f"""
        SELECT
            GlobalEventID, SQLDATE, Actor1Name, Actor2Name,
            ActionGeo_FullName, ActionGeo_CountryCode,
            EventRootCode, GoldsteinScale, NumArticles,
            NumSources, AvgTone, SOURCEURL
        FROM {DEFAULT_TABLE}
        {index_hint}
        WHERE {where_clause}
        ORDER BY NumArticles * ABS(GoldsteinScale) DESC
        LIMIT %s
    """
    params.append(top_n)
    return await pool.fetchall(sql, tuple(params))


# ============================================================================
# Daily Brief
# ============================================================================

async def query_daily_brief(pool, query_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    query_date = query_date or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    brief = await pool.fetchone("SELECT * FROM daily_summary WHERE date = %s", (query_date,))
    if brief:
        return dict(brief)

    row = await pool.fetchone(f"""
        SELECT
            COUNT(*) as total_events,
            SUM(CASE WHEN GoldsteinScale < -5 THEN 1 ELSE 0 END) as conflict_events,
            SUM(CASE WHEN GoldsteinScale > 5 THEN 1 ELSE 0 END) as cooperation_events,
            AVG(GoldsteinScale) as avg_goldstein,
            AVG(AvgTone) as avg_tone
        FROM {DEFAULT_TABLE}
        WHERE SQLDATE = %s
    """, (query_date,))

    return dict(row) if row else None


# ============================================================================
# Stream Events
# ============================================================================

async def query_stream_events(
    pool, actor_name: str,
    start_date: Optional[str] = None, end_date: Optional[str] = None,
    max_results: int = 100
):
    """Generator-friendly streaming query."""
    from ..database.streaming import StreamingQuery

    streaming = StreamingQuery(pool, chunk_size=50)
    date_filter = ""
    params = [f"%{actor_name}%", f"%{actor_name}%"]

    if start_date and end_date:
        date_filter = "AND SQLDATE BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    params.append(max_results)

    sql = f"""
        SELECT CAST(SQLDATE AS CHAR) as SQLDATE, Actor1Name, Actor2Name, EventCode,
               GoldsteinScale, AvgTone, ActionGeo_FullName,
               ActionGeo_Lat, ActionGeo_Long
        FROM {DEFAULT_TABLE}
        WHERE (Actor1Name LIKE %s OR Actor2Name LIKE %s)
        {date_filter}
        ORDER BY SQLDATE DESC
        LIMIT %s
    """

    async for row in streaming.stream(sql, tuple(params)):
        yield dict(row)


# ============================================================================# RAG / Vector Search (ChromaDB)
# ============================================================================

def get_chroma_db_path() -> str:
    """Get the ChromaDB persistent storage path."""
    configured_path = os.getenv("CHROMA_DB_PATH")
    if configured_path:
        return configured_path

    # Navigate from mcp_server/app/queries/ up to the project root.
    project_root = Path(__file__).resolve().parents[3]
    return str(project_root / 'chroma_db')


def get_chroma_collection():
    """Load and cache the ChromaDB collection for this backend process."""
    import chromadb
    from chromadb.utils import embedding_functions

    db_path = get_chroma_db_path()
    model_name = os.getenv("CHROMA_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    cache_key = f"{db_path}::{model_name}"

    if cache_key in _CHROMA_COLLECTION_CACHE:
        return _CHROMA_COLLECTION_CACHE[cache_key]

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Vector database not found at {db_path}")

    client = _CHROMA_CLIENT_CACHE.get(db_path)
    if client is None:
        client = chromadb.PersistentClient(path=db_path)
        _CHROMA_CLIENT_CACHE[db_path] = client

    embedding_function = _CHROMA_EMBEDDING_CACHE.get(model_name)
    if embedding_function is None:
        embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name
        )
        _CHROMA_EMBEDDING_CACHE[model_name] = embedding_function

    collection = client.get_collection(
        name="gdelt_news_collection",
        embedding_function=embedding_function
    )
    _CHROMA_COLLECTION_CACHE[cache_key] = collection
    return collection


def chroma_date_in_filter(start_date: str, end_date: str) -> Dict[str, Any]:
    """Build a ChromaDB string-date filter using $in because range ops require numbers."""
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    if start > end:
        start, end = end, start

    dates = []
    current = start
    while current <= end and len(dates) <= 366:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    if len(dates) == 1:
        return {"date": {"$eq": dates[0]}}
    return {"date": {"$in": dates}}


def infer_chroma_date_filter(query: str) -> Optional[Dict[str, Any]]:
    """Infer a ChromaDB metadata date filter from common natural-language hints."""
    text = query.lower()

    explicit_dates = re.findall(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if explicit_dates:
        normalized = [
            f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
            for year, month, day in explicit_dates
        ]
        start_date = min(normalized)
        end_date = max(normalized)
        return chroma_date_in_filter(start_date, end_date)

    year_month = re.search(r"\b(20\d{2})[-/](\d{1,2})\b", text)
    if year_month:
        year = int(year_month.group(1))
        month = int(year_month.group(2))
        last_day = calendar.monthrange(year, month)[1]
        return chroma_date_in_filter(
            f"{year:04d}-{month:02d}-01",
            f"{year:04d}-{month:02d}-{last_day:02d}",
        )

    month_name = re.search(
        r"\b("
        + "|".join(MONTH_NAME_TO_NUMBER.keys())
        + r")\s+(20\d{2})\b",
        text,
    )
    if month_name:
        month = MONTH_NAME_TO_NUMBER[month_name.group(1)]
        year = int(month_name.group(2))
        last_day = calendar.monthrange(year, month)[1]
        return chroma_date_in_filter(
            f"{year:04d}-{month:02d}-01",
            f"{year:04d}-{month:02d}-{last_day:02d}",
        )

    return None


async def query_search_news_context(
    query: str,
    n_results: int = 5
) -> Dict[str, Any]:
    """
    Search news article content via ChromaDB vector semantic search.
    
    Args:
        query: Natural language search query
        n_results: Number of results to return (default 5, max 10)
    
    Returns:
        Dict with 'results' list and 'query' metadata
    """
    try:
        db_path = get_chroma_db_path()
        if not os.path.exists(db_path):
            return {
                "error": "Vector database not found",
                "db_path": db_path,
                "message": "Please build the knowledge base first"
            }
        
        try:
            collection = get_chroma_collection()
        except ImportError:
            raise
        except Exception as exc:
            return {
                "error": "Collection not found",
                "message": f"News collection 'gdelt_news_collection' not found or unavailable. Please build the knowledge base first. Details: {exc}"
            }

        collection_count = collection.count()
        if collection_count == 0:
            return {
                "query": query,
                "results": [],
                "count": 0,
                "message": "ChromaDB collection exists but is empty. Build the index before using semantic search."
            }
        
        query_kwargs = {
            "query_texts": [query],
            "n_results": min(n_results, 10),
            "include": ["documents", "metadatas", "distances"],
        }
        date_filter = infer_chroma_date_filter(query)
        if date_filter:
            query_kwargs["where"] = date_filter

        results = collection.query(**query_kwargs)
        
        if not results['documents'] or not results['documents'][0]:
            return {
                "query": query,
                "results": [],
                "message": f"No related news found for '{query}'"
            }
        
        # Format results
        formatted_results = []
        for i in range(len(results['documents'][0])):
            metadata = results['metadatas'][0][i] or {}
            distance = None
            if results.get("distances") and results["distances"][0]:
                distance = results["distances"][0][i]
            formatted_results.append({
                "event_id": results['ids'][0][i],
                "date": metadata.get('date', 'Unknown'),
                "source_url": metadata.get('source_url', 'Unknown'),
                "actor1": metadata.get('actor1', ''),
                "actor2": metadata.get('actor2', ''),
                "location": metadata.get('location', ''),
                "event_type": metadata.get('event_type', ''),
                "goldstein": metadata.get('goldstein', ''),
                "distance": distance,
                "content": results['documents'][0][i],
            })
        
        return {
            "query": query,
            "results": formatted_results,
            "count": len(formatted_results)
        }
        
    except ImportError:
        return {
            "error": "Missing dependencies",
            "message": "ChromaDB not installed. Run: pip install chromadb sentence-transformers"
        }
    except Exception as e:
        return {
            "error": "Search failed",
            "message": str(e)
        }
