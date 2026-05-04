# GDELT Analysis Platform

> AI-driven event exploration, interactive dashboard visualization, and risk forecasting for GDELT 2.0 North America (2024).

## Overview

This platform provides a **dual-mode interface** for analyzing GDELT (Global Database of Events, Language, and Tone) data:

- **AI Explore** — Natural language querying powered by a hybrid planner (local Ollama router + rule-based fast path + remote LLM report generation).
- **Dashboard** — Fast, interactive data visualization with auto-generated insights, time-series charts, geographic heatmaps, and event timelines.
- **Forecast** — Transformer-Hawkes neural model for 7-day event risk prediction.

The system is built for **sub-200ms dashboard response times** using a precomputed `daily_summary` table, shared SQL layer, and optimized subquery patterns.

---

## Technology Stack

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.10+ | Runtime |
| FastAPI | ≥0.115 | API framework |
| Uvicorn | ≥0.32 | ASGI server |
| aiomysql | — | Async MySQL connection pool |
| Pydantic | ≥2.9 | Data validation |
| LangChain | ≥0.3 | LLM integration (OpenAI-compatible APIs) |
| OpenAI SDK | ≥1.55 | LLM API client (Kimi/OpenAI/Anthropic compatible) |
| ChromaDB | — | Vector database for semantic news search |
| Sentence-Transformers | — | Text embeddings (all-MiniLM-L6-v2) |
| NumPy / Pandas | — | Data processing |
| BeautifulSoup4 | — | Web scraping |
| Google Cloud BigQuery | ≥3.0 | GKG media analysis (optional) |

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.3 | UI framework |
| TypeScript | 5.6 | Type safety |
| Vite | 5.4 | Build tool & dev server |
| ECharts | 5.5 | Time-series & distribution charts |
| Leaflet | 1.9 | Interactive maps |
| Lucide React | 0.460 | Icon library |

### Local AI Routing
| Technology | Purpose |
|------------|---------|
| Ollama | Local LLM runtime for fast intent routing (qwen2.5:3b) |
| Qwen2.5 (3B) | Lightweight local model for query classification & entity extraction |

### Vector Search & RAG
| Technology | Purpose |
|------------|---------|
| ChromaDB | Persistent vector database for semantic news search |
| Sentence-Transformers | `all-MiniLM-L6-v2` embeddings for text similarity |

### Database & Infrastructure
| Technology | Purpose |
|------------|---------|
| MySQL 8.0+ | Primary data store with spatial extensions |
| Docker & Docker Compose | Container orchestration |
| GDELT 2.0 | Source event data (North America 2024) |

---

## Project Structure

