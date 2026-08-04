# 15 — Validation Rules

Deterministic, unit-tested, language- and layout-agnostic. The LLM proposes; this engine disposes. Every check returns `{status: pass|warn|fail, severity: info|warning|error, reason, evidence}` and writes a `validation_checks` row.

## 1. Arithmetic reconciliation (the heart)

Money stored as `numeric(18,4)`; display rounds to 2dp; all checks use **round-half-up** to 2dp (EU business convention) unless evidence of banker's rounding.

Rules:
1. **Line net:** `net = round2(qty * unit * (1 - disc_pct/100))`. Validate per line.
2. **Line VAT:** `vat = round2(net * rate/100)`.
3. **Line gross:** `gross = round2(net + vat)` (only if printed; else computed).
4. **Subtotal:** `sum(net(line)) == subtotal` (tolerance +-0.01 for supplier rounding).
5. **VAT total:** `sum(vat(line)) == total_vat` (tolerance +-0.02 for multi-rate invoices).
6. **Grand total:** `subtotal + total_vat + shipping + other == total` (tolerance +-0.02).
7. **Reverse charge / zero-rated:** if any line rate=0 with RC marker then VAT must be 0 and no VAT line expected.

Every mismatch: `fail` + evidence `{expected, actual, delta, source_lines: [...]}`. UI shows expected-vs-actual inline. **Never auto-correct** — flag for review (a real supplier can legitimately round oddly; humans decide).

Tolerance rationale: suppliers print rounded 2dp totals from their ERP; tiny deltas (<=0.02) are rounding artifacts, larger ones are errors or tampering.

## 2. VAT number validation (per country)

| Country | Pattern (standard) | Notes |
|---|---|---|
| DE | `DE` + 9 digits | checksum via `stdnum.de.idnr` |
| IT | `IT` + 11 digits | no checksum but national DB optional |
| FR | `FR` + 11 chars (2 letters + 9 digits, or 10 digits + letter) | modulo 11 checksum |
| ES | `ES` + 9 (letter/number mix by entity type) | checksummed |
| NL | `NL` + 9 digits + `B` + 2 digits | format only |
| BE | `BE` + 10 digits | mod-97 |
| AT | `AT` + `U` + 8 digits | mod-97 |

- **VIES check** (official EC web service) via cached proxy: 24h TTL cache keyed by `vat+supplier_name`; stale-while-revalidate. Response: `valid | invalid | not_registered | timeout`.
- VIES down -> degrade to format-only + `warn` (`VIES_UNAVAILABLE`).
- **Mode recognition** (from text + extraction): reverse charge / intra-community / zero-rated. If RC marker present, VAT=0 expected; conflicting VAT -> `fail`.

## 3. IBAN / BIC

- IBAN: country-specific length + structure + **MOD-97** checksum (modulo per EU standard). Reject/flag on checksum failure.
- BIC: 8 or 11 chars, `AAAA BB CC [DDD]` pattern.
- Cross-field: IBAN country approx supplier country else `warn`.
- `schwifty`/`stdnum` for structure; custom mod-97 always double-checked by tests.

## 4. Dates & currency

- Date parse: dd.mm.yyyy, mm/dd/yyyy (locale-aware after language detect), ISO, EU long forms; ambiguous dates -> `warn`.
- Sanity: invoice_date not in future (+14d grace), due_date >= invoice_date (or missing allowed), invoice_date within +-10y.
- Currency: ISO 4217 3-letter; unknown -> `warn`; currency code vs symbol/euro mismatch -> `warn`.

## 5. Mandatory-field compliance (per jurisdiction)

| Jurisdiction | Required (selection) |
|---|---|
| DE (s14 UStG) | supplier name+address, supplier VAT, invoice number, invoice date, description of supply, qty/extent, net, rate, VAT amount, total |
| IT (DPR 633/72) | supplier data, invoice number, date, description, base amount, VAT, total, customer VAT when B2B |
| FR (CGI art. 242 nonies) | similar + supplier tax number |
| NL / BE / ES / AT | analogous EEC 2006/112 basics |

Missing mandatory -> `fail` severity=warning (flagged for the accountant, not auto-blocking; micro-suppliers legitimately omit some fields — the accountant decides).

## 6. Cross-field consistency

- Invoice number format vs supplier history (known supplier pattern; anomaly -> `warn`).
- Currency consistency across line items, VAT %, and header.
- Due date plausibility vs payment terms (`Net 30` -> due approx inv+30; gross mismatch -> `warn`).
- Duplicate candidate: same `supplier+number` (or near: same supplier+date+total) already in org -> `warn` + `DUPLICATE_CANDIDATE` (full module P2; check seeded now).

## 7. Rule engine architecture

```
validate/engine.py: run_all(invoice, extraction) -> list[Check]
  rules/:
    arithmetic.py   -- the 7 rules above
    vat.py          -- format, VIES, mode
    iban.py, dates.py, currency.py, mandatory.py, consistency.py
```

- Rules are pure functions: `(invoice, extraction) -> Check`. Zero I/O inside rules (VIES I/O lives in the proxy, injected).
- Deterministic ordering; idempotent; safe to re-run on every correction.
- New jurisdiction = new profile dict + tests, not new code.

## 8. Seeded-error golden set (eval)

`tests/golden/errors.jsonl`: correct invoices mutated to inject (a) arithmetic drift, (b) VAT checksum failure, (c) IBAN mod-97 break, (d) swapped totals, (e) missing mandatory field. Recall target >= 95%.

## 9. Threshold & status wiring

- Any `fail` on money/VAT/IBAN -> field `validator_status=fail` -> confidence floor -> `requires_review`.
- `warn` counts against confidence but does not force review alone.
- Check severity drives UI grouping (errors red, warnings amber, info gray) and later workflow rules (P3).
