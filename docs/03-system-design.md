# 03 — System Design

## 1. Component inventory

| Component | Kind | Purpose | Scale path |
|---|---|---|---|
| `apps/web` | Next.js | UI, BFF, auth session | static CDN + serverless later |
| `api` | FastAPI | REST, auth/RBAC, orchestration, webhooks | scale out behind Caddy (stateless) |
| `worker` | Celery | task chain execution | N workers, then GPU pool |
| `postgres` | DB | source of truth | pgBouncer → managed PG |
| `redis` | broker/cache | queue, rate limit, pub/sub | managed Redis |
| `minio` | object storage | docs, exports | S3-compatible managed |
| `llm-gateway` | in-process | provider registry + budgets | — |
| `vies-proxy` | small FastAPI | VAT validation (cached) | — |

## 2. Request lifecycles

### 2.1 Upload → completed
```
POST /v1/invoices (multipart)           API
  ├─ validate file (size/type/dup hash) 
  ├─ persist raw object (MinIO) + invoice row(status=queued)
  └─ enqueue ingest                ──► worker
        ingest: unpack zip, normalize, split pages
        route: digital text? no-OCR : OCR(PaddleOCR)
        ocr: per page → page blocks (text+bbox+conf+table)
        classify: invoice|credit_note|proforma|not-invoice (LLM+rules)
        extract: rules-first → LLM → VLM escalation → field merge
        validate: arithmetic + VAT + IBAN + mandatory
        confidence: per-field composite
        finalize: compute status (completed|requires_review)
                                           ──► POST webhook invoice.processing_completed
```

### 2.2 Human correction → learning
```
POST /v1/invoices/{id}/corrections      API (RBAC: member+)
  ├─ validate payload against schema
  ├─ persist correction (old,new,source,context) + audit
  ├─ recompute affected validation + confidence
  └─ enqueue learn                     ──► worker: append to supplier/country few-shot store + eval candidate set
```

### 2.3 Export
```
POST /v1/exports {type, filters, format}    API
  ├─ enqueue export task              ──► worker
        query rows → build CSV/XLSX/JSON/XML → store → audit
  └─ 202; GET /v1/exports/{id} → presigned URL when ready
```

## 3. Data flow details

### 3.1 Document normalization
- Ingest produces `invoice_pages`: for PDFs, `pdfplumber` extracts native text + word boxes; if text density ≈ 0 → rasterize (PyMuPDF, 300 DPI) → PaddleOCR. Images → EXIF orientation normalize → PaddleOCR. HEIC converted via `pillow-heif`.
- Every OCR block: `{text, x0,y0,x1,y1, confidence, line_no, reading_order, table_cell?}`.

### 3.2 Extraction contract (the currency of the system)
Every field is an object:
```json
{
  "field": "vat_number",
  "value": "DE123456789",
  "confidence": 0.96,
  "method": "regex+VIES",
  "source_text": "USt-IdNr.: DE123456789",
  "bbox": {"page": 0, "x0":0.6,"y0":0.2,"x1":0.8,"y1":0.22},
  "validator": {"status":"pass","rule":"vat_format_de","detail":"..."},
  "status": "accepted"
}
```
All are persisted in `extraction_fields` (see `docs/04`).

### 3.3 Field merge precedence
1. Deterministic extractors (regex/rules) — mark `method=rules`, conf from regex quality + OCR char conf
2. LLM for residual fields — grounded, must return source+bbox
3. VLM escalation for low-OCR-confidence pages
4. Cross-field reconciliation: invoice date vs due date, totals recomputation — validator wins, extraction flagged `warn`
5. Missing mandatory → `requires_review`

### 3.4 Confidence composite
`conf = w1·method + w2·ocr + w3·consistency + w4·validator` per field class, reason codes attached (`docs/12` §Confidence). Org threshold from `org_settings`.

## 4. Async primitives

- **Task DAG:** each stage idempotent; state in `processing_jobs`; `stage`, `status`, `attempt`, `error`.
- **Retries:** Celery retry w/ exponential backoff (3×) for transient (LLM 429/5xx, VIES timeout); permanent failures (OCR no text, unsupported format) mark failed immediately.
- **Dead letter:** tasks exceeding max retries → `worker_dlq` redis list; alert; manual replay tool.
- **Idempotency:** file SHA-256 dedupe; processing idempotent by `processing_jobs.id`; webhook delivery idempotent by event id.
- **Backpressure:** queue depth metric + auto worker scaling (compose: worker replicas; k8s: HPA on queue depth).

## 5. Caching & external calls

| External | Policy | Fallback |
|---|---|---|
| VIES VAT check | Redis cache TTL 24h (per VAT+timestamp), stale-while-revalidate | format-only validation, flag `warn` |
| LLM provider | no cache (privacy), token budget per invoice | registry fallback provider |
| OCR models | loaded once in worker (warm) | Tesseract |
| ISO/currency/rates | local static, versioned | — |

## 6. Security architecture (summary — full in `docs/18`)

- **AuthN:** email+password (argon2id via `pwdlib`), JWT access (15 min) + refresh (rotating, Redis deny-list), TOTP MFA (P2), OIDC SSO (P3).
- **AuthZ:** RBAC roles (owner/admin/member/viewer) + Postgres RLS per org. API requests scoped by JWT org claims; API-key requests scoped by key's org.
- **Keys:** API keys stored as `sha256` hash only; prefix `iiq_`; granular scopes; rotation.
- **Documents:** presigned URLs (5 min TTL), path encodes org/invoice; access audited.
- **Rate limiting:** slowapi per-route (auth brute-force, upload, export), Redis-backed.
- **Secrets:** env/secrets manager; no secrets in repo (`.env` gitignored).
- **Audit:** append-only `audit_logs` (who/what/when/ip/ua/delta), WORM-ish by no-update policy + restricted roles.

## 7. Observability

- **Logs:** structlog JSON; fields: `request_id`, `org_id`, `invoice_id`, `task`, `stage`, `duration_ms`.
- **Metrics (Prometheus):** `invoiceiq_upload_total`, `invoiceiq_processing_duration_seconds` (histogram by stage), `invoiceiq_stp_rate`, `invoiceiq_field_conf` (histogram), `invoiceiq_llm_cost_total` (by provider/model), `invoiceiq_queue_depth`, `invoiceiq_vat_check_duration`.
- **Traces:** OpenTelemetry (API + worker), console exporter dev, OTLP to collector → Grafana Tempo (staging+).
- **Alerting:** queue depth > N for 5 min, task failure rate > 1%, VIES error rate > 10%, LLM budget > X/day.

## 8. Scale plan (100 → 100k/day)

| Volume | Shape | Moves |
|---|---|---|
| ≤100/day | single VPS, 1 worker | MVP |
| ≤10k/day | 1 VPS + GPU node (OCR/VLM) | more workers, pgBouncer, VIES proxy separate, caching tier |
| ≤100k/day | 3–5 nodes | k3s/Helm, managed PG/Redis/S3, partitioned queues (ocr/extract/validate), auto-scale on queue depth, CDN for docs |
| Millions | multi-region EU | per-country processing region, sharded queues, data-locality regions (DE/FR/…) |

Partitioned queues (P3): `ocr`, `extract_llm`, `validate`, `export` on separate prefetch counts — OCR bursts don't starve quick validations.
