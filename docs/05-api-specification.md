# 05 — API Specification

REST over HTTPS, base path `/v1`. OpenAPI 3.1 auto-generated from FastAPI (served at `/v1/openapi.json` + ReDoc). Async pattern: mutations that trigger processing return **202** + resource; progress via webhooks or polling `GET /v1/invoices/{id}`.

## 1. Conventions

- **Auth:** `Authorization: Bearer <jwt>` (user) or `X-API-Key: iiq_...` (machine). Keys scoped per `api_keys.scopes`.
- **Tenancy:** derived from token; `app.org_id` enforced server-side + RLS.
- **Errors:** envelope `{"error": {"code": "...", "message": "...", "detail": {...}, "request_id": "..."}}`. Codes: `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_ERROR`, `RATE_LIMITED`, `TOO_LARGE`, `UNSUPPORTED_FORMAT`, `INVOICE_NOT_PROCESSABLE`, `CONFLICT` (duplicate), `UPGRADE_REQUIRED`.
- **Pagination:** `?cursor=<opaque>` + `Link` header; default page 50, max 200.
- **Idempotency:** `Idempotency-Key` header honored on POST mutations (30 min window).
- **Dates:** ISO-8601 UTC. **Money:** JSON numbers (internal 4dp, display 2dp) — API returns exact numeric; UI formats.
- **Rate limits:** per org+key; headers `X-RateLimit-*`; see `docs/18`.

## 2. Auth

| Method | Path | Notes |
|---|---|---|
| POST | `/v1/auth/register` | email, password → creates user + org |
| POST | `/v1/auth/login` | → `{access_token, refresh_token}`; TOTP challenge flag |
| POST | `/v1/auth/refresh` | rotating refresh |
| POST | `/v1/auth/logout` | revoke refresh |
| POST | `/v1/auth/mfa/setup` | returns otpauth URI (P2) |
| POST | `/v1/auth/mfa/verify` | TOTP verify (P2) |
| GET | `/v1/me` | current user + orgs |
| POST | `/v1/orgs` | create org |
| GET | `/v1/orgs/{org_id}` | org + settings + plan |
| PATCH | `/v1/orgs/{org_id}` | settings: confidence_threshold, data_residency, locale |
| GET/POST | `/v1/orgs/{org_id}/members` | list / invite |
| PATCH/DELETE | `/v1/orgs/{org_id}/members/{user_id}` | role change / remove |

## 3. Invoices

### Upload (single / bulk / zip)
`POST /v1/invoices` — `multipart/form-data`, field `files[]` (1..100). Returns:

```json
202
[{"id":"<uuid>","filename":"inv.pdf","status":"queued","duplicate_of":null}]
```
- `409 CONFLICT` with `duplicate_of` if same `sha256` already exists (unless `allow_duplicate=true`).
- Limits: 20 MB/file; `pdf,png,jpeg,jpg,webp,heic,zip`; zip expanded recursively (max 100 files, depth 3).

### Query
`GET /v1/invoices?status=&supplier_id=&vat=&min_total=&max_total=&currency=&country=&lang=&from=&to=&q=&cursor=`
- `q`: full-text across invoice_number, supplier_name, description (pg_trgm/tsvector).
- Response: `{items:[InvoiceSummary], next_cursor}`.

### Detail
`GET /v1/invoices/{id}` → `InvoiceDetail` = summary + `pages[]`, `fields[]` (extraction contract), `line_items[]`, `validation[]`, `corrections[]`, `jobs[]` (status), `document_url` (presigned, 5 min).

### Review operations
| Method | Path | Effect |
|---|---|---|
| POST | `/v1/invoices/{id}/corrections` | submit field corrections `[{field,value,reason}]` → recompute validation/confidence |
| POST | `/v1/invoices/{id}/approve` | review_decision=approved, status=completed (if validations pass) |
| POST | `/v1/invoices/{id}/reject` | review_decision=rejected; optional reason |
| POST | `/v1/invoices/{id}/reprocess` | re-run pipeline from chosen stage (e.g. `ocr`) |
| DELETE | `/v1/invoices/{id}` | soft delete + storage cleanup |
| GET | `/v1/invoices/{id}/document` | presigned URL for source file |

### Export
| Method | Path | Notes |
|---|---|---|
| POST | `/v1/exports` | `{format: csv\|xlsx\|json\|xml, filters:{...}}` → 202 `{id}` |
| GET | `/v1/exports/{id}` | → `{status, url?}` presigned when ready |

## 4. Suppliers

| Method | Path | Notes |
|---|---|---|
| GET | `/v1/suppliers` | list + profile (invoice count, total, accuracy) |
| GET | `/v1/suppliers/{id}` | detail + flags |
| POST | `/v1/suppliers/{id}/flag` | mark suspicious / merge request |
| POST | `/v1/suppliers/merge` | `{keep_id, merge_id}` (P2) |

## 5. Keys, webhooks, usage

| Method | Path | Notes |
|---|---|---|
| GET/POST/DELETE | `/v1/api-keys` | create returns plaintext once (`iiq_` + 40); list shows prefix+scopes+last_used |
| GET/POST/PATCH/DELETE | `/v1/webhooks` | CRUD; `PATCH` enable/disable, rotate secret |
| POST | `/v1/webhooks/{id}/test` | send `ping` event |
| GET | `/v1/webhooks/{id}/events` | delivery log + replay |
| GET | `/v1/usage` | credits/pages consumed (period) |
| GET | `/v1/usage/breakdown` | by day, supplier, source |
| GET | `/v1/audit-logs` | admin/owner only; filters |

## 6. Webhook events (outbound)

Header `X-InvoiceIQ-Signature: t=<ts>,v1=<hmac_sha256(secret, ts.payload)>`. Retries: 3 with backoff (1 min, 10 min, 1 h), then `dead`; replay via UI/API. Idempotent by event id.

| Event | Payload highlights |
|---|---|
| `invoice.processing_completed` | `{id, status, confidence, fields:{...summary}, document_url}` |
| `invoice.requires_review` | `{id, fields:[flagged fields w/ reason]}` |
| `invoice.approved` / `invoice.rejected` | `{id, reviewed_by, decision}` |
| `invoice.exported` | `{id, format, url}` |
| `invoice.failed` | `{id, stage, error_code}` |
| `webhook.ping` | `{pong: true}` |

## 7. Invoice schema (extraction contract — JSON)

```jsonc
{
  "supplier_name": {"value":"Bosch GmbH","confidence":0.98,"method":"llm",
                    "source_text":"Bosch GmbH, Stuttgart","bbox":{"page":0,"x0":0.05,"y0":0.08,"x1":0.4,"y1":0.1},
                    "validator":{"status":"pass","rule":"mandatory_de","detail":null},"status":"accepted"},
  "vat_number":   {"value":"DE811123456","confidence":0.99,"method":"regex+VIES", ...},
  "line_items":   {"value":[{"description":"Werkzeug","quantity":2,"unit_price":49.9,
                     "net":99.8,"vat_rate":19,"vat_amount":18.96,"gross":118.76}], ...}
}
```
Complete field list in `docs/01` §5.3. Every field object carries `value, confidence, method, source_text, bbox, validator, status`.

## 8. SDK contract (P2)

- `POST /v1/invoices` upload, poll `GET`, listen webhooks — mirrored in Python + Node SDKs, generated from OpenAPI. Not in MVP.
