# GDELT Analysis Platform

Interactive dashboard, forecast workspace, and AI analyst chat for the GDELT 2.0 North American event dataset.

This branch combines direct FastAPI data APIs, a React dashboard, a Transformer Hawkes Process forecast service, and a LangGraph chat agent with MySQL, THP, and ChromaDB tools.

## Current Features

- **Dashboard**: Date-range overview, total events, unique actors, total articles, average Goldstein score, daily event trends, conflict rate, geographic hotspot map, top actors, representative events, event drawer, and Markdown report export.
- **Location / Actor filtering**: Dashboard and Forecast support explicit `Location` and `Actor` modes instead of treating every text input the same way.
- **Forecast workspace**: Forecast-start input, 7-day risk outlook, low / median / high prediction intervals, scenario comparison, and model evaluation metadata.
- **THP forecasting**: Neural Transformer Hawkes Process service for event intensity forecasting across global, country, actor, country-pair, actor-pair, event-root, and event-code series.
- **AI analyst chat**: LangGraph ReAct agent with tool calling for event search, dashboard summaries, time-series analysis, country-pair comparison, THP forecasting, and ChromaDB RAG context.
- **ChromaDB RAG**: Local semantic index over representative GDELT events for background, cause, and context-style questions.
- **Performance optimizations**: Summary tables, representative-event precompute, geo labels, spatial index support, and backend TTL caching.

## Architecture

```text
React + Vite frontend
        |
        v
FastAPI backend
        |
        +-- MySQL / GDELT structured event queries
        +-- THP forecast service and model checkpoint
        +-- ChromaDB semantic context search
        +-- LangGraph ReAct chat agent
```

The system separates responsibilities:

- **MySQL** stores structured GDELT event data and powers exact counts, filters, maps, time series, and dashboard metrics.
- **THP** predicts future event intensity and returns forecast intervals.
- **ChromaDB** retrieves semantically relevant event context for chat explanations.
- **LLM / LangGraph** decides which tools to call and writes the final analyst-style answer.

## Repository Contents

```text
backend/
  agents/gdelt_agent.py          # LangGraph chat agent
  routers/data.py                # Dashboard, forecast, event, compare APIs
  routers/agent.py               # Chat APIs
  services/data_service.py       # Service layer and cache
  services/thp_service.py        # THP forecast service
  services/thp_neural.py         # Neural THP model definition

frontend/
  src/components/Dashboard.tsx
  src/components/ForecastWorkspace.tsx
  src/components/ForecastPanel.tsx
  src/components/ChatPanel.tsx
  src/components/MapPanel.tsx
  src/components/ReportExport.tsx

mcp_server/
  app/queries/core_queries.py    # Shared SQL and ChromaDB query logic

db_scripts/
  import_event.py                # CSV import into MySQL
  dashboard_fast_precompute.sql  # Dashboard acceleration tables
  build_chromadb_index.py        # Build local ChromaDB RAG index
  train_thp_model.py             # Train THP checkpoint
```

## What Is Not Uploaded

The repository intentionally does **not** include local secrets or large generated assets:

- `.env` and API keys
- `data/` raw GDELT CSV files
- `models/` THP checkpoints, training arrays, and training logs
- `chroma_db/` local vector database
- local database files or dumps

These are ignored by `.gitignore` and must be created locally.

## Quick Start With Docker

### 1. Clone and checkout this branch

```bash
git clone https://github.com/SolomonGao/DBMSproject.git
cd DBMSproject
git checkout codex/chat-thp-chromadb-dashboard
```

### 2. Create `.env`

Create a local `.env` file in the project root. Do not commit it.

```bash
LLM_PROVIDER=kimi
KIMI_CODE_API_KEY=your_api_key_here

DB_HOST=db
DB_PORT=3306
DB_USER=root
DB_PASSWORD=rootpassword
DB_NAME=gdelt

THP_CHECKPOINT_PATH=models/thp_gdelt.pt
CHROMA_DB_PATH=/app/chroma_db
```

