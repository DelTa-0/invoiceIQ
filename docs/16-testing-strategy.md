# 16 — Testing Strategy

Three concentric layers: **unit (fast, deterministic) → integration (real PG/Redis/OCR, nightly-able) → eval (accuracy, the product's truth)**. Plus E2E UI and load. The eval harness is the compass: if it's green, features ship; if it's red, nothing does.

## 1. Unit tests (pytest, milliseconds)

| Module | Coverage |
|---|---|
| `validate/arithmetic.py` | rounding matrix (round-half-up 2dp, cents), multi-rate sums, RC/zero-rated, tolerance edges, all 7 rules |
| `validate/vat.py` | per-country format+checksum (DE/IT/FR/ES/NL/BE/AT), VIES adapter (mocked: valid/invalid/timeout), RC detection phrases (de/it/fr/es/nl/en) |
| `validate/iban.py` | MOD-97 across EU country-lengths, BIC pattern, edge inputs |
| `validate/dates.py` | locale format matrix, ambiguous dates, sanity bounds |
| `confidence/engine.py` | composite math, weights per class, threshold boundary, reason codes |
| `extract/rules/*` | regex extractors: VAT, invoice numbers (many formats), locale numbers (1.234,56 vs 1,234.56), dates |
| `extract/merge.py` | precedence, rule-vs-LLM conflict, missing mandatory, method tagging |
| `llm/registry.py` | routing by policy (eu_only/us_opt_in/sovereign), fallback chain, token budget |
| `ingest/*` | zip flatten+limit, HEIC convert, dedupe sha256, size/type guards |
| `db/` | model constraints, RLS policy matrix (org A cannot read org B — property test over all tenant tables) |
| `webhooks/` | HMAC signature (tamper detection), retry/backoff schedule, replay idempotency |

Property-based (hypothesis): IBAN generators, VAT checksums, arithmetic over random decimals.

## 2. Integration tests (real PG + Redis, no mocks where it matters)

- API lifecycle: upload (multi/zip) -> 202 -> poll -> completed (against `make dev`-style stack via testcontainers or compose profile `ci`).
- Auth: register/login/refresh/logout, org switch, RBAC matrix (owner/admin/member/viewer on every route).
- Webhooks: delivery, HMAC, retry on 500, dead-letter, replay.
- Exports: CSV/XLSX/JSON/XML builders vs golden file byte-compare; presigned URL flow.
- Audit: every mutating action writes `audit_logs`; append-only trigger blocks UPDATE/DELETE.
- Usage metering: page_processed events counted correctly incl. retries (no double-count).

## 3. Eval harness (accuracy truth)

**Golden set** (`tests/golden/invoices.jsonl` + files): labeled ground truth, stratified:
- By country/language: DE/IT/FR/ES/NL/BE/AT + EN (>= 40 each at MVP, >= 300 total)
- By source: digital, scanned, photo, rotated, low-DPI, fax, handwriting-annotated
- By layout: single-page, multi-page, multi-rate, RC, credit note, proforma, non-invoice

**Seeded-error set** (`tests/golden/errors.jsonl`): correct docs mutated to inject the failure classes from `docs/15` s8.

**Harness** (`tests/eval/run.py`):
1. Run pipeline over golden + error sets (provider-agnostic, pinned model/prompt versions).
2. Compute per-field: precision, recall, F1, exact-match rate; document-level STP rate.
3. Report matrix: by country, language, source class, doc_type; money-field error severity (wrong total = critical).
4. Regressions: compare to committed baseline JSON; any F1 drop > 0.5pt or money-field regressions -> `eval.yml` fails + GitHub issue.
5. Emit `eval/reports/<date>.json` for the record.

**Gate policy:** any prompt/model/OCR-engine/rule change runs eval before merge (CI manual gate or on-change job). Dashboard charts the F1 trends.

## 4. E2E (Playwright, `apps/web`)

- Auth flows, upload + queue UI, review (click field -> highlight -> edit -> approve), exports download, settings (keys/webhooks), dark/light, empty/error states, keyboard shortcuts.
- Runs against staging build; seeded fixtures; CI nightly.

## 5. Load (locust)

- Scenarios: concurrent uploads (10/50/100), review actions, export bursts, webhook storms.
- Assert: P95 processing latency, queue depth, no error-rate cliff; validate target 10k/day with 2 workers before P2 GA.
- Report cost: `cost/invoice` per scenario.

## 6. Golden fixture generation

`scripts/gen_fixtures.py`: template-based synthetic invoices (Jinja2 -> HTML -> PDF via weasyprint, or fpdf) parameterized over country/language/layout/variant, plus deterministic "mutation" for error set. Real anonymized invoices are P2 (partner-sourced, labeled).

## 7. CI wiring

```
ci.yml: ruff → pyright → pytest(unit) → pytest(integration, compose) → build images → eval(gate) → (nightly) e2e + load
```
Speed: unit in CI always; integration + eval on merge-to-main and nightly; e2e/load nightly.

## 8. Test hygiene rules
- No sleeps/retry-loops in tests (inject fakes for LLM/VIES/time).
- LLM calls mocked at unit level; eval is the only place real calls happen (cost-budgeted, pinned versions).
- Each golden invoice has a fixture file + label row; naming `<country>-<layout>-<variant>.pdf`.
- Seed data idempotent; tests never mutate real tenant data.
