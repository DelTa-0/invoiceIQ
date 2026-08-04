# 02 — Technical Architecture

## 1. Architecture at a glance

```
                    ┌────────────────────────────────────────────┐
                    │             apps/web (Next.js)             │
                    │  UI · BFF · React Query · TanStack Table   │
                    └──────────────────┬─────────────────────────┘
                                       │ HTTPS / JSON
                    ┌──────────────────▼─────────────────────────┐
                    │         services: api (FastAPI)            │
                    │  Auth/RBAC · REST /v1 · Webhooks dispatch  │
                    │  Orchestration · Signed URLs · Usage       │
                    └───────────────┬───────────────┬────────────┘
                                    │ enqueue       │ read
                    ┌───────────────▼───────┐  ┌────▼────────────────┐
                    │  Redis (broker/cache) │  │  PostgreSQL 16      │
                    │  rate-limit · pubsub  │  │  RLS · pg_trgm      │
                    └───────────────┬───────┘  │  tsvector · jsonb   │
                                    │          └─────────────────────┘
                    ┌───────────────▼───────┐
                    │  workers (Celery)     │  ┌───────────────────────┐
                    │  ingest→ocr→extract   │  │ MinIO / S3-compatible │
                    │  →validate→confidence │  │  docs + exports       │
                    └───────────────┬───────┘  └───────────────────────┘
                                    │
                    ┌───────────────▼───────┐  ┌───────────────────────┐
                    │  LLM Provider Registry│  │  VIES / external      │
                    │  Mistral (EU) default │  │  checks (cached)      │
                    │  + opt-in US routes   │  └───────────────────────┘
                    └───────────────────────┘
```

**The queue is the seam.** Every long-running step (OCR, extraction, validation, export) is a Celery task. The API never blocks on AI; it enqueues and returns `202`. This single decision gives horizontal scaling, retries, and a natural place for observability.

## 2. Decision rationale & trade-offs

### D1. Monorepo, modular monolith, one Python package
- **Choice:** `apps/web` (Next.js) + `backend/src/invoiceiq` (FastAPI + Celery share the same package) + `packages/schemas`.
- **Why:** FastAPI, Celery workers, and validation must share domain models. One package = atomic deploys, one Alembic tree, no version skew.
- **Why not microservices:** solo founder on one VPS; service boundaries add distributed-system tax (networking, retries, tracing) before you have a customer. The module boundaries *are* the future microservice seams — `ocr`, `extract`, `llm`, `validate`, `confidence` are import-isolated packages with interfaces, so splitting later is mechanical.
- **Trade-off:** single deploy unit; mitigated by worker/API separate processes and the queue.

### D2. Broker: Celery + Redis (deviation from brief)
- **Brief says RabbitMQ.** On one VPS that's an Erlang service for zero benefit at MVP volume. Redis is already required (cache, rate limit, pub/sub, session). Celery+Redis is battle-tested at 10k+/day.
- **Why not Redis-pure (RQ/arq):** Celery gives beat scheduling, rate limiting, prefork, and a huge community — the brief demands Celery, and it is the right long-term choice.
- **Migration path:** `core/queue.py` abstracts broker config; RabbitMQ = env swap. Documented in `docs/17`.

### D3. Multi-tenancy: single Postgres + RLS
- **Why:** schema-per-tenant kills connection pooling (each tenant needs N pools or a pooler with spooky session state) and complicates every migration. A single database with **Postgres Row-Level Security** enforces org isolation at the engine level — a query that forgets `org_id` returns zero rows, not another org's data.
- **Trade-off:** all tenants share tables → need careful index sizing and `ANALYZE`. Fine at 100k invoices/day. Supabase-style SaaS standard.

### D4. Async everything
Upload → `202` + `processing_jobs` row → task chain. UI polls or subscribes. **Why:** AI latency (1–120 s) must not hold HTTP connections; retries/dead-letters are free; burst handling via queue backlog.

### D5. S3-compatible storage behind an interface
- Local disk (dev), MinIO (VPS), Hetzner Object Storage / AWS S3 / Cloudflare R2 (scale) — all behind `storage.py`.
- Documents served via **short-lived presigned URLs**, never through the API body (keeps CDN options open and audits every access).

### D6. Hybrid extraction, deterministic-first
- Digital PDF text ≈ free and exact → use it. PaddleOCR for scans. **Regex/rule engine first** for well-formed fields (VAT, IBAN, dates, numbers), LLM only where rules can't reliably reach (supplier names, line-item semantics, ambiguous layouts). VLM only as escalation.
- **Why:** per-invoice LLM cost at $0.10–0.30/page destroys SME margin; rules are free, deterministic, auditable. LLM adds generality where rules are brittle.
- **Order of precedence per field:** deterministic match > LLM > VLM, with cross-checks. (See `docs/12`.)