```
DBMSproject/
│
├── backend/                         # FastAPI application
│   ├── main.py                      # App factory, lifespan, CORS, static files
│   ├── dependencies.py              # Dependency injection (DB pool)
│   ├── agents/
│   │   ├── planner.py               # Hybrid planner: Ollama router + rule engine + LLM report
│   │   └── enhanced_reporter.py     # Enhanced event report with storyline + news + GKG
│   ├── database/
│   │   ├── pool.py                  # Async MySQL connection pool
│   │   └── streaming.py             # Streaming query helpers
│   ├── queries/                     # Shared SQL layer (Single Source of Truth)
│   │   ├── core_queries.py          # All SQL query definitions
│   │   └── query_utils.py           # Sanitization & parsing helpers
│   ├── routers/
│   │   ├── data.py                  # Dashboard data endpoints (/api/v1/data/*)
│   │   └── analyze.py               # AI analysis endpoints (/api/v1/analyze)
│   ├── schemas/
│   │   └── responses.py             # Pydantic request/response models
│   └── services/
│       ├── data_service.py          # DB wrapper for dashboard & planner
│       ├── executor.py              # Query plan executor
│       ├── gkg_client.py            # Cost-controlled BigQuery client (GKG + Mentions)
│       ├── news_scraper.py          # Web scraping for event source articles
│       ├── storyline_builder.py     # Timeline + entity evolution builder
│       └── thp_service.py           # Transformer-Hawkes forecast model
│
├── frontend/                        # React + TypeScript + Vite
│   ├── src/
│   │   ├── App.tsx                  # Tabbed layout (Explore / Forecast / Dashboard)
│   │   ├── api/client.ts            # Typed HTTP client
│   │   ├── components/
│   │   │   ├── Dashboard.tsx        # Main dashboard orchestrator
│   │   │   ├── InsightCards.tsx     # Auto-generated insight cards
│   │   │   ├── StatsCards.tsx       # KPI cards with sparklines & trends
│   │   │   ├── TimeSeriesChart.tsx  # ECharts: events + conflict rate + tone
│   │   │   ├── MapPanel.tsx         # Leaflet map with conflict/cooperation legend
│   │   │   ├── DistributionCharts.tsx # Event type donut + geo bar charts
│   │   │   ├── HotEventsPanel.tsx   # Top 5 headlines by media coverage
│   │   │   ├── EventTimeline.tsx    # Chronological event list
│   │   │   ├── FilterBar.tsx        # Date / location / actor / type filters
│   │   │   ├── ExplorePanel.tsx     # AI natural language search UI
│   │   │   ├── EventReportPanel.tsx  # Enhanced event report with storyline + GKG
│   │   │   ├── EventStorylinePanel.tsx # Chronological event chain (BEFORE/SEED/AFTER/REACTION)
│   │   │   ├── ForecastWorkspace.tsx # THP forecast controls
│   │   │   └── ForecastChart.tsx    # Forecast visualization
│   │   └── types/index.ts           # TypeScript type definitions
│   ├── package.json
│   ├── vite.config.ts
│   └── index.html
│
├── mcp_server/                      # MCP server directory (legacy, currently unused)
│   └── app/                         # Empty placeholder for future MCP integration
│
├── db_scripts/                      # Database scripts
│   ├── gdelt_db_v1.sql              # Main events_table schema
│   ├── precompute_tables.sql        # daily_summary, event_fingerprints, etc.
│   ├── add_indexes.sql              # Basic indexes
│   ├── add_search_indexes.sql       # Search-optimized indexes
│   ├── add_spatial_indexes.sql      # Spatial (POINT) indexes
│   ├── all_indexes.sql              # Complete index script
│   ├── import_event.py              # CSV data importer
│   ├── etl_pipeline.py              # Event fingerprint ETL
│   ├── parallel_etl_pipeline.py     # Parallel ETL backfill
│   ├── build_knowledge_base.py      # ChromaDB vector index builder
│   ├── check_db_status.py           # DB health & stats checker
│   └── partition_events_table.sql   # Table partitioning script
│
├── data/                            # GDELT CSV chunks (gitignored)
├── chroma_db/                       # ChromaDB vector store
├── logs/                            # Runtime logs (gitignored)
├── models/                          # Trained THP model weights
│
├── run_backend.py                   # Backend launch script
├── start_kb.py                      # Knowledge base build daemon
├── backfill_fingerprints_parallel.py # Parallel fingerprint backfill
├── docker-compose.yml               # Docker Compose: MySQL + Backend + Frontend
├── Dockerfile                       # Python backend image
├── requirements.txt                 # Python dependencies
├── pyproject.toml                   # Project metadata
├── ARCHITECTURE.md                  # Detailed architecture docs
└── README.md                        # This file
```

---

## Quick Start (Docker Compose — Recommended)

The easiest way to run the entire stack is with Docker Compose, which spins up MySQL, the FastAPI backend, and the React frontend.

### Prerequisites
- Docker & Docker Compose
- At least 4GB RAM available for containers

### 1. Clone & Navigate

```bash
git clone <repository-url>
cd DBMSproject
```

### 2. Create Environment File

```bash
cp .env.env.backup .env
```

Edit `.env` and add your LLM API key:

```bash
# Database (used by Docker Compose internally)
DB_HOST=db
DB_PORT=3306
DB_USER=root
DB_PASSWORD=rootpassword
DB_NAME=gdelt

# LLM Provider (choose one)
LLM_PROVIDER=kimi
KIMI_CODE_API_KEY=sk-your-key-here
# or OPENAI_API_KEY=sk-...
# or ANTHROPIC_API_KEY=sk-...

# Optional: Custom base URL for OpenAI-compatible APIs
# LLM_BASE_URL=https://api.moonshot.cn/v1

# Optional: Ollama local router (for AI Explore intent routing)
# OLLAMA_URL=http://host.docker.internal:11434/api/generate

# Optional: GKG BigQuery (for enhanced reports)
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
# BIGQUERY_PROJECT_ID=your-gcp-project-id
```

### 3. Start All Services

```bash
docker-compose up -d
```

This starts three containers:

