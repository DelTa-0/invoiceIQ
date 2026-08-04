# 04 — Database Schema

PostgreSQL 16. Conventions: `snake_case`, `citext` for names/VAT, `numeric(18,4)` for money internals (display rounds to 2dp), timestamptz everywhere, soft-delete via `deleted_at` where useful, **append-only** for audit. UUID PKs (v7 for time-ordered, via `pgcrypto`/app). All tenant tables carry `org_id` + a Postgres RLS policy.

## 1. Identity & tenancy

```sql
CREATE TABLE organizations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          text UNIQUE NOT NULL,
  name          text NOT NULL,
  plan          text NOT NULL DEFAULT 'free',            -- free|starter|pro|enterprise
  data_residency text NOT NULL DEFAULT 'eu_only',        -- eu_only | us_opt_in | sovereign
  confidence_threshold numeric(5,4) NOT NULL DEFAULT 0.85,
  settings      jsonb NOT NULL DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         citext UNIQUE NOT NULL,
  password_hash text,                                     -- NULL when SSO-only
  full_name     text NOT NULL,
  locale        text NOT NULL DEFAULT 'en',
  mfa_secret    text,                                     -- encrypted at rest
  mfa_enabled   boolean NOT NULL DEFAULT false,
  status        text NOT NULL DEFAULT 'active',           -- active|suspended|disabled
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE org_members (
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role          text NOT NULL DEFAULT 'member',           -- owner|admin|member|viewer
  status        text NOT NULL DEFAULT 'active',           -- active|invited|suspended
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, user_id)
);

CREATE TABLE teams (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name text NOT NULL
);
CREATE TABLE team_members (
  team_id uuid NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY (team_id, user_id)
);

CREATE TABLE invites (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email citext NOT NULL,
  role text NOT NULL DEFAULT 'member',
  token_hash text NOT NULL,
  expires_at timestamptz NOT NULL,
  created_by uuid REFERENCES users(id),
  used_at timestamptz
);
```

## 2. Suppliers & master data

```sql
CREATE TABLE suppliers (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name          text NOT NULL,
  normalized_name citext NOT NULL,                        -- for dedupe
  vat_number    text,
  country_code  char(2),
  address       jsonb,
  iban          text,                                     -- encrypted
  profile       jsonb NOT NULL DEFAULT '{}',              -- per-supplier accuracy stats
  flags         jsonb NOT NULL DEFAULT '{}',              -- suspicious flags (fraud layer)
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, normalized_name)
);
```

## 3. Documents & processing