You can also use another OpenAI-compatible provider by setting `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, and the matching API key environment variable.

### 3. Start services

```bash
docker compose up -d --build
```

Open:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- MySQL host port: `localhost:3307`

## Loading Data

Place GDELT CSV files under `data/` with names like:

```text
data/gdelt_2024_na_000000000000.csv
data/gdelt_2024_na_000000000001.csv
```

Then import them into Docker MySQL:

```bash
docker exec gdelt_backend python db_scripts/import_event.py
```

After import, build the acceleration tables:

```bash
Get-Content db_scripts/dashboard_fast_precompute.sql | docker exec -i gdelt_mysql mysql -uroot -prootpassword gdelt
```

These tables make dashboard loading, representative events, and map labels much faster.

## Training THP Forecast Model

The model checkpoint is local and ignored by Git. To train one from the imported MySQL data:

```bash
docker exec gdelt_backend python db_scripts/train_thp_model.py --epochs 80
```

For GPU training, use a local or Docker environment with CUDA-enabled PyTorch, then run:

```bash
python db_scripts/train_thp_model.py --epochs 80 --device cuda --amp --compile
```

The default output is:

```text
models/thp_gdelt.pt
```

The backend loads this file through `THP_CHECKPOINT_PATH`.

## Building ChromaDB RAG Index

ChromaDB is also local and ignored by Git. After importing data and building representative events, create the semantic index:

```bash
python db_scripts/build_chromadb_index.py --reset --limit 10000 --batch-size 256
```

This creates:

```text
chroma_db/
```

The chat agent uses this index for questions about causes, background, context, and narrative explanations.

## Useful API Endpoints

### Data APIs

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/data/dashboard` | Dashboard summary, top actors, representative events |
| `GET /api/v1/data/timeseries` | Daily, weekly, or monthly event trends |
| `GET /api/v1/data/geo` | Geographic event hotspots |
| `GET /api/v1/data/events` | Search events by query, date, location, actor, or map coordinate |
| `GET /api/v1/data/top-events` | High-impact events for reports and event drawer |
| `GET /api/v1/data/compare` | Compare two countries, actors, or keywords |
| `GET /api/v1/data/country-pair` | True bilateral country-pair cooperation/conflict trends |
| `GET /api/v1/data/forecast` | THP forecast with intervals and model metadata |
| `GET /api/v1/data/health` | Backend, database, and cache health |

### Agent APIs

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/agent/chat` | Natural-language analyst chat |
| `GET /api/v1/agent/tools` | List available chat tools |
| `GET /api/v1/agent/helps` | Tool usage tips |

## Example Questions

```text
Compare cooperation versus conflict trends between the United States and Canada in 2024.
Forecast United States and Canada conflict after 2024-02-01.
Why were Canada police conflict events prominent in January 2024?
Show Canada conflict from January 15 2024 to January 20 2024.
Compare United States and Canada for all events in January 2024.
```

## Development Commands

Frontend build:

```bash
docker exec gdelt_frontend npm run build
```

Backend syntax check:

```bash
docker exec gdelt_backend python -m py_compile backend/agents/gdelt_agent.py backend/services/data_service.py mcp_server/app/queries/core_queries.py
```

Restart services:

```bash
docker compose restart backend frontend
```

Check logs:

```bash
docker logs gdelt_backend --tail 100
docker logs gdelt_frontend --tail 100
```

## Notes

- Dashboard is designed for fast structured analytics and does not call the LLM.
- Forecast uses the THP service; without a local checkpoint, it falls back to baseline behavior where available.
- Chat combines LLM reasoning with real tools. It can use MySQL for facts, THP for forecasts, and ChromaDB for semantic context.
- ChromaDB results are semantic context, not exact aggregate counts. Use MySQL-backed tools for exact statistics.

## License

Virginia Tech DBMS Project.