| Service | Container Name | URL | Description |
|---------|---------------|-----|-------------|
| MySQL | `gdelt_mysql` | `localhost:3307` | Database with auto-init schema |
| Backend | `gdelt_backend` | `http://localhost:8000` | FastAPI server |
| Frontend | `gdelt_frontend` | `http://localhost:5173` | React dev server |

Wait ~15 seconds for MySQL to initialize, then verify:

```bash
curl http://localhost:8000/health
```

### 4. Import GDELT Data (First Time)

Place your GDELT CSV files in `./data/`, then run the importer inside the backend container:

```bash
# Single-threaded import
docker exec -it gdelt_backend python db_scripts/import_event.py

# Or use the parallel ETL for large datasets
docker exec -it gdelt_backend python db_scripts/parallel_etl_pipeline.py
```

### 5. Add Database Indexes

```bash
docker exec -i gdelt_mysql mysql -u root -prootpassword gdelt < db_scripts/all_indexes.sql
```

### 6. Build Precomputed Tables (Optional but Recommended)

Precomputed tables dramatically speed up dashboard queries:

```bash
docker exec -it gdelt_backend python db_scripts/etl_pipeline.py
```

### 7. Stop Services

```bash
docker-compose down
```

To remove all data (including MySQL volume):

```bash
docker-compose down -v
```

---

## Manual Setup (Without Docker)

### Prerequisites
- Python 3.10+
- Node.js 20+
- MySQL 8.0+ with spatial extensions

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 3. Configure MySQL

Create the database and schema:

```bash
mysql -u root -p < db_scripts/gdelt_db_v1.sql
mysql -u root -p gdelt < db_scripts/precompute_tables.sql
mysql -u root -p gdelt < db_scripts/all_indexes.sql
```

### 4. Configure Environment

Create `.env` in the project root:

```bash
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=gdelt

LLM_PROVIDER=kimi
KIMI_CODE_API_KEY=sk-your-key-here
```

### 5. Import Data

```bash
python db_scripts/import_event.py
```

### 6. Start Backend

```bash
python run_backend.py --reload
```

Backend will be at `http://localhost:8000` with auto-reload enabled.

### 7. Start Frontend

```bash
cd frontend
npm run dev
```

Frontend will be at `http://localhost:5173`.

---

## Dashboard Features

| Feature | Description |
|---------|-------------|
| **Insight Cards** | Auto-generated key findings: peak activity day, most active actor, tension trends, media sentiment, geographic hotspots, dominant event type |
| **Stats Cards** | Six KPIs with mini sparklines: Total Events, Conflict Rate, Avg Tone, Unique Actors, Total Articles, Avg Goldstein |
| **Time Series Chart** | Daily event count + conflict rate + average tone (ECharts three-axis combo with zoom) |
| **Geographic Map** | Leaflet heatmap or event markers with color-coded legend (conflict / cooperation / protest / other) |
| **Distribution Charts** | Event type donut chart and top-location horizontal bar chart |
| **Hot Headlines** | Top 5 most-reported events with severity badges and metadata |
| **Event Timeline** | Chronological vertical timeline grouped by date (appears after search) |
| **Event Storyline** | Chronological event chain: BEFORE → SEED → AFTER + REACTIONS, with relevance scoring |
| **Event Detail** | Rich metadata: actors, location, Goldstein scale, tone, articles, AI-generated summary |
| **Smart Filters** | Date range, location autocomplete, actor autocomplete, event type, keyword search |

---

## API Endpoints

### Data Routes (`/api/v1/data/*`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard?start=&end=` | Dashboard metrics, top actors, event types, geo distribution |
| GET | `/timeseries?start=&end=&granularity=` | Event time series with conflict rate & tone |
| GET | `/geo?start=&end=&precision=` | Geo heatmap grid points |
| GET | `/events?query=&start=&end=&limit=` | Structured event search with filters |
| GET | `/geo/events?start=&end=&limit=` | Geo-located event points for maps |
| GET | `/top-events?start=&end=&limit=` | Top events by media coverage (NumArticles) |
| GET | `/insights?start=&end=` | Precomputed sentiment + hot headlines |
| GET | `/suggestions/actors?q=&limit=` | Actor autocomplete |
| GET | `/suggestions/locations?q=&limit=` | Location autocomplete |
| GET | `/forecast?start=&end=&region=&actor=&event_type=&forecast_days=` | Event risk forecast |
| GET | `/health` | Service health check |