```sql
CREATE TABLE invoices (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id         uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  supplier_id    uuid REFERENCES suppliers(id),
  object_key     text NOT NULL,                           -- storage path (org-scoped)
  sha256         char(64) NOT NULL,                       -- dedupe
  filename       text NOT NULL,
  file_size      bigint NOT NULL,
  mime_type      text NOT NULL,
  source         text NOT NULL DEFAULT 'upload',          -- upload|api|webhook|email|folder
  status         text NOT NULL DEFAULT 'queued',          -- queued|processing|requires_review|completed|failed|archived
  doc_type       text,                                    -- invoice|credit_note|proforma|other
  language       text,                                    -- de|it|fr|es|nl|en
  country        char(2),                                 -- supplier country
  currency       char(3),
  invoice_number text,
  invoice_date   date,
  due_date       date,
  supplier_name  text,
  supplier_vat   text,
  subtotal       numeric(18,4),
  total_vat      numeric(18,4),
  total          numeric(18,4),
  total_conf     numeric(5,4),                            -- document-level confidence
  review_decision text,                                   -- pending|approved|rejected
  review_by      uuid REFERENCES users(id),
  reviewed_at    timestamptz,
  source_reference text,                                  -- email subject, webhook ref...
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  deleted_at     timestamptz
);
CREATE INDEX idx_invoices_org_status ON invoices(org_id, status);
CREATE INDEX idx_invoices_org_dates ON invoices(org_id, invoice_date DESC);
CREATE INDEX idx_invoices_org_supplier ON invoices(org_id, supplier_id);
CREATE INDEX idx_invoices_org_total ON invoices(org_id, total DESC);
CREATE INDEX idx_invoices_sha ON invoices(sha256);
CREATE INDEX idx_invoices_vat ON invoices(org_id, supplier_vat);

CREATE TABLE invoice_pages (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id uuid NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  page_no    int NOT NULL,
  width      int NOT NULL, height int NOT NULL,
  text_layer boolean NOT NULL DEFAULT false,              -- digital (no OCR)
  ocr_engine text,                                        -- none|paddleocr|tesseract
  UNIQUE (invoice_id, page_no)
);

CREATE TABLE ocr_blocks (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id    uuid NOT NULL REFERENCES invoice_pages(id) ON DELETE CASCADE,
  text       text NOT NULL,
  conf       numeric(5,4) NOT NULL,
  x0 numeric, y0 numeric, x1 numeric, y1 numeric,        -- normalized 0..1
  line_no    int, reading_order int,
  table_cell boolean NOT NULL DEFAULT false,
  row_no int, col_no int
);
CREATE INDEX idx_ocr_blocks_page ON ocr_blocks(page_id);

CREATE TABLE processing_jobs (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id uuid NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  stage      text NOT NULL,                               -- ingest|ocr|classify|extract|validate|finalize
  status     text NOT NULL DEFAULT 'pending',             -- pending|running|done|failed|retrying
  attempt    int NOT NULL DEFAULT 0,
  error      text,
  payload    jsonb,
  started_at timestamptz, finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_jobs_invoice ON processing_jobs(invoice_id);

CREATE TABLE extraction_fields (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id   uuid NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  field        text NOT NULL,                             -- snake_case field key
  value        jsonb,                                     -- typed value (string/number/date/array)
  confidence   numeric(5,4),
  method       text,                                      -- rules|llm|vlm|user
  source_text  text,
  bbox         jsonb,                                     -- {page,x0,y0,x1,y1}
  validator_status text,                                  -- pass|warn|fail|null
  validator_detail jsonb,
  status       text NOT NULL DEFAULT 'accepted',          -- accepted|flagged|edited
  edited_by    uuid REFERENCES users(id),
  edited_at    timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (invoice_id, field)
);
CREATE INDEX idx_ef_invoice ON extraction_fields(invoice_id);

CREATE TABLE line_items (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id    uuid NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  position      int NOT NULL,
  description   text,
  quantity      numeric(18,4),
  unit_price    numeric(18,4),
  discount_pct  numeric(8,4),
  net           numeric(18,4),
  vat_rate      numeric(8,4),
  vat_amount    numeric(18,4),
  gross         numeric(18,4),
  sku           text,
  confidence    numeric(5,4),
  UNIQUE (invoice_id, position)
);
CREATE INDEX idx_li_invoice ON line_items(invoice_id);

CREATE TABLE validation_checks (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id   uuid NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  check_name   text NOT NULL,                             -- vat_arithmetic|vat_number|iban|total_reconcile...
  status       text NOT NULL,                             -- pass|warn|fail
  severity     text NOT NULL DEFAULT 'info',              -- info|warning|error
  reason       text,
  evidence     jsonb,                                     -- expected vs actual, source lines
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (invoice_id, check_name)
);
```

## 4. Corrections (learning loop)

```sql
CREATE TABLE corrections (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id     uuid NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  field          text NOT NULL,
  old_value      jsonb,
  new_value      jsonb NOT NULL,
  context        jsonb NOT NULL DEFAULT '{}',             -- doc_type, supplier, country, language
  reason         text,
  created_by     uuid REFERENCES users(id),
  created_at     timestamptz NOT NULL DEFAULT now(),
  applied        boolean NOT NULL DEFAULT true,           -- whether re-extraction adopted it
  eval_candidate boolean NOT NULL DEFAULT false           -- queued for eval set promotion
);
CREATE INDEX idx_corrections_ctx ON corrections((context->>'supplier'));
```

