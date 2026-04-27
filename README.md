# GDELT Analysis Platform v2.0

> **Dashboard + AI Chat** for GDELT 2.0 North American event analysis.

## What's New in v2.0

- **Dashboard**: Direct data visualization (time series, maps, stats) — no waiting for LLM
- **AI Analyst Chat**: LangGraph-powered ReAct agent with tool-calling and memory
- **FastAPI Backend**: Modern async API with auto-generated docs (`/docs`)
- **React Frontend**: Vite + TypeScript + ECharts + Leaflet
- **Dual-path architecture**: Data APIs bypass LLM entirely for <200ms response times

## Architecture

```
Frontend (React)  →  FastAPI  →  Data Service (DB)   ← Dashboard
                           ↓
                     LangGraph Agent  →  MCP Server  ← Chat
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for full design details.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env` and set your LLM API key:

```bash
# Required for Chat Agent
LLM_PROVIDER=kimi              # or moonshot, claude, openai
KIMI_CODE_API_KEY=sk-xxx       # or MOONSHOT_API_KEY, ANTHROPIC_API_KEY, etc.

# Database (same as before)
DB_HOST=db
DB_PORT=3306
DB_USER=root
DB_PASSWORD=rootpassword
DB_NAME=gdelt_db
```

### 3. Start the Backend

```bash
python run_backend.py
```

Server will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

### 4. Start the Frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

Frontend will be at http://localhost:5173 with proxy to backend.

## API Endpoints

### Data Routes (`/api/v1/data/*`) — Dashboard

| Endpoint | Description |
|----------|-------------|
| `GET /dashboard?start=&end=` | 5-dimension stats + trends |
| `GET /timeseries?start=&end=&granularity=` | Time series data |
| `GET /geo?start=&end=&precision=` | Geo heatmap grid |
| `GET /events?query=&limit=` | Event search |
| `GET /health` | DB + cache health |

### Agent Routes (`/api/v1/agent/*`) — Chat

| Endpoint | Description |
|----------|-------------|
| `POST /chat` | Natural language chat with tools |
| `GET /tools` | List available agent tools |

## Project Structure

```
DBMSproject/
├── backend/              # FastAPI application
│   ├── main.py           # Entry point
│   ├── routers/
│   │   ├── data.py       # Dashboard endpoints
│   │   └── agent.py      # Chat endpoints
│   ├── services/
│   │   └── data_service.py
│   ├── agents/
│   │   └── gdelt_agent.py   # LangGraph ReAct agent
│   └── schemas/
│       └── responses.py
│
├── frontend/             # React Dashboard
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── ChatPanel.tsx
│   │   │   ├── TimeSeriesChart.tsx
│   │   │   └── MapPanel.tsx
│   │   └── api/client.ts
│   └── package.json
│
├── mcp_server/           # Preserved MCP server
│   └── app/tools/core_tools_v2.py
│
├── run_backend.py        # Launch script
├── ARCHITECTURE.md       # Design docs
└── requirements.txt
```

## Legacy Components

- `mcp_server/` — MCP server unchanged; can run independently
- `frontend/` — React Dashboard + Chat UI (Vite + TypeScript)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Server | FastAPI + Uvicorn |
| Agent | LangGraph + LangChain OpenAI |
| Database | MySQL + aiomysql pool |
| Cache | Custom LRU+TTL |
| Frontend | React 18 + Vite + TypeScript |
| Charts | Apache ECharts |
| Maps | Leaflet + react-leaflet |
| Vector DB | ChromaDB + sentence-transformers |

## License

Virginia Tech DBMS Project
