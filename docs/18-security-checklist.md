# 18 — Security Checklist

Baseline: **OWASP ASVS Level 1** for MVP, Level 2 by P3. Threat model: multi-tenant invoice data (PII + financial), LLM as untrusted-input processor, API-first exposure.

## 1. Authentication & sessions
- [x] Passwords: argon2id (pwdlib), min 10 chars, breach-list check (P2), no storage of plaintext.
- [x] JWT access 15 min + rotating refresh 30d; refresh reuse detection (revoke family); Redis deny-list on logout.
- [x] MFA (TOTP) P2; enforced for owner/admin by P3.
- [ ] SSO OIDC/SAML + SCIM (P3).
- [ ] Brute-force: per-account + per-IP rate limits on /auth/*, lockout w/ exponential backoff.
- [ ] Session binding to user-agent/ip fingerprint (P2), device list + revoke.

## 2. Authorization & tenancy
- [x] RBAC roles: owner/admin/member/viewer; matrix enforced in `deps.py` + route guards.
- [x] Postgres RLS on every tenant table; `app.org_id` set from token; RLS property tests.
- [x] API keys: `sha256` hash stored, prefix `iiq_`, scopes, rotation, revocation, last-used audit.
- [ ] Row-level field permissions (accountant sees IBAN; viewer sees masked) — P2.
- [ ] Idempotency keys prevent double-mutation; `Idempotency-Key` validated.

## 3. Transport & storage
- [x] TLS 1.2+ everywhere (Caddy auto-HTTPS); HSTS; internal network between services.
- [x] At-rest: disk encryption (LUKS/SOPS), app-level AES-256-GCM for `suppliers.iban`, `users.mfa_secret`, `webhooks.secret`, API key material.
- [x] Presigned URLs (5 min TTL), path includes org+invoice; every access audit-logged.
- [x] Upload validation: size/type/sha; PDF sanitization (no JS/attachments via pdfplumber render path); malware scan ClamAV (P2); image bombs rejected (dimension + decompression limits).
- [ ] Object lifecycle: orphan cleanup job, retention policy enforcement (P2 UI).

## 4. Application security
- [x] Input validation: Pydantic strict schemas; JSONB writes schema-validated; no SQL injection (SQLAlchemy params); no `eval`/pickle on untrusted input.
- [x] LLM untrusted input: prompt-injection mitigations (`docs/13` s6); no tool/OS access from doc text; output always schema-validated.
- [x] CSRF: same-site cookies (Next.js BFF), no state-changing GET; CORS locked to app origin.
- [x] Rate limits: slowapi Redis-backed per-route (auth, upload, export, webhook delivery); headers exposed.
- [x] SSRF: outbound webhook URLs blocked against internal ranges (metadata 169.254.169.254, loopback, link-local); webhook secret never echoed.
- [x] Dependency scanning (pip-audit + npm audit in CI); container scanning (trivy) in CI.
- [x] Error handling: no stack traces to clients; generic messages; structured error codes + `request_id`.

## 5. Logging, monitoring, incident response
- [x] `audit_logs` append-only (trigger blocks UPDATE/DELETE; restricted roles; owner/admin read).
- [x] Structured logs (request_id/org_id/invoice_id), Sentry with PII scrubbing.
- [x] Metrics for security: auth-fail rate, 4xx bursts, webhook failure, RLS-mismatch alerts.
- [ ] Incident response runbook: detection -> containment (revoke keys/suspend org) -> notification (GDPR 72h if personal data breach) -> postmortem. Draft by P2 GA.

## 6. Data protection & privacy controls (see also `docs/19`)
- [x] EU-only storage/processing default; per-org `data_residency` policy enforced at LLM routing + region.
- [x] Data export/deletion API (GDPR rights) — implement P1, UI P2.
- [x] Retention: configurable per org; default accounting-aligned (10y documents, configurable) with audit-logged deletion.
- [x] Sub-processor list maintained; DPAs signed; processing records (Art. 30).

## 7. Secrets & infra
- [x] Secrets in env/secret store, never repo; `.env` gitignored; CI GH secrets.
- [x] Minimal image surface; non-root containers; read-only root FS where feasible; no debug endpoints in prod.
- [x] Regular patching cadence (unattended-upgrades, image rebuilds monthly); backup restore drills.

## 8. Compliance program (P3/P4)
- [ ] SOC 2 Type II roadmap, ISO 27001 later; pentest before P3 GA; bug bounty optional.
- [ ] Vendor risk: LLM/OCR providers' EU residency + retention clauses verified and documented.

## Ownership & cadence
Sole founder owns security; checklist re-reviewed at each phase exit; items marked P2/P3 are gated to those phases but designed in now.