### Analyze Routes (`/api/v1/analyze`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/analyze` | Natural language → planner + executor → structured data |
| POST | `/analyze/report` | Generate AI report from analysis results (delayed load) |
| POST | `/analyze/event-report` | Enhanced report: storyline + actor activity + GKG insights |
| POST | `/analyze/storyline` | Event storyline data (timeline + entities + themes) |

---

## AI Explore Architecture

The **AI Explore** tab uses a **hybrid routing pipeline** that balances speed, cost, and accuracy:

```
User Query
    │
    ▼
┌─────────────────┐
│  Ollama Router  │  ← Local qwen2.5:3b (fast, free, no API calls)
│  (Local LLM)    │     Extracts: location, dates, event_type, intent
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐  ┌─────────────┐
│ Rule   │  │  Remote LLM │  ← Kimi / OpenAI / Claude / Moonshot
│ Engine │  │  (Tools)    │     Complex reasoning, comparison, synthesis
└────┬───┘  └──────┬──────┘
     │             │
     └──────┬──────┘
            ▼
    ┌───────────────┐
    │  DataService  │  ← Direct DB queries via shared SQL layer
    │  (Direct DB)  │
    └───────┬───────┘
            ▼
    ┌───────────────┐
    │  JSON Results │  → Frontend charts, timeline, map
    └───────────────┘
```

### Routing Logic

1. **Ollama Local Router** (`OllamaRouter`) extracts structured context from natural language:
   - **Location** canonicalization (e.g., "NYC" → "New York")
   - **Date range** parsing (e.g., "last week", "Jan 2024", "Q1 2024")
   - **Event type** classification (protest / conflict / cooperation)
   - **Intent** routing (search / detail / brief / overview / hot / off_topic)

2. **Rule-Based Fast Path** handles simple lookups with explicit filters:
   - Direct dashboard, timeseries, geo, or event searches
   - No remote LLM calls → sub-second response

3. **Remote LLM Tool Execution** handles complex queries requiring reasoning:
   - Comparisons, synthesis, open-ended questions
   - Uses Kimi / OpenAI / Claude via LangChain `ChatOpenAI`

### Two-Stage Report Design

| Stage | Endpoint | What It Does | Latency |
|-------|----------|--------------|---------|
| 1 | `POST /analyze` | Planner + Executor only. Returns data + visualization plan. | ~1-3s |
| 2 | `POST /analyze/report` | Report Generator. Creates natural language summary. | ~2-5s |

Stage 2 is called **lazily** by the frontend after Stage 1 data is already rendered, keeping the UI responsive.

### Enhanced Event Report (`POST /analyze/event-report`)

A comprehensive single-call report that includes:
- **Executive summary** with key findings
- **Event Storyline** — chronological chain (preceding → seed → following + reactions)
- **Actor Activity Overview** — daily aggregated conflict/cooperation trends
- **GKG Insights** — media themes, co-occurring entities, tone timeline (BigQuery)
- **News Coverage** — scraped article content from SOURCEURL

**Report Configuration** (user-configurable via frontend):

| Option | Default | Description | Cost |
|--------|---------|-------------|------|
| `useGKG` | `true` | Enable GKG BigQuery queries | ~$0.005-0.01 |
| `useStoryline` | `true` | Enable event storyline | Free |
| `gkgToneDays` | `14` | Tone timeline window (3-14 days) | — |
| `gkgThemesDays` | `1` | Themes query days (1-7) | — |
| `storylineDaysBefore` | `7` | Storyline look-back (1-30 days) | — |
| `storylineDaysAfter` | `7` | Storyline look-forward (1-30 days) | — |
| `useGKGStorylineFilter` | `false` | GKG theme overlap for storyline precision | ~$0.09 |
| `useMentionsStorylineFilter` | `false` | Shared-article detection for storyline | ~$0.005 |

### Supported LLM Providers