### D7. LLM provider registry + residency policy
- Registry maps `(org.policy, task, quality)` → provider. Default: **Mistral EU** (extraction). Opt-in orgs may enable OpenAI/Claude/Gemini with DPA; sovereign orgs use local Qwen2.5-VL on a GPU node.
- **Why:** residency is the product's legal wedge and must be an org setting, not a fork. Switch models = config row, not code.

### D8. Validation is deterministic, never the LLM
The LLM proposes; the **rule engine disposes**. Arithmetic reconciliation, VAT/IBAN checks, mandatory-field compliance are pure Python with unit-tested rounding semantics. LLM errors become flagged review items instead of silent bad data.

### D9. Search: LLM→typed filter, not RAG (MVP)
NL query → cheap LLM translates to typed filter params → SQL on pg_trgm/tsvector. **Why:** invoices are structured facts; RAG-over-invoices invites hallucinated rows. pgvector semantic layer is P3 for supplier similarity/fuzzy matching.

## 3. Tech stack (pinned)

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js 15 (App Router), TypeScript 5, Tailwind 4, shadcn/ui, React Query 5, TanStack Table 8, Framer Motion, Zod | `pnpm` |
| BFF/UI | Next.js API routes for proxying to FastAPI (auth token forwarding, no CORS pain in prod) | |
| API | FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, slowapi (rate limit), authlib | Uvicorn behind Caddy |
| Workers | Celery 5 + Redis (broker/backend), preload-pool | separate process/container |
| DB | PostgreSQL 16 (+ `pg_trgm`, `citext`), RLS, `pgvector` later | |
| Cache | Redis 7 | |
| Storage | MinIO (dev/VPS) → S3-compatible | presigned URLs |
| OCR | pypdf/pdfplumber (digital) · PaddleOCR PP-OCRv4 + PP-Structure · Tesseract fallback | CPU-first |
| LLM | Mistral (EU) default; registry: OpenAI, Anthropic, Gemini, local Qwen2.5-VL | provider package |
| Validation | `schwifty`/custom (IBAN), `stdnum` (VAT format), VIES REST proxy (cached), custom arithmetic engine | |
| Observability | structlog, OpenTelemetry, Prometheus + Grafana, Sentry | |
| Deploy | Docker Compose (Caddy) on EU VPS → k3s/Helm later; GitHub Actions CI | |
| E2E | Playwright; pytest + httpx; locust (load) | |

## 4. Concurrency & scaling model

- **Unit of work:** an invoice = one task chain (DAG): `ingest → route → ocr → classify → extract → validate → confidence → finalize`. Retryable per-stage; failed stages mark invoice `failed` with stage + error.
- **Workers scale horizontally** by subscribing to the same queue; task-level idempotency via `processing_jobs` state + document hash.
- **Throughput math (CPU OCR, PaddleOCR):** ~2–4 s/page single-thread; a 4-vCPU worker sustains ~15–60 pages/min. 10k/day ≈ 7/min average → one 4-core worker is comfortable with bursts; two for headroom. GPU node cuts OCR 5–10× and unlocks VLM.
- **Cost guardrails:** digital PDFs skip OCR; LLM tokens budgeted per invoice; extraction cache keyed by doc-hash + model version.

## 5. Environments

| Env | Where | DB | Docs |
|---|---|---|---|
| dev | laptop, host-run API/web + docker PG/Redis | local | `docs/17` §DevMachine |
| staging | VPS, compose, seeded golden set | VPS PG | CI-deployed |
| prod | VPS → managed EU cloud | managed PG | `docs/17` |

## 6. Cross-cutting concerns

- **Config:** pydantic-settings + `.env`; no secrets in repo; secrets vaulted (Docker secrets / SOPS later).
- **Errors:** domain error codes (`INVOICE_VALIDATION_FAILED`, `OCR_NO_TEXT`, `UPLOAD_TOO_LARGE`…), structured logs with `request_id`/`invoice_id`/`org_id`.
- **Observability:** OpenTelemetry traces on task chain + HTTP; Prometheus metrics (`invoiceiq_processing_duration`, `invoiceiq_llm_cost_total`, `invoiceiq_stp_rate`); Grafana dashboards.
- **Testing:** see `docs/16` — golden sets, property tests, eval harness, E2E.