## 5. API, webhooks, usage, billing

```sql
CREATE TABLE api_keys (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name        text NOT NULL,
  key_hash    char(64) NOT NULL,                          -- sha256 of secret
  key_prefix  text NOT NULL,                              -- 'iiq_' + 8
  scopes      text[] NOT NULL DEFAULT '{invoices.read,invoices.write,exports.write}',
  last_used_at timestamptz,
  created_by  uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  revoked_at  timestamptz
);

CREATE TABLE webhooks (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  url         text NOT NULL,
  secret      text NOT NULL,                              -- HMAC secret (encrypted)
  events      text[] NOT NULL,
  enabled     boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE webhook_events (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  webhook_id   uuid NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
  event        text NOT NULL,
  payload      jsonb NOT NULL,
  signature    text NOT NULL,
  status       text NOT NULL DEFAULT 'pending',           -- pending|delivered|failed|dead
  attempts     int NOT NULL DEFAULT 0,
  next_attempt timestamptz,
  last_error   text,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_we_status ON webhook_events(webhook_id, status);

CREATE TABLE exports (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  format       text NOT NULL,                             -- csv|xlsx|json|xml
  filters      jsonb,
  object_key   text,
  status       text NOT NULL DEFAULT 'queued',            -- queued|processing|ready|failed
  created_by   uuid REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE usage_events (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  event_type text NOT NULL,                               -- page_processed|llm_call|export|api_call
  quantity   int NOT NULL DEFAULT 1,
  meta       jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_usage_org_time ON usage_events(org_id, occurred_at);

CREATE TABLE subscriptions (
  org_id          uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  provider        text NOT NULL DEFAULT 'stripe',
  provider_id     text,
  plan            text NOT NULL,
  status          text NOT NULL,                          -- trialing|active|past_due|canceled
  current_period_end timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE plans (
  id         text PRIMARY KEY,                            -- free|starter|pro|enterprise
  pages_month int NOT NULL,
  price_eur  numeric(10,2) NOT NULL,
  features   jsonb NOT NULL DEFAULT '{}'
);
```

## 6. Audit & system

```sql
CREATE TABLE audit_logs (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  org_id     uuid NOT NULL,
  actor_type text NOT NULL,                               -- user|api_key|system
  actor_id   uuid,
  action     text NOT NULL,                               -- invoice.approved|member.invited|key.created...
  resource   text NOT NULL,                               -- invoice, member, key, export...
  resource_id text,
  delta      jsonb,
  ip         inet, user_agent text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_org_time ON audit_logs(org_id, created_at DESC);
-- No UPDATE/DELETE on audit_logs: trigger blocks any modification.

CREATE TABLE org_settings (
  org_id    uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  settings  jsonb NOT NULL DEFAULT '{}',
  updated_by uuid,
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

## 7. RLS policies (per tenant table)

```sql
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON invoices
  USING (org_id = current_setting('app.org_id')::uuid);
-- Same pattern: suppliers, extraction_fields, line_items, validation_checks,
-- corrections, exports, usage_events, webhooks, api_keys, org_members, org_settings.
-- audits visible to owner/admin only (policy on role).
```
API sets `SET app.org_id = <ctx>` per request after JWT/API-key auth. Workers set it from the invoice's org. `auth.uid` alternative is the Supabase model; here `app.org_id` is simplest for mixed actor types.

## 8. Migration & seed notes

- Alembic; one migration per feature branch; squash after GA.
- Seeds: `plans`, ISO currency/language/country tables, tax-rate profiles (see `docs/15`).
- `numeric(18,4)` everywhere; money display rounding is presentation-layer only — this kills float drift in reconciliation tests.
- Encryption: `suppliers.iban`, `users.mfa_secret`, `webhooks.secret` encrypted with app-level AES-256-GCM key from env (`ENCRYPTION_KEY`); never stored plaintext.