| Provider | Environment Variable | Default Model |
|----------|----------------------|---------------|
| **Kimi** (Moonshot) | `KIMI_CODE_API_KEY` | `kimi-k2-0905-preview` |
| **Moonshot** | `MOONSHOT_API_KEY` | `kimi-k2-0905-preview` |
| **OpenAI** | `OPENAI_API_KEY` | `gpt-4o` |
| **Claude** (Anthropic) | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-20241022` |

All providers use the OpenAI-compatible API format via LangChain.

---

## Database Schema

### Main Table: `events_table`
Stores raw GDELT event records with 24+ fields including actors, locations, event codes, sentiment, and media volume.

Key columns:
- `SQLDATE` — Event date
- `Actor1Name`, `Actor2Name` — Primary and secondary actors
- `Actor1Type1Code`, `Actor2Type1Code` — Actor type codes (GOV, MIL, EDU, etc.)
- `EventCode`, `EventRootCode` — CAMEO event taxonomy
- `QuadClass` — Verbal/Material × Cooperation/Conflict
- `GoldsteinScale` — Conflict intensity (-10 to +10)
- `AvgTone` — Media sentiment
- `NumArticles`, `NumMentions`, `NumSources` — Media coverage metrics
- `ActionGeo_Lat`, `ActionGeo_Long` — Geographic coordinates

### Precomputed Tables
- `daily_summary` — Daily aggregated stats (events, conflicts, avg sentiment, top actors JSON)
- `event_fingerprints` — LLM-enriched events (headlines, summaries, severity scores)
- `region_daily_stats` — Per-region daily aggregation
- `geo_heatmap_grid` — Pre-aggregated 0.5° grid cells for fast map rendering

### Indexes
See `db_scripts/all_indexes.sql` for the complete index strategy. Key indexes:
- `idx_sqldate` — Date filtering
- `idx_numarticles` — Media coverage sorting
- `idx_date_actor` — Composite date + actor
- `idx_date_geo` — Composite date + geography
- `idx_event_root` — Event type filtering

---

## Performance Notes

| Metric | Target | How It's Achieved |
|--------|--------|-------------------|
| Dashboard load | < 200ms | Precomputed `daily_summary` table + parallel queries |
| Time series | < 200ms | DB-side aggregation with date indexes |
| Geo heatmap | < 300ms | Precomputed `geo_heatmap_grid` or ROUND() GROUP BY |
| AI Explore | < 5s | Planner → parallel tool execution → streaming response |
| Insights | Non-blocking | Fetched independently; never blocks main dashboard |

Heavy real-time GROUP BYs (QuadClass, ActorType) have been removed from the critical path. Distribution charts use pre-aggregated dashboard data instead.

---

## Useful Scripts

| Script | Purpose |
|--------|---------|
| `python run_backend.py --reload` | Start backend with auto-reload |
| `python db_scripts/import_event.py` | Import GDELT CSV files |
| `python db_scripts/etl_pipeline.py` | Build precomputed tables & fingerprints |
| `python db_scripts/parallel_etl_pipeline.py` | Parallel ETL for large datasets |
| `python db_scripts/build_knowledge_base.py` | Build ChromaDB vector index from event summaries |
| `python db_scripts/check_db_status.py` | Check DB health, table sizes, index usage |
| `python start_kb.py` | Knowledge base build daemon (watches for new data) |
| `cd frontend && npm run build` | Build frontend for production |

---

## Event Storyline Precision

The **Event Storyline** feature builds a chronological narrative chain around a seed event using a **three-layer precision system**:

```
SQL Layer (MySQL, Free) → GKG Layer (BigQuery, ~$0.09) → Mentions Layer (BigQuery, ~$0.005)
```

### Layer 1: SQL Precision (Always On)

`query_event_storyline()` in `backend/queries/core_queries.py` filters candidates using:
- **Same actor pair** (bidirectional: A→B or B→A)
- **Same location** (`ActionGeo_CountryCode` or `ActionGeo_FullName`)
- **Same QuadClass** (1-2=cooperation, 3-4=conflict)
- **Causal CAMEO chain** — seed's `EventRootCode` maps to plausible preceding codes (e.g., `19 (Use force)` ← `01,03,04,06,07`)

### Layer 2: GKG Theme Overlap (Optional)

`gkg_client.score_events_by_theme_overlap()` attaches a **Jaccard similarity score** (0-1) based on shared media themes from the GKG table. Events with higher theme overlap are ranked higher.

### Layer 3: Mentions Shared-Articles (Optional)

`gkg_client.get_shared_mention_articles()` queries the `eventmentions_partitioned` BigQuery table to find **exact article matches** between seed and candidates:

```sql
WITH seed_articles AS (
  SELECT MentionSourceName, MentionIdentifier
  FROM `gdelt-bq.gdeltv2.eventmentions_partitioned`
  WHERE GLOBALEVENTID = {seed_id}
)
SELECT c.GLOBALEVENTID, COUNT(*) as shared_articles
FROM ... c
JOIN seed_articles s ON c.MentionIdentifier = s.MentionIdentifier
WHERE c.GLOBALEVENTID IN ({candidate_ids})
GROUP BY c.GLOBALEVENTID
```

This is much more precise than shared-source (which only checks media outlet name).

### Composite Relevance Scoring

All candidates receive a **relevance_score** (0-100) computed as:

| Component | Weight | Description |
|-----------|--------|-------------|
| Temporal proximity | 0-30 | Days from seed (exponential decay) |
| Location match | 0-20 | Exact match = 20, partial = 12 |
| SQL match quality | 15-25 | Base 15 + NumArticles boost |
| GKG theme overlap | 0-15 | Jaccard × 15 |
| Shared articles | 0-10 | Log scale: 1 article = 5pts, 5+ = 10pts |

Events are **ranked by relevance_score** (not just date), so the most story-relevant events appear first.

### Frontend Display

Each event card shows:
- **Relevance score badge** (red ≥70, orange ≥40, gray <40)
- **Shared articles badge** (e.g., "3 articles")
- **Theme overlap badge** (e.g., "theme 80%")
- **Shared sources badge** (fallback if no exact article match)

---

## BigQuery GKG Integration

The platform optionally integrates with **GDELT BigQuery** for media analysis:

### Tables Used

| Table | Purpose | Cost |
|-------|---------|------|
| `gdelt-bq.gdeltv2.gkg_partitioned` | Media themes, entities, tone | ~$0.003/day (566MB) |
| `gdelt-bq.gdeltv2.eventmentions_partitioned` | Event-article mappings | ~$0.00008/query (16MB) |

### Cost Controls

`backend/services/gkg_client.py` enforces:
- **Mandatory `_PARTITIONTIME` filters** — queries without partition filter are rejected
- **Dry-run cost estimation** — every query is dry-run first; rejected if > limit
- **Per-query byte limit** — default 1GB max per query
- **Daily quota** — default 10GB/day per process
- **Result caching** — 1-hour TTL to avoid duplicate costs

### Environment Setup

```bash
# Service account JSON (recommended)
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export BIGQUERY_PROJECT_ID=your-gcp-project-id

