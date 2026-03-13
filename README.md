# GDELT Narrative API

A production-ready **Spatio-Temporal Narrative AI Agent** for North America Event Analysis via MCP Architecture.

[![CI](https://github.com/your-org/gdelt-narrative-api/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/gdelt-narrative-api/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## 🎯 Overview

This system uses the **Model Context Protocol (MCP)** to bridge relational MySQL databases with Large Language Models (LLMs). It enables autonomous discovery and synthesis of antecedent events leading up to user-defined target events using the **GDELT 2.0 dataset** (2024 North American events).

### Key Features

- 🔗 **MCP Architecture**: Seamless integration between SQL databases and LLMs
- 🤖 **AI-Powered Analysis**: Uses Moonshot AI (Kimi) for narrative generation
- 🗄️ **GDELT Integration**: Full support for GDELT 2.0 event data
- 🌐 **REST API**: FastAPI-based with OpenAPI documentation
- 📊 **Spatio-Temporal Queries**: Geographic and temporal event filtering
- 🐳 **Docker Ready**: Complete containerization support
- ✅ **Production Quality**: Type hints, testing, linting, CI/CD

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   FastAPI        │────▶│   MCP Client    │
│   (index.html)  │◄────│   (backend)      │◄────│   (mcp/)        │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                    ┌─────────────────────┘
                                    │
                           ┌────────▼────────┐
                           │   MCP Server    │
                           │   (mcp_server/) │
                           └────────┬────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
           ┌─────────────────┐           ┌─────────────────┐
           │   MySQL DB      │           │   LLM (Kimi)    │
           │   (gdelt_db)    │           │   (via API)     │
           └─────────────────┘           └─────────────────┘
```

### Project Structure

```
.
├── backend/
│   ├── src/gdelt_api/          # Main application package
│   │   ├── config/             # Configuration management
│   │   ├── core/               # Core utilities (logging, exceptions)
│   │   ├── api/                # API layer (routes, dependencies)
│   │   ├── services/           # Business logic
│   │   ├── models/             # Pydantic models
│   │   ├── db/                 # Database layer
│   │   ├── mcp/                # MCP client
│   │   └── utils/              # Utilities
│   ├── tests/                  # Test suite
│   ├── alembic/                # Database migrations
│   └── Dockerfile              # Container image
├── mcp_server/                 # MCP Server implementation
├── db_scripts/                 # Database setup scripts
├── docker-compose.yml          # Orchestration
├── pyproject.toml             # Python dependencies
└── Makefile                   # Development commands
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- MySQL 8.0+
- Moonshot AI API Key

### Installation

1. **Clone and setup environment:**

```bash
# Copy environment template
cp .env.example .env
# Edit .env with your credentials
```

2. **Install dependencies:**

```bash
make dev-install
# or
pip install -e ".[dev,lint]"
```

3. **Setup database:**

```bash
# Create database
mysql -u root -p < db_scripts/gdelt_db_v1.sql

# Import data (optional)
python db_scripts/import_event.py

# Run migrations
make migrate
```

4. **Start the server:**

```bash
# Development with auto-reload
make run-dev

# Production
make run
```

The API will be available at `http://localhost:8000`

### Docker Deployment

```bash
# Build and run all services
docker-compose up -d

# View logs
docker-compose logs -f api
```

## 📖 API Documentation

Once running, access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health

### Example Usage

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Chat with AI
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What happened in Washington DC last week?"}]
  }'

# Search events
curl "http://localhost:8000/api/v1/events?country_code=US&start_date=2024-01-01"
```

## 🧪 Development

### Running Tests

```bash
# All tests
make test

# With coverage
make test-coverage

# Specific markers
pytest -m unit        # Unit tests only
pytest -m integration # Integration tests
```

### Code Quality

```bash
# Run all linters
make lint

# Format code
make format

# Pre-commit hooks
pre-commit run --all-files
```

### Project Commands

```bash
make help          # Show all available commands
make migrate       # Run database migrations
make seed-db       # Import sample data
make docker-build  # Build Docker images
make clean         # Clean cache files
```

## 🔧 Configuration

Configuration is managed via environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `ENV` | Environment (development/testing/production) | `development` |
| `DEBUG` | Debug mode | `false` |
| `DB_PASSWORD` | MySQL password | - |
| `API_KEY` | Moonshot AI API key | - |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FORMAT` | Log format (json/console) | `json` |

## 📚 Tech Stack

| Component | Technology |
|-----------|------------|
| Web Framework | FastAPI |
| Database | MySQL 8.0 + SQLAlchemy 2.0 |
| LLM | Moonshot AI (Kimi) |
| MCP | Model Context Protocol |
| Testing | pytest + pytest-asyncio |
| Linting | ruff + mypy + bandit |
| CI/CD | GitHub Actions |
| Container | Docker + Docker Compose |

## 📝 License

MIT License - See [LICENSE](LICENSE) for details.

## 👥 Research Team

Virginia Tech - "Ut Prosim" (That I May Serve)

- Xing Gao
- Xiangxin Tang
- Yuxin Miao
- Ziliang Chen

## 📄 Citation

If you use this project in your research, please cite:

```bibtex
@article{gdelt_narrative_api,
  title={Spatio-Temporal Narrative AI Agent for North America Event Analysis via MCP Architecture},
  author={Tang, Xiangxin and Gao, Xing and Miao, Yuxin and Chen, Ziliang},
  institution={Virginia Tech},
  year={2024}
}
```
