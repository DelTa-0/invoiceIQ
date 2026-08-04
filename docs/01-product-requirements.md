# 01 — Product Requirements Document (PRD)

## 1. Product summary

InvoiceIQ is a European, GDPR-first, AI accounts-payable platform. It converts supplier invoices — scanned PDF, digital PDF, image, mobile photo, email attachment — into validated, accounting-ready structured data with per-field confidence, a human review surface, and a full audit trail. It extracts, validates, flags inconsistencies, and learns from corrections. It is an AI employee for accounts payable, not a text extractor.

## 2. Problem statement

European SMEs manually re-key supplier invoices into accounting software (DATEV, Lexoffice, Odoo, Xero…). Each invoice costs $12–20 in labor + error correction. Incumbent automation is either enterprise-priced (Rossum $18k+/yr) or extraction-only with no validation/fraud/review (Mindee), or US-first (Veryfi). InvoiceIQ targets the underserved middle: SMEs, agencies, logistics, manufacturing, retail, and accounting firms/bureaus.

## 3. Target users

- **Primary:** SMEs, agencies, logistics, manufacturing, retail, accounting firms, bookkeepers
- **Countries:** DE, IT, FR, ES, NL, BE, AT first; EU-wide later
- **Personas:** Office manager (uploads, reviews), accountant/bookkeeper (approves, exports, integrates), finance lead (monitors VAT, fraud, spend), IT/admin (API keys, webhooks, SSO, org config)
- **Non-goals (MVP):** outgoing invoices, payroll, e-invoicing issuance, payment execution

## 4. Core jobs to be done

1. "Get invoice data into my accounting system without typing it."
2. "Be confident the numbers are right before I pay or post."
3. "Find a specific invoice or supplier quickly."
4. "Know what my AI got wrong and fix it so it stops being wrong."
5. "Prove to auditors/regulators what was processed and by whom."
6. "Stay GDPR-compliant and EU-resident without thinking about it."

## 5. Feature requirements (MVP boundary)

### 5.1 Upload (MVP)
- Single/multi file upload, drag-and-drop, bulk, ZIP (flat + nested), web, REST API (`multipart`), webhook-received files
- Formats: PDF, PNG, JPEG, WEBP, HEIC→JPEG; limits: 20 MB/file, 100 files/batch
- De-duplication at ingest (file SHA-256)
- Async: upload → `202 Accepted` → processing events via webhook/WS

**Post-MVP:** email ingest (forward-to-address), folder monitoring (SMB/Drive/SFTP), mobile SDK

### 5.2 OCR & ingestion (MVP)
- Digital PDFs: native text extraction (≈€0)
- Scanned/low-quality/rotated: PaddleOCR PP-OCRv4 + PP-Structure (deskew, auto-orientation, table recognition, multi-page)
- Tesseract fallback for rare languages; handwriting = best-effort, low confidence
- Output: normalized page model — blocks with text, bbox, confidence, reading order, table structure

### 5.3 Extraction (MVP)
Header fields: supplier name/address, VAT number, tax ID, invoice number, invoice date, due date, currency, PO number, customer/buyer, IBAN, BIC, bank name, payment terms, payment method, invoice language, country, invoice type, document notes.
Line items: description, quantity, unit price, discount, tax %, VAT amount, subtotal, shipping, other charges, total.
**Extraction contract:** every field carries value + confidence + source text + bbox + method + validator status (see `docs/12`).

### 5.4 VAT intelligence (MVP)
- Per-country tax profiles: DE MwSt 19/7, IT IVA 22/10/5/4, FR TVA 20/10/5.5/2.1, ES IVA 21/10/4, NL BTW 21/9, BE BTW 21/12/6, AT USt 20/10/13
- Modes: reverse charge, intra-community, zero-rated, reduced rates, mixed/multi-rate
- Arithmetic reconciliation: Σline ± discount ± shipping = subtotal; Σ VAT; subtotal + VAT = total; per-line `qty × unit × (1−disc) × rate` rounding rules (round-half-up to 2dp)
- **Mismatches highlighted with per-check detail** (expected vs actual, delta, source lines)

### 5.5 Validation engine (MVP)
Deterministic, rule-based, per-field and cross-field (see `docs/15`):
- VAT number: format per country + **VIES** check (cached; EC service is rate-limited) + reverse-charge flags
- IBAN: structure, length, MOD-97 checksum; BIC format
- Dates: multi-format parsers, sanity (not future, not absurd); due ≥ invoice date
- Currency: ISO 4217; numbers: decimal/comma locales
- Mandatory fields per jurisdiction (e.g., DE §14 UStG: supplier name+address+VAT, invoice number, date, line description, amounts)
- Every check emits `{status: pass|warn|fail, rule, reason, evidence}`

