# GDELT Narrative API Makefile

.PHONY: help install dev-install test lint format clean docker-build docker-run migrate run run-dev

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development
install: ## Install production dependencies
	pip install -e "."

dev-install: ## Install development dependencies
	pip install -e ".[dev,lint]"
	pre-commit install || echo "pre-commit not installed, skipping"

# Testing
test: ## Run all tests
	cd backend && PYTHONPATH=./src python -m pytest ../tests

test-unit: ## Run unit tests only
	cd backend && PYTHONPATH=./src python -m pytest ../tests -m unit

test-integration: ## Run integration tests
	cd backend && PYTHONPATH=./src python -m pytest ../tests -m integration

test-coverage: ## Run tests with coverage report
	cd backend && PYTHONPATH=./src python -m pytest ../tests --cov=gdelt_api --cov-report=html --cov-report=term

# Linting and formatting
lint: ## Run linters (ruff, mypy, bandit)
	cd backend && ruff check src
	cd backend && mypy src
	cd backend && bandit -r src

format: ## Format code with ruff
	cd backend && ruff format src
	cd backend && ruff check --fix src

# Database
migrate: ## Run database migrations
	cd backend && PYTHONPATH=./src alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create msg="description")
	cd backend && PYTHONPATH=./src alembic revision --autogenerate -m "$(msg)"

# Docker
docker-build: ## Build Docker images
	docker-compose build

docker-run: ## Run services with Docker Compose
	docker-compose up -d

docker-stop: ## Stop Docker services
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f api

# Development server
run: ## Run development server (Windows compatible)
	cd backend && set PYTHONPATH=./src && python -m gdelt_api.main

run-dev: ## Run with auto-reload (Windows compatible)
	cd backend && set PYTHONPATH=./src && python -m uvicorn gdelt_api.main:app --reload --host 0.0.0.0 --port 8000

# Unix/Mac alternative
run-unix: ## Run on Unix/Mac
	cd backend && PYTHONPATH=./src python -m gdelt_api.main

run-dev-unix: ## Run with auto-reload on Unix/Mac
	cd backend && PYTHONPATH=./src uvicorn gdelt_api.main:app --reload --host 0.0.0.0 --port 8000

# Cleaning
clean: ## Clean up cache files
	python -c "import shutil, glob; [shutil.rmtree(p, True) for p in glob.glob('**/__pycache__', recursive=True)]"
	python -c "import os, glob; [os.remove(f) for f in glob.glob('**/*.pyc', recursive=True)]"
	python -c "import os, glob; [os.remove(f) for f in glob.glob('**/*.pyo', recursive=True)]"
	python -c "import shutil; shutil.rmtree('htmlcov', True)"
	python -c "import os; os.remove('.coverage') if os.path.exists('.coverage') else None"

# Utilities
seed-db: ## Seed database with sample data
	python db_scripts/import_event.py

requirements: ## Export requirements.txt (requires pip-tools)
	pip-compile pyproject.toml -o requirements.txt || echo "pip-tools not installed, run: pip install pip-tools"
	pip-compile --extra dev pyproject.toml -o requirements-dev.txt || echo "pip-tools not installed"
