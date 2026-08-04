# 06 — Folder Structure

## 1. Top level

```
invoiceiq/
├── apps/
│   └── web/                        # Next.js dashboard + BFF
├── backend/
│   ├── pyproject.toml
│   ├── src/invoiceiq/              # the one Python package (shared by api+worker)
│   └── alembic/                    # migrations
├── packages/
│   └── schemas/                    # canonical JSON schema (source of truth)
├── infra/
│   ├── docker/                     # Dockerfiles, compose fragments
│   ├── monitoring/                 # prometheus.yml, grafana provisioning
│   └── deploy/                     # systemd units, scripts, k8s (later)
├── docs/                           # this documentation package
├── tests/                          # pytest suite + fixtures + golden sets + eval
├── .github/workflows/              # CI
├── Makefile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## 2. Backend package (`backend/src/invoiceiq`)

```
invoiceiq/
├── main.py                 # FastAPI app factory (env-gated: api/worker/export)
├── settings.py             # pydantic-settings, env-driven
├── db.py                   # engine, session factory, RLS context manager
├── api/
│   ├── deps.py             # auth deps, org ctx, rate limits
│   ├── errors.py           # domain errors -> error envelope
│   ├── routers/
│   │   ├── auth.py  orgs.py  members.py
│   │   ├── invoices.py  suppliers.py  exports.py
│   │   ├── webhooks.py  api_keys.py  usage.py  audit.py
│   └── openapi.py          # tags, security schemes, example payloads
├── workers/
│   ├── app.py              # Celery app (broker from settings)
│   ├── chain.py            # task DAG definition & wiring
│   ├── ingest.py  ocr.py  classify.py  extract.py  validate.py  finalize.py  export.py
├── core/
│   ├── tenancy.py          # org ctx, RLS enforcement
│   ├── audit.py            # audit_logs writer
│   ├── errors.py           # domain exceptions + codes
│   └── events.py           # outbound webhook event bus
├── storage/
│   ├── base.py             # Storage protocol (put/get/presign/delete)
│   ├── local.py  s3.py     # disk + S3-compatible impls
├── ingest/
│   ├── normalize.py        # unzip, HEIC, format detect
│   └── pdf.py              # text-layer extraction + rasterize
├── ocr/
│   ├── base.py             # OCREngine protocol
│   ├── paddle.py  tesseract.py  digital.py
├── extract/
│   ├── rules/              # deterministic extractors
│   │   ├── vat.py  iban.py  dates.py  numbers.py  invoice_number.py
│   ├── llm.py              # LLM extraction (provider-agnostic)
│   ├── vlm.py              # multimodal escalation
│   ├── merge.py            # field merge precedence (docs/12 §3.3)
│   └── schema.py           # extraction contract schema
├── llm/
│   ├── registry.py         # provider routing by org policy
│   ├── providers/
│   │   ├── mistral.py  openai.py  anthropic.py  gemini.py  local.py
│   └── tokens.py           # budgeting, structured-output helpers
├── validate/
│   ├── engine.py           # rule runner + results
│   ├── arithmetic.py       # reconciliation w/ correct rounding
│   ├── vat/                # per-country profiles + VIES client
│   ├── iban.py  dates.py  mandatory.py  currency.py
├── confidence/
│   └── engine.py           # composite field confidence + thresholds
├── review/
│   └── service.py          # corrections, approve/reject, learning hooks
├── export/
│   ├── csv.py  xlsx.py  json.py  xml.py  builders.py
├── usage/
│   └── service.py          # usage_events writer
└── webhooks/
    ├── dispatch.py  signatures.py  retry.py
```

**Isolation rule:** `ocr`, `extract`, `llm`, `validate`, `confidence` never import each other's internals; they communicate via the extraction contract (`extract/schema.py`). This keeps each a future microservice seam and makes eval/testing trivial.

## 3. Frontend (`apps/web`)

```
apps/web/
├── app/
│   ├── (marketing)/            # landing page (round 2)
│   ├── (auth)/login  register  invite
│   ├── (app)/                  # authenticated shell (sidebar, org switcher)
│   │   ├── invoices/           # list + review detail
│   │   ├── suppliers/
│   │   ├── settings/           # org, team, keys, webhooks
│   │   └── usage/
│   ├── layout.tsx  providers.tsx
├── components/
│   ├── ui/                     # shadcn primitives (installed)
│   ├── upload/                 # Dropzone, UploadQueue, BulkProgress
│   ├── invoices/               # Table, Filters, StatusBadge, ReviewView...
│   ├── document/               # DocumentViewer, HighlightLayer, PageNav
│   ├── fields/                 # FieldCard, FieldInput, ConfidenceRing, SourcePopover
│   └── layout/                 # Sidebar, OrgSwitcher, ThemeToggle, CommandPalette
├── lib/                        # api client, react-query hooks, utils
├── types/                      # zod schemas (mirrors packages/schemas)
├── hooks/
├── middleware.ts               # auth guard
└── next.config.ts  tailwind.config.ts
```

## 4. Packages (`packages/schemas`)

```
schemas/
├── invoice.schema.json         # extraction contract (canonical)
├── events.schema.json          # webhook payloads
├── api.schema.json             # request/response types
└── README.md                   # how py (pydantic) + ts (zod) are generated/kept in sync
```

**Why a canonical JSON schema:** Pydantic and Zod both generate from it in CI, so the extraction contract can never drift between backend, frontend, and SDK. This is the highest-leverage file in the repo.

## 5. Tests

```
tests/
├── unit/                       # validators, arithmetic, confidence, rules
├── integration/                # api + db (real postgres via testcontainers)
├── e2e/                        # playwright (web)
├── load/                       # locust scenarios
├── fixtures/                   # sample PDFs/images (per country/layout)
├── golden/                     # labeled ground-truth (eval source of truth)
│   ├── invoices.jsonl          # doc → expected fields
│   └── errors.jsonl            # seeded error cases (fraud/vat mismatch)
└── eval/                       # harness + reports/ (field-F1 per country)
```

## 6. CI/CD

```
.github/workflows/
├── ci.yml                      # lint (ruff), typecheck (pyright/tsc), pytest, build images
├── eval.yml                    # nightly eval run on golden set, regressions to GitHub issue
└── deploy.yml                  # SSH deploy to VPS (compose pull + up)
```

## 7. Why this shape (solo-founder lens)

- One package = one mental model; modules mirror the pipeline so the docs → code mapping is 1:1.
- `Makefile` encodes every dev command (`make dev`, `make test`, `make eval`, `make lint`, `make up`) so muscle memory is trivial.
- The `extract/schema.py` contract means the review UI, export builders, and SDK all consume the identical shape — no glue code to drift.
