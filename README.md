# GDELT Analysis Platform

> AI-driven event exploration, dashboard visualization, and forecasting for GDELT 2.0 North America.

## What’s New

- **Tabbed React frontend** with `AI Explore`, `Forecast`, and `Dashboard` views
- **FastAPI backend** serving both fast data APIs and LLM-assisted analysis
- **Dual-path design**:
  - `/api/v1/data/*` for direct structured dashboard data
  - `/api/v1/analyze` for AI query planning + execution
- **Two-stage report generation**:
  - `POST /api/v1/analyze` returns plan + data quickly
  - `POST /api/v1/analyze/report` generates natural language report lazily
- **Forecast service** based on Transformer-Hawkes event risk estimation
- **Shared SQL layer** in `backend/queries/core_queries.py`

## Architecture

The current architecture separates fast analytics from AI-driven reasoning.

- `Dashboard` uses direct DB queries and structured JSON for charts.
- `AI Explore` uses an LLM-based planner and executor to map natural language to data queries.
- Report generation is deferred until after analysis, so UI remains responsive.

See [ARCHITECTURE.md](ARCHITECTURE.md) for full design details.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root and set database and optional LLM values:

```bash
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=rootpassword
DB_NAME=gdelt_db

LLM_PROVIDER=kimi
KIMI_CODE_API_KEY=sk-xxx
# or MOONSHOT_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY
```

### 3. Start Backend

```bash
python run_backend.py
```

Available endpoints:
- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

### 4. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at `http://localhost:5173`.

## API Endpoints

### Data Routes (`/api/v1/data/*`)

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/data/dashboard?start=&end=` | Dashboard metrics, top actors, and trends |
| `GET /api/v1/data/timeseries?start=&end=&granularity=` | Event time series aggregation |
| `GET /api/v1/data/geo?start=&end=&precision=` | Geo heatmap grid points |
| `GET /api/v1/data/events?query=&limit=` | Structured event search |
| `GET /api/v1/data/geo/events?start=&end=&limit=` | Event point data for maps |
| `GET /api/v1/data/suggestions/actors?q=&limit=` | Actor autocomplete suggestions |
| `GET /api/v1/data/suggestions/locations?q=&limit=` | Location autocomplete suggestions |
| `GET /api/v1/data/forecast?start=&end=&region=&actor=&event_type=&forecast_days=` | Event risk forecast |
| `GET /api/v1/data/health` | Service health status |

### Analyze Routes (`/api/v1/analyze`)

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/analyze` | Natural language analysis plan + query execution |
| `POST /api/v1/analyze/report` | Generate AI report from analysis results |

## Project Structure

```
DBMSproject/
├── backend/                    # FastAPI application
│   ├── main.py                 # App factory, lifespan, CORS
│   ├── dependencies.py         # DI helpers
│   ├── queries/                # Shared SQL/query layer
│   │   └── core_queries.py
│   ├── routers/                # API endpoint definitions
│   │   ├── analyze.py
│   │   └── data.py
│   ├── schemas/                # Pydantic models
│   │   └── responses.py
│   ├── services/               # Business logic and DB wrappers
│   │   ├── data_service.py
│   │   ├── executor.py
│   │   └── thp_service.py
│   └── agents/                 # Planner + report generator
│       └── planner.py
│
├── frontend/                   # React frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── App.tsx
│       ├── api/client.ts
│       ├── components/
│       │   ├── ExplorePanel.tsx
│       │   ├── Dashboard.tsx
│       │   ├── ForecastWorkspace.tsx
│       │   └── ReportPanel.tsx
│       └── types/index.ts
│
├── mcp_server/                 # Optional legacy MCP tool server
│   └── app/
│       ├── queries/core_queries.py
│       └── tools/core_tools_v2.py
├── run_backend.py              # Launch FastAPI server
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Project metadata
├── ARCHITECTURE.md             # Architecture documentation
└── README.md                   # This file
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, aiomysql |
| Query Layer | MySQL, shared SQL layer in `backend/queries/core_queries.py` |
| AI Planner | LLM-based planner + report generator |
| Forecast | Transformer-Hawkes forecasting service |
| Frontend | React 18, Vite, TypeScript |
| Visualization | ECharts, Leaflet |

## Notes

- `AI Explore` is the primary natural language discovery experience.
- `Dashboard` is built for fast chart rendering with structured JSON.
- `Forecast` provides risk estimation from historical event sequences.
- `mcp_server/` is preserved for optional use but is not required for the core FastAPI backend.
