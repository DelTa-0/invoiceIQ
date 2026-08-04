# 09 — Enterprise Roadmap

Target: accounting firms, shared service centers, and mid-market finance teams that need isolation, e-invoicing compliance, ERP depth, and governance. Sold on **EU residency + auditability + e-invoicing**, where the US-first competitors are structurally weak.

## 1. The enterprise wedge (why we win)

1. **EU data residency as a feature** — sovereign processing, GDPR+AI Act posture (see `docs/19`), EU-hosted models by default. US competitors (Veryfi, OpenAI-backed) can't match this story.
2. **E-invoicing compliance** — Germany's E-Rechnung (B2B mandate from 2025) and France's 2026-27 mandate make **XRechnung/ZUGFeRD/Factur-X import** a compliance requirement, not a nicety. InvoiceIQ handles both classic invoices and structured e-invoices.
3. **Auditability** — per-field provenance (source text + bbox + confidence + validator), immutable audit log, correction trail. Auditors accept it; controllers trust it.
4. **Cost** — deterministic-first pipeline priced per page under Rossum by ~10×, with transparent per-page economics.

## 2. Enterprise feature map (phased)

| Capability | Phase | Notes |
|---|---|---|
| SSO (OIDC/SAML) + SCIM | P3 | Entra ID, Google, Okta; group→team mapping |
| Approved-IP / trusted environments | P3 | optional network policy |
| Multi-step approval workflows | P3 | per-amount thresholds, role gates |
| Custom fields & validation rules per org | P3 | JSON schema editing in UI |
| ERP connectors | P3 | DATEV CSV/ZUGFeRD, Lexoffice, Odoo, Xero, QuickBooks |
| E-invoice parsing | P3 | XRechnung/ZUGFeRD/Factur-X (XML), UBL/cii |
| e-invoice generation | P4 | outbound XRechnung/Factur-X for resellers |
| White-label / private cloud | P4 | dedicated cluster per enterprise |
| SLA + uptime guarantees, BAA/DPA templates | P4 | enterprise legal pack |
| Data residency regions | P4 | DE/FR dedicated regions |

## 3. Integrations architecture (designed in, built later)

- **Connector abstraction:** each integration = `{auth, schema map, sync mode (push/pull), events}` behind a registry, mirroring the LLM provider registry pattern.
- **Accounting sync:** exports become **structured journal payloads** (date, lines, tax, dimension fields) → connector maps to target (DATEV CSV columns, Xero/Xero journal API, Odoo account.move).
- **Reliability:** outbox pattern — `exports`/`webhook_events` as the outbox; connector worker consumes, marks delivered, retries with backoff, dead-letters; reconciliation by connector-side journal ID + idempotency key.
- **Scope:** DATEV first (largest German firm density), then Odoo (SMB EU), then Xero/QuickBooks, then Lexoffice (German SME SaaS), then Pennylane/Holded (FR/ES).
- **E-invoice:** parse structured XML natively (no OCR) — separate `einvoice/` module; validate against XRechnung/Factur-X schemas + business rules; merge into same `extraction_fields` contract so the rest of the platform is agnostic.

## 4. Enterprise security & governance (P3-P4)

- SCIM lifecycle sync, session policies (max lifetime, MFA enforced), device trust optional
- Field-level encryption keys per tenant (BYOK P4)
- DPA templates + data processing addenda; sub-processor list published
- Retention policies per org (configurable, audit-logged deletion)
- Pen-test + SOC2 Type II program (roadmap toward certification; contract clauses support pre-cert stage)
- Admin API for tenant management + audit export (SIEM-friendly JSONL)

## 5. Enterprise pricing shape (P3)

- Per-seat + per-page hybrid; volume discounts; dedicated region uplift; white-label premium
- Professional services: template tuning, connector builds, migration
- See `docs/23` (Round 2) for full pricing strategy.

## 6. GTM for enterprise (Round 2 detail)

Channel through accounting firms (resellers) and regional bookkeeping SaaS (OEM via API). Pilot: 3–5 firms in DE + FR each processing 1k+/mo.
