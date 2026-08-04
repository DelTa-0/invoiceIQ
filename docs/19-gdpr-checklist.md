# 19 — GDPR Checklist

InvoiceIQ is a **data processor** for customers (controllers). Data processed: personal data within invoices (names, addresses, VAT/IDs, IBANs, emails) + account data. Applicable alongside the **EU AI Act** (fully applicable 2026-08-02). This checklist is the compliance contract, not just a feature list.

## 1. Roles & legal basis
- [x] Processor for customer invoice data (DPA in place, processor obligations Art. 28).
- [x] Controller for our own account data; lawful basis: contract + legitimate interest (documented).
- [x] Data Processing Agreement template published; SCCs where sub-processors transfer (avoided by EU-only default).
- [x] Article 30 records of processing activities (RoPA) maintained.

## 2. Data minimization & purpose
- [x] We extract invoice fields for the stated purpose (AP automation) and nothing more; no advertising-derived uses.
- [x] Optional fields not silently collected; data retention configurable (default aligns with statutory accounting retention, e.g. 10y DE/IT/FR, configurable down).
- [x] Pseudonymization option: supplier/customer personal-data fields masked in exports (P2 toggle).

## 3. Data subject rights (Art. 15-22)
- [ ] Right of access: export all data of a data subject (P1 API + UI).
- [ ] Right of erasure: delete documents + extractions + derived corrections; supplier profile anonymized (P1).
- [ ] Right to rectification: correction UI is the mechanism; propagate on request.
- [ ] Right to object / restriction / portability: documented process + export (P2).
- [ ] Automated decision-making (Art. 22): InvoiceIQ is assistive — no fully-automated decisions with legal effects; human review is built-in (`requires_review`). Documented in transparency notice.

## 4. Transparency (Art. 13/14 + AI Act)
- [x] Privacy notice + AI transparency notice published (auto-classification, confidence, human-in-the-loop).
- [ ] AI Act: transparency statement that AI processes documents; minimal-risk classification documented; human oversight for high-value determinations documented.
- [ ] No AI training on customer data without explicit opt-in consent (default: tenant-scoped few-shot only, no cross-tenant training).

## 5. Security of processing (Art. 32)
- [x] Encryption in transit (TLS) and at rest (disk + app-level for sensitive fields); pseudonymization where feasible.
- [x] Access controls: RBAC + RLS; least privilege; audit logs of access to documents/exports.
- [x] Resilience: backups + restore drills; incident detection + response runbook.
- [x] Regular testing of security measures (pen-test cadence P3).

## 6. Breach notification (Art. 33/34)
- [ ] Runbook: detect -> assess severity -> notify DPA within 72h -> notify data subjects where high risk -> document. Drafted P1, drilled P2.

## 7. International transfers (Art. 44-49, Schrems II)
- [x] **Default: EU-only.** Storage (PG/object) in EU region; default LLM = EU-hosted (Mistral EU).
- [x] US LLM (OpenAI/Claude/Gemini) is per-tenant **opt-in** with explicit consent + DPA + no-retention config; tenant setting `data_residency` enforced at routing.
- [x] Sub-processor list published; any transfer justified by adequacy/SCCs + documented.

## 8. Data residency & regional deployment
- [x] Region selection = tenant residency region (MVP: single EU region; P4: per-country regions).
- [x] Verified no incidental transfers (no US analytics SDKs; Sentry DPA/EU region or self-hosted; telemetry scrubbed of invoice content).

## 9. Accountability & DPIA
- [x] Data Protection Impact Assessment (DPIA) drafted before GA — invoice processing is not per se high-risk, but automated decision-support + LLM warrant one; Art. 35 documented.
- [ ] Records of processing, DPA registry, vendor assessments maintained as code/docs in `docs/compliance/`.
- [ ] AI Act FRIA (fundamental rights impact assessment) — minimal-risk class; document reasoning.

## 10. Consent & children
- [x] No minors' data expected; invoices are B2B; still, no consent needed for processing (legal basis = contract) — recorded.

## 11. Data protection by design/default (Art. 25)
- [x] Privacy defaults: EU-only, minimal fields, retention configurable, no cross-tenant AI training.
- [x] PII minimization in logs: log sanitizer strips IBAN/VAT/names from structured logs; Sentry scrubbing on.

## 12. Processor-vendor chain (OCR/LLM providers)
- [x] Mistral EU: DPA, EU processing, no training on data (verified contract terms).
- [x] PaddleOCR: self-hosted (no data leaves our VPS) — the strongest residency story.
- [ ] Re-verify provider terms each contract renewal; maintain sub-processor register.

## Compliance artifacts to produce (Round 2/legal)
- ToS, Privacy Policy, DPA, AI Transparency Notice, RoPA, DPIA, Sub-processor register, Breach runbook, Retention policy table.
- DPA template supports "EU data only" and "US opt-in allowed" tenant modes.
