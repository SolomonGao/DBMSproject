# GDELT Analysis Platform

Interactive dashboard, THP forecast workspace, and AI analyst chat for the GDELT 2.0 North American event dataset.

This branch is prepared so another user can run the Forecast page without retraining the THP model. The final lightweight checkpoint is included at `models/thp_gdelt.pt`; local database data still needs to be imported into Docker MySQL.

## Features

- **Dashboard**: event totals, actors, articles, Goldstein score, time series, conflict rate, geographic hotspots, representative events, and Markdown report export.
- **Forecast**: Transformer Hawkes Process forecast, 7-day projected event counts, low / median / high intervals, risk labels, metadata, and backtest metrics.
- **Compare Mode**: compare locations or actors over a selected date range.
- **Analyst Chat**: LangGraph tool-calling agent for data questions, event search, dashboard summaries, country-pair analysis, and THP forecasts.
- **ChromaDB RAG**: optional local semantic index for richer chat context.

## Included vs. Local-Only Files

Included in Git:

- Source code for backend, frontend, MCP queries, and database scripts
- Docker configuration
- `.env.example`
- Final THP forecast checkpoint: `models/thp_gdelt.pt`

Not included in Git:

- `.env` and API keys
- Raw GDELT CSV files under `data/`
- Docker MySQL volume data
- ChromaDB vector database under `chroma_db/`
- THP training caches, sweep outputs, logs, and backup checkpoints

## Quick Start

### 1. Clone and checkout the branch

```bash
git clone https://github.com/SolomonGao/DBMSproject.git
cd DBMSproject
git checkout codex/forecast-ready-thp-model
```

### 2. Create `.env`

```bash
cp .env.example .env
```

Forecast and Dashboard do not require an LLM API key. Analyst Chat requires setting a valid key in `.env`.

### 3. Start Docker services

```bash
docker compose up -d --build
```

Open:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- MySQL host port: `localhost:3307`

The default Docker setup does not require a GPU. Forecast inference runs on CPU with the included THP checkpoint.

## Load Data For Forecast

The THP model is included, but Forecast still needs historical event summaries from MySQL. Put the 2024 North America GDELT CSV files in `data/`, for example:

```text
data/gdelt_2024_na_000000000000.csv
data/gdelt_2024_na_000000000001.csv
```

Import the CSV files:

```bash
docker exec gdelt_backend python db_scripts/import_event.py
```

Build the dashboard and forecast summary tables:

```bash
Get-Content db_scripts/dashboard_fast_precompute.sql | docker exec -i gdelt_mysql mysql -uroot -prootpassword gdelt
```

After this, open the Forecast tab and use a forecast start date such as `2024/01/31`.

## Forecast Model

The included checkpoint is:

```text
models/thp_gdelt.pt
```

Current checkpoint metadata:

- Model: neural Transformer Hawkes Process
- Version: `thp_v5_series_event_normalized+calibrated`
- Sequence window: `14` days
- Model size: about `1.56 MB`
- Parameters: about `0.38M`
- Backtest MAE: `83.77`
- Backtest RMSE: `604.71`
- Moving-average baseline MAE: `167.74`

The backend loads it through:

```text
THP_CHECKPOINT_PATH=models/thp_gdelt.pt
```

## Optional: Retrain Or Tune THP

Retraining is not required to run Forecast. If you want to train a new model after importing data:

```bash
docker exec gdelt_backend python db_scripts/train_thp_model.py --epochs 80 --device cpu
```

For GPU environments with CUDA-enabled PyTorch:

```bash
docker exec gdelt_backend python db_scripts/train_thp_model.py --epochs 80 --device cuda --amp
```

To run the GPU hyperparameter sweep used for the final model:

```bash
docker exec gdelt_backend python db_scripts/sweep_thp_gpu.py --deploy-best --device cuda --amp --max-trials 8
```

## Optional: Build ChromaDB For Chat RAG

ChromaDB is not required for Forecast. After importing data and building representative events, create the semantic index with:

```bash
docker exec gdelt_backend python db_scripts/build_chromadb_index.py --reset --limit 10000 --batch-size 256
```

This creates local files under `chroma_db/`, which are intentionally ignored by Git.

## API Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/data/dashboard` | Dashboard summary and representative events |
| `GET /api/v1/data/timeseries` | Daily, weekly, or monthly trends |
| `GET /api/v1/data/geo` | Geographic hotspots |
| `GET /api/v1/data/events` | Search events |
| `GET /api/v1/data/top-events` | High-impact representative events |
| `GET /api/v1/data/compare` | Compare two actors or locations |
| `GET /api/v1/data/country-pair` | Bilateral country-pair trends |
| `GET /api/v1/data/forecast` | THP forecast with intervals and metadata |
| `POST /api/v1/agent/chat` | Analyst chat |

## Example Prompts

```text
Forecast United States and Canada conflict after 2024-02-01.
Compare cooperation versus conflict trends between the United States and Canada in 2024.
Show Canada conflict from January 15 2024 to January 20 2024.
Compare POLICE and Canada for all events in January 2024.
```

## Development Commands

Build frontend:

```bash
docker exec gdelt_frontend npm run build
```

Syntax check backend scripts:

```bash
docker exec gdelt_backend python -m py_compile backend/services/thp_neural.py db_scripts/train_thp_model.py db_scripts/calibrate_thp_checkpoint.py db_scripts/sweep_thp_gpu.py
```

Restart services:

```bash
docker compose restart backend frontend
```

View logs:

```bash
docker logs gdelt_backend --tail 100
docker logs gdelt_frontend --tail 100
```

## License

Virginia Tech DBMS Project.
