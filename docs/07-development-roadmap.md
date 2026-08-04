# 07 — Development Roadmap

Principles: ship the pipeline before the dashboard, ship the contract before the features, keep the eval harness running from week 1 (you can't improve what you can't measure), and never block shipping on billing/SSO.

## Phase 0 — Foundation (weeks 1–2)
**Exit criteria:** `make dev` boots the full stack on a laptop; CI green; a hand-made PDF reaches `status=completed`.

- [x] Repo, docs package, git init
- [ ] `docker-compose.yml`: postgres, redis, (minio), api, worker, web
- [ ] Backend skeleton: settings, FastAPI app factory, health endpoint, Celery app, storage abstraction
- [ ] Auth: register/login/refresh, JWT, RBAC stubs, org creation
- [ ] SQLAlchemy models + Alembic baseline migration (full `docs/04` schema)
- [ ] RLS policy set + `app.org_id` context
- [ ] Frontend skeleton: Next.js + Tailwind + shadcn, auth pages, app shell
- [ ] CI (ruff, pyright, tsc, pytest), Makefile, `.env.example`
- [ ] `tests/golden/` scaffolding + fixture generator script

## Phase 1 — MVP (weeks 3–8)
**Exit criteria:** P1 acceptance in `docs/08` passes; eval harness reports F1 ≥ target on golden set; a paying design-partner runs a real 50-invoice batch.

- [ ] Ingest: upload API (multi/zip), normalize, dedupe (sha256), object storage
- [ ] OCR layer: digital path (pdfplumber) + PaddleOCR + Tesseract fallback; page blocks model
- [ ] Document classification (invoice/credit note/other)
- [ ] Extraction: rules (VAT/IBAN/dates/numbers/invoice number) → LLM (Mistral) → merge
- [ ] Validation: arithmetic reconciliation, VAT format + VIES, IBAN, mandatory (DE first, then IT/FR/ES/NL/BE/AT)
- [ ] Confidence engine + thresholds
- [ ] Review UI: document viewer + field editor + highlights + approve/reject
- [ ] Corrections + learning-loop storage
- [ ] Exports: CSV/XLSX/JSON/XML
- [ ] Webhooks + event log + replay
- [ ] Usage metering + audit logging complete
- [ ] Eval harness operational; golden set ≥ 300 invoices across 7 countries/languages
- [ ] Staging deploy + monitoring (Sentry, Prometheus/Grafana)

## Phase 2 — Growth (weeks 9–16)
- [ ] Stripe billing + subscription plans + credit gating
- [ ] Email ingest (forward-to-address) + attachment normalization
- [ ] Folder monitoring (SFTP/Drive/SMB) for accounting firms
- [ ] Duplicate & near-duplicate detection
- [ ] Fraud signals: tampering heuristics, IBAN-change velocity, missing VAT, supplier anomaly
- [ ] Suppliers module UI + merge
- [ ] TOTP MFA; API key scopes hardening
- [ ] NL search (LLM→filter) + saved filters
- [ ] De/FR/IT/ES/NL UI localization
- [ ] Load test to 10k/day; GPU OCR node (optional)

## Phase 3 — Enterprise (months 5–9)
- [ ] SSO (OIDC/SAML) + SCIM
- [ ] Integrations: DATEV (CSV/ZUGFeRD), Lexoffice, Odoo, Xero, QuickBooks; webhook-driven
- [ ] E-invoicing: XRechnung/ZUGFeRD import + Factur-X (the German/French enterprise wedge)
- [ ] Workflow rules builder (if/then on supplier/VAT/total)
- [ ] AI chat over invoices (RAG over extracted facts) + pgvector semantic search
- [ ] Analytics dashboards (spend, VAT, processing cost)
- [ ] Approval flows (multi-step, roles)

## Phase 4 — Scale (months 10+)
- [ ] k3s → managed K8s; partitioned queues (ocr/extract/validate/export)
- [ ] Managed PG/Redis/S3 in EU region; pgBouncer
- [ ] GPU worker pool + local Qwen2.5-VL sovereign option
- [ ] Multi-region EU (data locality per country)
- [ ] 100k/day capacity test + cost telemetry review

## Parallel threads (start early, run always)
- **Eval:** golden set grows by ≥50/week from real corrections; nightly eval job.
- **Cost:** per-invoice cost telemetry visible in staging dashboard from P1.
- **Security/GDPR:** checklists (`docs/18`, `docs/19`) signed off before P1 GA; DPIA drafted in P2.
- **GTM (Round 2 docs):** landing, pricing, demo script drafted in parallel with P2.

## Risks to timeline
| Risk | Mitigation |
|---|---|
| PaddleOCR table quality on EU layouts | PP-Structure + post-merge heuristics; golden-set-driven; VLM escalation fallback |
| VIES flakiness | Cache + degrade to format-only |
| LLM structured-output drift | JSON-schema validation + retry-with-fix; pinned provider versions |
| Review UI scope creep | Wireframes (`docs/10`) frozen; keyboard-first bulk ops deferred |
| Partner churn mid-P1 | Design partners signed for 2 fixed batches; SLA via staging |
