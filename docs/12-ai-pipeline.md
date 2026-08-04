# 12 — AI Pipeline

## 1. End-to-end pipeline

```
 upload → ingest → route → ocr → classify → extract → validate → confidence → finalize → review → export
```

| Stage | Input → Output | Engine | Failure mode → action |
|---|---|---|---|
| ingest | file → normalized pages + page objects | pypdf/pdfplumber/PyMuPDF, pillow-heif, zipfile | corrupt → `failed(ingest)` |
| route | pages → text-layer? | text density heuristic (words/page, chars/block) | low density → OCR path |
| ocr | raster → page blocks (text+bbox+conf+table) | PaddleOCR PP-OCRv4 + PP-Structure; Tesseract fallback | empty output → `OCR_NO_TEXT` → VLM escalation |
| classify | page text → doc_type | rules + LLM (3-way) | → `other`, flag review |
| extract | doc model → field candidates | rules-first → LLM → VLM → merge | low conf → `requires_review` |
| validate | candidates → checks | deterministic engine | fail → flag field, do NOT auto-fix |
| confidence | candidates+checks → per-field + doc score | composite engine | below threshold → `requires_review` |
| finalize | scores → status + events | state machine | → webhooks |
| review | human edits → corrected contract | UI + corrections store | feeds learning loop |
| export | contract → file | builders | → presigned URL |

## 2. Extraction strategy (deterministic-first)

**Precedence per field:**
1. **Rules** — VAT format per country, IBAN mod-97, invoice-number patterns, ISO dates, locale numbers. Deterministic, free, auditable. Used when regex confidence ≥ high threshold.
2. **LLM** — residual/ambiguous fields (supplier name, payment terms, line description, notes). Grounded: must return `source_text` + `bbox`. JSON-schema constrained output.
3. **VLM** — escalation when OCR char confidence is low (scan quality, handwriting, complex tables) or page has no text layer and classification is uncertain. Multimodal provider per org policy (default EU-hosted; local Qwen2.5-VL on GPU node for sovereign tenants).
4. **Cross-field reconciliation** — totals recomputed independently; validator output overrides raw extraction; mismatches never silently accepted.

**Merge rules (`extract/merge.py`):**
- If rule and LLM agree → accept, confidence boosted by agreement.
- If disagree → prefer rule for well-formed fields (VAT/IBAN/numbers/dates); flag the loser as `warn` with both candidates in evidence.
- Missing mandatory field → mark `requires_review` with reason `MISSING_MANDATORY`.
- Every merged field carries `method` = last effective source (rules|llm|vlm|user).

## 3. Document model (the contract between stages)

```jsonc
{
  "doc_type": "invoice",
  "language": "de",                    // detected (fastText/langid + LLM confirm)
  "country": "DE",
  "pages": [
    {"page_no": 0, "blocks": [
      {"text":"USt-IdNr.: DE811123456", "conf":0.98,
       "bbox":[0.6,0.2,0.8,0.22], "line_no":3, "reading_order":4,
       "role":"key_value", "label":"vat_number"}
    ]}
  ],
  "tables": [{"page_no":0, "rows":[{"cells":[{"text":"Werkzeug","bbox":[...]}, ...]}], "conf":0.9}]
}
```
Block labeling (`key_value`, `amount`, `date`, `company`, `address`, `table`) comes from PP-Structure layout + light rules; it primes the LLM and gives the review UI its highlights.

## 4. Cost control (LLM-light design)

| Invoice class | OCR | LLM | VLM | est. cost |
|---|---|---|---|---|
| Digital PDF | skip | extract (2–4k tok) | never | ~€0.002–0.01 |
| Clean scan | PaddleOCR CPU | extract | never | ~€0.01–0.02 |
| Poor scan/photo | PaddleOCR CPU | extract + page re-OCR w/ VLM if conf low | escalated | ~€0.03–0.08 |
| Handwritten/rotated | OCR best-effort | — | VLM primary | ~€0.05–0.15 |

- **Token budget** per invoice (extract prompt); line items batched in one call, not per line.
- **Skip LLM entirely** when rules cover 100% of fields with high confidence (common for repetitive suppliers) — triggers learning-loop "trusted supplier" flag.
- **Retry-with-fix:** on JSON schema failure, append the validation error and retry once (no free-form re-prompt loops).
- **Cache:** extraction cache keyed by `sha256 + model_version` (only for identical re-processing; never cross-tenant).

## 5. Confidence engine

`field_confidence` is a **weighted composite**, never a raw model score:

```
conf = w1·method_conf + w2·ocr_conf + w3·consistency + w4·validator
w (per field class):
  amounts:    w=[0.45, 0.25, 0.15, 0.15]
  identity:   w=[0.40, 0.30, 0.15, 0.15]   (name, vat, iban)
  dates/text: w=[0.35, 0.35, 0.10, 0.20]
```
- `method_conf`: rules→regex-quality heuristic; llm→provider score mapped via calibration; vlm→similar.
- `ocr_conf`: mean char confidence of source blocks (0.9 when digital text layer).
- `consistency`: agreement between independent extractors (rule vs LLM); cross-field (due≥invoice, totals).
- `validator`: pass=1.0, warn=0.7, fail=0.0.
- **Reason codes** surfaced to UI: `LOW_OCR_CONF`, `RULE_LLM_DISAGREE`, `VAT_MISMATCH`, `MISSING_MANDATORY`, `DATE_SANITY`, `DUPLICATE_CANDIDATE`, `PROVIDER_LOW`, `TABLE_STRUCTURE_LOW`.

Document-level: `doc_conf = min(mean(conf) , min(conf of money fields))` — money fields dominate (a wrong total is worse than a wrong payment term).

**Thresholding:** per-field class threshold + doc threshold from `org_settings.confidence_threshold` (default 0.85). Any money/identity field below → `requires_review`.

## 6. Learning loop (corrections → better extraction)

```
user correction ──► corrections table (old,new,context)
        ├─► recompute validation/confidence for invoice (immediate)
        ├─► few-shot store: per {supplier,country,language,doc_type} top-k correct extractions
        │     injected into LLM prompt (as examples, NOT in-context personal data at scale — 
        │     sampling only metadata-safe examples)
        ├─► eval candidate queue (≥ N corrections for a supplier → add to golden eval set)
        └─► supplier profile accuracy stat → feed "trusted supplier" fast-path (skip LLM)
```
**Privacy constraint:** few-shot examples are stored pre-sanitized (values that are not personal data, or re-verified as already-processed documents of the same tenant); cross-tenant learning is aggregate-only or opt-in. Full cross-tenant model fine-tuning is P4 and gated by explicit consent.

## 7. Eval & monitoring hooks

- Every pipeline run writes: stage durations, confidences, method mix, cost, STP decision → Prometheus + `usage_events`.
- Nightly eval: golden set → field-F1 by country/language/source class; regressions → GitHub issue (`docs/16`).
- Dashboard: STP rate, cost/invoice, conf histograms, correction rate by supplier, LLM error rate (schema failures, retries).