# Optional limits
export BIGQUERY_DAILY_GB_LIMIT=10
export BIGQUERY_QUERY_TIMEOUT_SEC=30
```

---

## Semantic News Search (ChromaDB / RAG)

The platform includes a **Retrieval-Augmented Generation (RAG)** pipeline for semantic news search:

### How It Works

1. **Embedding Generation** — Event summaries and article snippets are embedded using `all-MiniLM-L6-v2` (384-dim vectors)
2. **Vector Storage** — Embeddings are stored in a persistent ChromaDB collection (`gdelt_news_collection`)
3. **Semantic Query** — Natural language queries are converted to embeddings and matched against the vector store
4. **Result Enrichment** — Retrieved events include metadata: event ID, date, source URL, and full content

### API

| Method | Endpoint | Description |
|--------|----------|-------------|
| (Internal) | `search_news_context(query, n_results=5)` | Semantic search via ChromaDB |

This is exposed through the **AI Explore** tab — when a user asks about news content, the planner routes to `news_context` which performs vector similarity search.

### Building the Knowledge Base

```bash
# One-time build
python db_scripts/build_knowledge_base.py

# Or run the daemon to continuously index new events
python start_kb.py
```

Prerequisites:
```bash
pip install chromadb sentence-transformers
```

The vector database is stored in `./chroma_db/` and persists across restarts.

---

## Troubleshooting

### Backend can't connect to MySQL
- Verify MySQL is running: `docker ps` or `mysqladmin ping`
- Check `.env` credentials match your MySQL setup
- If using Docker, ensure `DB_HOST=db` (service name), not `localhost`

### Frontend can't reach backend
- Backend CORS is configured for `localhost:5173` by default
- Verify backend is running: `curl http://localhost:8000/health`

### Dashboard queries are slow
- Ensure indexes are created: `mysql -u root -p gdelt < db_scripts/all_indexes.sql`
- Build precomputed tables: `python db_scripts/etl_pipeline.py`
- Check DB status: `python db_scripts/check_db_status.py`

### AI Explore returns errors
- Verify your LLM API key is set in `.env`
- Check that the provider API is accessible from your network

---

## License

Research project by Virginia Tech team: Xing Gao, Xiangxin Tang, Yuxin Miao, Ziliang Chen.

---

## References

- [GDELT Project](https://www.gdeltproject.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangChain](https://python.langchain.com/)
- [ECharts](https://echarts.apache.org/)
- [Leaflet](https://leafletjs.com/)
