# 13 — Prompt Engineering Strategy

## 1. Principles

1. **The LLM proposes; rules dispose.** Prompts optimize recall; validation guarantees correctness. Never ask an LLM to do arithmetic when a calculator exists.
2. **Grounded output only.** Every field must reference `source_text` + `bbox`. Fields without a source are returned as `missing` (or `low_confidence`), never invented.
3. **Schema-first.** JSON-Schema constrained output (provider tool-calls / structured output); Pydantic validates; malformed → one `retry-with-fix`.
4. **Deterministic preface.** Invoices are presented as a normalized doc model (blocks + roles + tables), not raw OCR soup. Less ambiguity = fewer tokens = cheaper.
5. **Multi-tenant safety.** No cross-tenant data in prompts; few-shot examples sanitized and tenant-scoped.

## 2. Prompt architecture

```
┌────────────────────────────────────────────────────────────────┐
│ SYSTEM (static)                                                │
│   You are an EU accounts-payable extraction specialist.        │
│   Return ONLY JSON matching the provided schema.               │
│   Rules:                                                       │
│    - cite source_text+bbox for every value                     │
│    - never invent values; missing → {"value":null,"missing":true}│
│    - money uses "." decimal; dates ISO-8601                    │
│    - recognize reverse charge / intra-community / zero-rated   │
│    - VAT country prefixes: DE=DE, IT=IT, FR=FR, ES=ES,         │
│      NL=NL, BE=BE, AT=AT, LU=LU...                             │
│    - do not do math; report raw numbers as printed             │
│    - if document is not an invoice, set doc_type=other and     │
│      leave fields null                                         │
├────────────────────────────────────────────────────────────────┤
│ EXAMPLES (≤3, per {supplier,country,language} when available)  │
│   (sanitized, tenant-scoped)                                   │
├────────────────────────────────────────────────────────────────┤
│ DOCUMENT (normalized doc model)                                │
│   language: de | country: DE | pages: [blocks + tables...]     │
├────────────────────────────────────────────────────────────────┤
│ SCHEMA (JSON Schema of extraction contract)                    │
└────────────────────────────────────────────────────────────────┘
```

## 3. Task-specific prompts

### 3.1 Classification (cheap model)
3-way: `invoice | credit_note | other` with `confidence` + one-line reason. Triggers sign detection (credit notes negative totals), no line-item over-engineering for `other`.

### 3.2 Extraction (primary)
Header + lines in one structured call when ≤ ~30 lines (typical). For huge line sets (>30): extract header first, then line items in batches of 25 with row anchors (`ref`) so merging is deterministic. Cost guardrail: never exceed `MAX_EXTRACT_TOKENS` (env).

### 3.3 VAT reasoning
Prompt recognizes: reverse charge (`steuerfreie innergemeinschaftliche Lieferung`, `reverse charge`…), intra-community, zero-rated, mixed rates. But the **decision to trust is the validator's**, using the per-country profile — the prompt only surfaces candidates + the phrase that implies the mode.

### 3.4 Correction-annotated re-extract
On human correction: re-prompt with `(field, old, new, reason)` appended as a correction hint for THIS doc only. Enables per-doc consistency without global retraining.

### 3.5 NL search (P2)
Query → `{filters: {...}, q: "...", reasoning}` in strict schema; execute on SQL. Provide enum values (statuses, currencies, countries) to prevent drift. No free-text generation of SQL.

## 4. Language handling

- Language auto-detect from text (fastText `lid.176` ~tiny; or heuristic + LLM confirm) → sets `invoice.language`, informs date/number parsing (dd.mm.yyyy vs mm/dd/yyyy), and chooses VAT locale patterns.
- Prompt system message is English; document stays in source language (the model reads it natively). Field *labels* normalize to English keys (`supplier_name`, `vat_number`, …) — UI localizes display.
- Multilingual line-item descriptions: kept verbatim; `invoice.language` stores dominant language.

## 5. Provider routing (residency-aware)

```jsonc
// llm/registry.py routing
{
  "eu_only":   {"extract": "mistral:medium", "classify": "mistral:small", "vlm": "mistral:pixtral"},
  "us_opt_in": {"extract": "openai:gpt-4o-mini|anthropic:claude-haiku", "vlm": "gemini:2.5-flash"},
  "sovereign": {"extract": "local:qwen2.5-7b", "vlm": "local:qwen2.5-vl-3b"}
}
```
Fallback chain per task; token + cost budgets enforced in `llm/tokens.py`; every call logged with `provider, model, prompt_tokens, completion_tokens, cost`.

## 6. Anti-hallucination hard rules (non-negotiable)

- No value without `source_text` + `bbox` → automatically `low_confidence`/`missing`.
- Money fields: LLM reports raw strings; arithmetic done by `validate/arithmetic.py`. LLM never returns computed totals it didn't read verbatim (and if it does, reconciliation flags it).
- Invoice number/date/VAT/IBAN: rule extractors take precedence on disagreement; LLM output demoted to candidate.
- Unknown/ambiguous → `missing:true` + `reason`, not a guess. `requires_review` beats a confident wrong answer.
- Prompt injection: document text is untrusted input; instruct the model that invoice text is DATA, never instructions; field extraction only; no tool access from doc content.

## 7. Versioning & eval

- Prompts live in `llm/prompts/*.py` (versioned constants); each pipeline run records `prompt_version` + `model_version` on `processing_jobs.payload` for reproducibility.
- Golden-set eval measures prompt changes (field-F1 per task) before rollout; A/B rollouts gated by eval job (see `docs/16`).
- Token drift alert: prompt tokens > 20% above baseline → PR review.
