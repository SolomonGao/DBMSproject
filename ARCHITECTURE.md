# GDELT Analysis Platform — Architecture

## Overview

This document describes the new architecture of the GDELT Analysis Platform, which evolved from a single-chatbox MCP client into a **Dashboard + AI Chat** dual-mode application.

## Design Principles

1. **Data Path ≠ Agent Path**: Dashboard data queries bypass LLM entirely; only complex natural-language analysis goes through the Agent.
2. **Reuse, Don't Rewrite**: Existing `mcp_server/`, `GDELTServiceOptimized`, and database layers are preserved and imported.
3. **LangChain is a Chat Intelligence Layer, Not a Global Middleware**.
4. **Prefer mature packages**: FastAPI, LangGraph, Vite, ECharts.

## Layer Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Layer                            │
│  ┌────────────────────────┐  ┌────────────────────────────┐ │
│  │   React Dashboard      │  │   Chat Panel / CLI         │ │
│  │   - ECharts charts     │  │   - Natural language       │ │
│  │   - Leaflet map        │  │   - Complex reasoning      │ │
│  │   - Stats cards        │  │   - Multi-tool planning    │ │
│  └───────────┬────────────┘  └─────────────┬──────────────┘ │
└──────────────┼─────────────────────────────┼───────────────┘
               │                             │
       ┌───────┴─────────────────────────────┴───────┐
       │          FastAPI API Gateway                 │
       │                                            │
       │   ┌─────────────────┐  ┌─────────────────┐  │
       │   │   Data Routes   │  │  Agent Routes   │  │
       │   │   /api/v1/data/*│  │  /api/v1/agent/*│  │
       │   │   < 200ms       │  │  1-5s           │  │
       │   └────────┬────────┘  └────────┬────────┘  │
       └────────────┼────────────────────┼───────────┘
                    │                    │
         ┌─────────┴────────┐  ┌────────┴──────────────┐
         │   Data Service   │  │   LangGraph Agent     │
         │   (Direct DB)    │  │   (ReAct pattern)     │
         │                  │  │                       │
         │  GDELTService    │  │  - Intent parsing     │
         │  Optimized       │  │  - Tool selection     │
         │                  │  │  - Parallel fetch     │
         │  ┌──────────┐    │  │  - Memory / State     │
         │  │ MySQL    │    │  │                       │
         │  │ ChromaDB │    │  │  ┌─────────────────┐  │
         │  └──────────┘    │  │  │  MCP Client     │  │
         └──────────────────┘  │  │  (stdio / sse)  │  │
                               │  └────────┬────────┘  │
                               └───────────┼───────────┘
                                           │
                               ┌───────────┴───────────┐
                               │     MCP Server        │
                               │    (FastMCP)          │
                               │  core_tools_v2.py     │
                               │                       │
                               │  ┌──────────────┐     │
                               │  │ MySQL Pool   │     │
                               │  │ ChromaDB     │     │
                               │  └──────────────┘     │
                               └───────────────────────┘
```

## Layer Descriptions

### 1. Frontend Layer (`frontend/`)

**React + Vite + TypeScript**

- **Dashboard** (`src/components/Dashboard.tsx`): Independent data panels (time series, map, stats cards). Fetches data directly from `/api/v1/data/*`.
- **Chat Panel** (`src/components/ChatPanel.tsx`): Conversational interface. Sends requests to `/api/v1/agent/chat`.
- **API Client** (`src/api/client.ts`): Typed HTTP client wrapping `fetch`.

### 2. FastAPI API Gateway (`backend/`)

**Single entry point for all HTTP requests.**

- **Data Routes** (`backend/routers/data.py`): Structured JSON endpoints for Dashboard.
- **Agent Routes** (`backend/routers/agent.py`): Conversational endpoints for Chat.
- **Lifespan Management**: Initializes DB pool on startup, closes on shutdown.
- **CORS**: Configured to allow local frontend development.

### 3. Data Service (`backend/services/data_service.py`)

**Direct database access for Dashboard queries.**

- Wraps `GDELTServiceOptimized` from `mcp_server/app/services/`.
- Returns **structured JSON** (Pydantic schemas), not markdown text.
- Independent database connection pool (does not share with MCP Server).

**Why bypass MCP for Dashboard?**
- MCP tools return **markdown text** optimized for LLM consumption.
- Dashboard needs **JSON arrays/objects** for chart libraries.
- Dashboard queries are deterministic; no reasoning required.

### 4. LangGraph Agent (`backend/agents/gdelt_agent.py`)

**Intelligent orchestration for Chat.**

- **Graph Structure**:
  - `understand` → Parse user intent
  - `plan` → Decide which data sources to fetch
  - `fetch` → Parallel tool execution (via MCP)
  - `synthesize` → LLM generates final response
- **State Management**: Explicit `AgentState` TypedDict.
- **Memory**: Conversation history maintained per session.
- **MCP Integration**: Tools are dynamically loaded from MCP Server via `MCPClient`.

### 5. MCP Server (`mcp_server/`)

**Preserved as-is.**

- `core_tools_v2.py`: Tool definitions using FastMCP.
- `app/services/gdelt_optimized.py`: Database queries, cache, streaming.
- `app/database/pool.py`: Async MySQL connection pool.
- Can be launched independently or via FastAPI lifespan (stdio mode).

## API Endpoints

### Data Routes (`/api/v1/data`)

| Method | Endpoint | Description | Cache |
|--------|----------|-------------|-------|
| GET | `/dashboard?start=&end=` | 5-dimension stats + trends | 5 min |
| GET | `/timeseries?start=&end=&granularity=` | Time series aggregation | 10 min |
| GET | `/geo?start=&end=&precision=` | Geo heatmap grid data | 5 min |
| GET | `/events?query=&limit=` | Event search (structured) | 2 min |
| GET | `/news?query=&n=` | RAG semantic search | 2 min |
| GET | `/health` | Service health check | none |

### Agent Routes (`/api/v1/agent`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Natural language chat with tools |
| GET | `/tools` | List available MCP tools |

## File Structure

```
DBMSproject/
├── backend/                    # FastAPI application
│   ├── main.py                 # Entry point, lifespan, CORS
│   ├── dependencies.py         # DB pool dependency injection
│   ├── schemas/
│   │   └── responses.py        # Pydantic request/response models
│   ├── routers/
│   │   ├── data.py             # Dashboard data endpoints
│   │   └── agent.py            # Chat agent endpoints
│   ├── services/
│   │   └── data_service.py     # Direct DB query wrapper
│   └── agents/
│       └── gdelt_agent.py      # LangGraph ReAct agent
│
├── frontend/                   # React Dashboard
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   └── client.ts
│       ├── components/
│       │   ├── Dashboard.tsx
│       │   ├── ChatPanel.tsx
│       │   ├── TimeSeriesChart.tsx
│       │   └── MapPanel.tsx
│       └── types/
│           └── index.ts
│
├── mcp_server/                 # Preserved MCP server
│   ├── main.py
│   └── app/
│       ├── tools/core_tools_v2.py
│       ├── services/gdelt_optimized.py
│       └── database/pool.py
│
├── mcp_app/                    # Preserved CLI client
│   ├── cli.py
│   ├── llm.py
│   └── client.py
│
├── run_backend.py              # Launch FastAPI server
├── requirements.txt            # Updated dependencies
├── pyproject.toml              # Updated dependencies
├── ARCHITECTURE.md             # This document
└── README.md                   # Updated usage guide
```

## Performance Targets

| Path | Target Latency | Notes |
|------|----------------|-------|
| `/api/v1/data/dashboard` | < 200ms | Parallel 5 queries + cache |
| `/api/v1/data/geo` | < 300ms | Grid aggregation + cache |
| `/api/v1/data/timeseries` | < 200ms | DB-side aggregation + cache |
| `/api/v1/agent/chat` | < 5s | Depends on tool count + LLM |

## Migration Notes

- Old `web_app/server.py` (http.server) is **deprecated** but kept for reference.
- Old `run_web.py` is replaced by `run_backend.py`.
- `mcp_app/cli.py` remains functional and can target the new FastAPI endpoints.
