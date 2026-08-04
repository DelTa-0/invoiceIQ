# InvoiceIQ

EU-first, GDPR-first AI accounts-payable for European SMEs. Upload supplier
invoices → deterministic-rules + AI extraction → validated structured data →
quick human review for low-confidence fields → export to your accounting
system or pull via API.

**Status:** Phase-0 scaffold. Backend + data model, extraction/validation core
with tests, auth, upload pipeline skeleton, Alembic migrations with RLS
tenancy, and a minimal Next.js frontend are all in place and verified end to
end locally.

## Stack

- **API / workers:** Python 3.12, FastAPI, SQLAlchemy, Celery, Alembic
- **DB:** PostgreSQL 16 with row-level security (org-isolated tenancy)
- **Queue:** Redis
- **Web:** Next.js 16 (App Router, Tailwind CSS), standalone build
- **LLM:** Mistral by default (EU); US providers are per-tenant opt-in
- **Deploy target:** single EU VPS via Docker Compose + Caddy (TLS)

## Layout

```
backend/            FastAPI app + Celery workers (single shared package)
  src/invoiceiq/      settings, db, models, extract, validate, confidence,
                      storage, workers, api
  alembic/            migrations (0001 = initial schema + RLS + audit trigger)
frontend/           Next.js app (marketing, auth, dashboard)
infra/docker/       Dockerfiles, init-db.sql (app role), Caddyfile
tests/              pytest suite (unit + API smoke)
docs/               00-19 design/requirements docs
```

## Quickstart (dev)

Requirements: Python 3.12, Node 22+, Docker, `make` (optional).

```bash
# 1. Start Postgres (host port 5433) + Redis
docker compose up -d

# 2. Backend
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -e "backend[dev]"
cd backend
.venv/Scripts/python -m alembic upgrade head   # applies schema + RLS
.venv/Scripts/python -m uvicorn invoiceiq.main:app --reload --port 8000

# 3. Worker (separate terminal)
cd backend
.venv/Scripts/python -m celery -A invoiceiq.workers.app:celery_app worker --pool=solo --loglevel=info

# 4. Web
cd frontend && npm install && npm run dev     # http://localhost:3000
```

API docs: http://127.0.0.1:8000/v1/docs · health: http://127.0.0.1:8000/healthz

### Important

- The **app role** is `invoiceiq_app` (non-superuser). RLS is bypassed for
  superusers, so the API/worker must connect as this role for tenant isolation
  to enforce. `infra/docker/init-db.sql` creates it on first container start;
  on an existing database run it once manually as a superuser.
- Local Postgres is on port **5433** because a native Postgres typically owns
  5432. Set `IIQ_DATABASE_URL` in `.env` to match (see `.env.example`).

## Checks

```bash
cd backend && .venv/Scripts/python -m pytest -q   # tests (root dir)
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m pyright src
cd ../frontend && npm run lint && npm run build
```

## Deployment

See `docs/17` and `docker-compose.prod.yml`. Build the images, export the
`IIQ_*` secrets, and run `docker compose -f docker-compose.prod.yml up -d`.