### 5.6 Confidence system (MVP)
- Per-field 0–1 composite score + reason codes (see `docs/12` §Confidence)
- Org-configurable threshold; fields below threshold → invoice status `requires_review`
- Document-level confidence = weighted min/mean → status: `completed` | `requires_review`

### 5.7 Human review (MVP)
- Split view: rendered document + field editor
- Click field → highlight source bbox on document page; show OCR snippet + confidence + validation issues
- Approve all / edit / reject; keyboard-first; bulk approve
- Every correction persisted (learning loop + audit)

### 5.8 Export (MVP)
- CSV, XLSX, JSON, XML; async; signed-download URL; audit logged
- Formats tailored per accounting target (DATEV CSV column map is post-MVP)

### 5.9 API & webhooks (MVP)
- REST `/v1` (OpenAPI 3.1), API keys (hashed), rate limits, idempotency
- Webhooks: `invoice.processing_completed`, `invoice.requires_review`, `invoice.approved`, `invoice.rejected`, `invoice.exported`; HMAC-signed, retry w/ backoff, event log + replay
- SDKs (Python, Node, JS) post-MVP

### 5.10 Tenancy & auth (MVP)
- Orgs, teams, invitations, RBAC (owner/admin/member/viewer), RLS isolation
- Email+password, TOTP MFA (post-MVP hardening), JWT access + refresh
- SSO/OIDC, SCIM: enterprise (P3)

### 5.11 Post-MVP modules (defined now, built later)
Duplicates & near-duplicate detection, fraud scoring (tampering, IBAN change, velocity), email ingest, folder monitoring, workflow rules builder, NL search, AI chat, analytics, ERP connectors, e-invoicing (XRechnung/ZUGFeRD/Factur-X), billing (Stripe), usage credits.

## 6. Non-functional requirements

- **Availability:** 99.5% target; async so uploads never fail on transient AI errors
- **Throughput:** 100/day at launch → 10k/day by end of year; design for 100k/day (see `docs/03` §Scale)
- **Latency:** P95 processing ≤ 30 s for digital PDFs, ≤ 2 min for scanned single-page
- **Data residency:** default EU storage + processing (GDPR §§44–49); per-tenant policy
- **Security:** OWASP ASVS Level 1 baseline; encryption in transit/at rest; signed URLs; audit logs (see `docs/18`)
- **Cost envelope:** target **$0.03–0.10 all-in cost per invoice** at 10k/day (deterministic-first pipeline) to preserve SME margin
- **Localization:** UI in EN initially; DE/FR/IT/ES/NL ship in P2. Extraction is language-agnostic from day 1 (DE/IT/FR/ES/NL/EN).

## 7. Success metrics

- STP (straight-through processing) rate: extraction-complete without review ≥ 75% by P1 exit
- Field-level F1 on golden set ≥ 0.95 header / ≥ 0.90 line items
- VAT/total mismatch recall: ≥ 95% on seeded-error golden set
- Review time per invoice ≤ 60 s P50; correction rate decline ≥ 10%/month per supplier (learning loop)
- Paid activation: ≥ 30% trial→paid; NRR ≥ 110% within 2 quarters

## 8. Monetization sketch (engineering implications only)

- Credits = pages processed; plans Free (50/mo)/Starter €49 (1k)/Pro €199 (10k)/Enterprise custom
- API usage metered separately; usage metering tables designed now (`usage_events`)
- **Engineering note:** `usage_events`, `subscriptions`, `plans` exist in schema now; Stripe lands P2

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucination on financial data | Grounded extraction (source+bBox mandatory), deterministic-first, validation gate |
| EU LLM accuracy gap vs US | Provider registry + opt-in policy; local VLM path; eval harness measures gap (see `docs/16`) |
| OCR quality on poor scans | PaddleOCR + preprocessing + VLM escalation path |
| VIES availability/rate limits | Cache with TTL + stale-while-revalidate; degrade to format-only validation |
| Solo-founder bus factor | Docs package, monorepo, CI, golden datasets, Makefile-first ops |
| Cost blowout at scale | Digital-PDF-skip-OCR, token budget, per-invoice cost telemetry |
