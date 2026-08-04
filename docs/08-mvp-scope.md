# 08 — MVP Scope

## 1. Definition

The MVP is the smallest release a European SME or accounting firm will pay for: **upload → validated structured data → human review → export + API**. Everything outside this is post-MVP.

## 2. In scope (MVP)

### Upload
- Web upload: drag-and-drop, file picker, multi-file, bulk, ZIP (nested), paste-from-clipboard
- REST API upload (`multipart`, up to 100 files/batch)
- Format: PDF, PNG, JPEG, WEBP, HEIC; ≤20 MB/file
- SHA-256 dedupe with `duplicate_of` response
- Async: `202` + status polling + webhooks

### Processing pipeline (MVP quality bar)
- Digital PDF native text path (no OCR cost)
- PaddleOCR for scanned/images/rotated/low-DPI (deskew + auto-orientation)
- Tesseract fallback for unsupported languages
- Multi-page support
- Doc classification: invoice / credit note / proforma / other
- Hybrid extraction: rules-first → Mistral LLM → merge (see `docs/12`)
- All header fields + line items from `docs/01` §5.3

### Validation (MVP)
- Arithmetic: per-line net, VAT, gross; subtotal; total reconciliation with rounding
- VAT number format + VIES (cached); reverse-charge & intra-community recognition
- IBAN structure + MOD-97; BIC format
- Date parse + sanity; currency ISO; mandatory fields for DE/IT/FR/ES/NL/BE/AT

### Confidence & review
- Per-field composite confidence + reason codes
- Org-configurable threshold → `requires_review`
- Review UI: split viewer, field highlight → source bbox, edit/approve/reject, bulk approve
- Corrections persisted + audit

### Export & integration surface
- CSV, XLSX, JSON, XML exports (async, presigned download)
- REST API (OpenAPI), API keys, webhooks (HMAC, retries, event log, replay)
- Audit logs for all user/key actions

### Tenancy & auth
- Orgs, teams, invitations, RBAC (owner/admin/member/viewer)
- Email + password, JWT sessions, password reset
- EU-only default processing; per-org `data_residency` policy field enforced

### Ops
- Docker Compose staging/prod on EU VPS, backups, Sentry, Prometheus/Grafana, structured logs
- Usage metering (pages processed) recorded (billing UI is P2)

## 3. Out of scope (explicit)

- Stripe billing/subscriptions/credit enforcement UI (metering recorded only)
- SSO, SCIM, TOTP MFA (auth hardening P2; basic security remains)
- Email ingest, folder monitoring
- Duplicate detection module, fraud scoring module
- NL search, AI chat
- Workflow builder, approval chains
- ERP connectors, e-invoicing (XRechnung/ZUGFeRD)
- Analytics dashboards
- Mobile app / SDKs
- Local VLM (sovereign GPU path)

## 4. MVP acceptance criteria

| # | Criterion | Target |
|---|---|---|
| A1 | Digital PDF → completed, no review | ≥ 85% of golden digital set |
| A2 | Scanned single-page → completed | ≥ 70% of golden scanned set |
| A3 | Field F1 vs golden | header ≥ 0.95, line items ≥ 0.90 |
| A4 | Arithmetic/VAT error recall | ≥ 95% on seeded-error set |
| A5 | No silent wrong money | 100% of extracted totals reconcile or are flagged |
| A6 | Review time | ≤ 60 s P50 |
| A7 | End-to-end API upload → webhook | round-trip ≤ 30 s (digital), ≤ 2 min (scan) P95 |
| A8 | Org isolation | cross-org access impossible (RLS test suite) |
| A9 | GDPR/security checklists | all MVP items closed (`docs/18`,`docs/19`) |
| A10 | Cost | ≤ $0.08 avg per digital page, ≤ $0.15 per scanned page (staging telemetry) |

## 5. Definition of done per feature
Feature ships when: golden-set eval passes for affected fields, integration tests green, audit events written, docs/API updated, staging deploy succeeds, and (for review/export) Playwright smoke passes.

## 6. What "pay" means
Design partners get 2-months free processing of real invoices in exchange for labeled ground truth (their corrections become golden data). Billing gates on A1–A10.
