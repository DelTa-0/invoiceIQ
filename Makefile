PY := backend/.venv/Scripts/python.exe
PIP := $(PY) -m pip
UVICORN := $(PY) -m uvicorn
CELERY := $(PY) -m celery
DOCKER_COMPOSE := docker compose

.PHONY: help setup up down migrate api worker test lint typecheck ci status

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv, install backend, start infra
	$(PY) -m venv backend/.venv
	$(PIP) install -e "backend[dev]"
	$(DOCKER_COMPOSE) up -d
	make migrate

up: ## Start Postgres + Redis
	$(DOCKER_COMPOSE) up -d

down: ## Stop infra
	$(DOCKER_COMPOSE) down

migrate: ## Run alembic migrations (working dir backend)
	cd backend && .venv/Scripts/python.exe -m alembic upgrade head

api: ## Run the API on :8000
	cd backend && .venv/Scripts/python.exe -m uvicorn invoiceiq.main:app --reload --port 8000

worker: ## Run a Celery worker
	cd backend && .venv/Scripts/python.exe -m celery -A invoiceiq.workers.app:celery_app worker --pool=solo --loglevel=info

test: ## Unit + API tests
	cd backend && .venv/Scripts/python.exe -m pytest

lint: ## Ruff check (backend + root)
	cd backend && .venv/Scripts/python.exe -m ruff check .
	.venv/Scripts/python.exe -m ruff check .

typecheck: ## Pyright (backend)
	cd backend && .venv/Scripts/python.exe -m pyright src

ci: test lint typecheck ## Everything CI runs

status: ## Running containers
	$(DOCKER_COMPOSE) ps
