# 14 — OCR Strategy

## 1. Goal
Maximize accuracy at minimum cost, with graceful degradation. Digital invoices cost ≈€0; only genuinely scanned/messy documents pay for OCR. Handwriting is best-effort and honestly low-confidence — never silently high-confidence.

## 2. Routing decision

```
file → normalize pages
  └─ PDF with text layer?  char/page density ≥ threshold?
        YES → digital path (pdfplumber: words + bboxes + tables)
        NO  → rasterize (PyMuPDF, 300 DPI) → PaddleOCR
  └─ image → EXIF orient → (auto-rotate via PaddleOCR angle classifier) → PaddleOCR
        └─ PaddleOCR low language support or poor result → Tesseract fallback
        └─ both poor + (photo/handwriting/heavy noise) → VLM escalation (P2+ GPU/local)
```

## 3. Engine matrix

| Engine | Use when | Strengths | Weaknesses |
|---|---|---|---|
| pdfplumber (digital) | text-layer PDF | exact, free, word boxes + tables | gibberish on scanned-only PDFs |
| PaddleOCR PP-OCRv4 | scans/images, 80+ langs, CJK | strong structured doc accuracy, fast on CPU, angle classifier, PP-Structure tables | framework install weight; docs mostly Chinese |
| Tesseract v5 | rare-language fallback | 100+ langs, mature | weaker tables/layout, needs preprocessing |
| (P2) Qwen2.5-VL / Pixtral | photo/handwriting/complex | true layout understanding | cost/GPU; latency |

**Recommendation:** PaddleOCR PP-OCRv4 is primary (benchmarked best open-source for structured docs, competitive with Tesseract, better tables via PP-StructureV3). Keep Tesseract as a narrow fallback for language gaps, not a co-primary.

## 4. Preprocessing pipeline (image path)

1. EXIF orientation fix (Pillow) — cheap, mandatory.
2. DPI check: if < 200 → upscale (Lanczos) to ≥ 300; reject > 600 (downscale).
3. Deskew via angle classifier (PaddleOCR built-in) — rotated pages.
4. Denoise/contrast: light CLAHE only when needed (measure sharpness); avoid blanket binarization (hurts modern ML OCR).
5. Auto-orientation by reading (PaddleOCR angle classification returns 0/90/180/270).
6. Page pairing for two-page spreads (mobile photos) — split on gutter.

## 5. Output model (per page)

Every block: `{text, conf, bbox[x0,y0,x1,y1] (normalized 0..1), line_no, reading_order, role, table_cell, row, col}`.

- **Reading order** from layout analysis (PP-Structure layout blocks → sort top-to-bottom, left-to-right within column regions).
- **Role labeling:** `key_value | amount | date | company | address | header | footer | table | note` — via PP-Structure + light heuristics; primes LLM and review highlights.
- **Tables:** PP-Structure table recognition → `tables[]` with row/col cells + bbox; line items parsed from cells; rows wrapping multiple visual lines merged by column alignment heuristic.
- **Confidence:** char-level from engine, per block; OCR conf feeds `field_confidence` (docs/12 §5).

## 6. Language handling

- Auto-detect (fastText lid.176) at page level → sets `invoice.language`.
- PaddleOCR `lang` param per detected language; multi-language docs: run per-language or rely on multilingual mode (de/it/fr/es/nl/en supported natively).
- Mixed VAT/number formats parsed with locale-aware rules (comma vs dot decimals) AFTER language known.

## 7. Failure & escalation ladder

1. Digital path returns empty/density-low → treat as scanned, go PaddleOCR.
2. PaddleOCR returns near-empty or avg conf < 0.5 → try Tesseract (different model, sometimes rescues).
3. Still poor → mark `OCR_NO_TEXT`/`LOW_QUALITY`, set doc-level `requires_review`, and (if org policy permits VLM) route to VLM for a second pass. Never output confident garbage.
4. Encrypted/corrupt PDF → `failed(UNSUPPORTED_FORMAT)` with clear UI message.

## 8. Performance & cost

- **CPU:** PP-OCRv4 ~1–3 s/page single-core modern CPU; a 4-vCPU worker ≈ 15–60 pages/min sustained. MVP volumes (≤1k/day) trivially fine; 10k/day = 2 workers or a small GPU node.
- **GPU (P2):** PaddleOCR GPU is 5–10× faster; also unlocks local VLM sovereign path. Keep models warm (worker preload), batch page tasks per invoice.
- **Model storage:** models cached in image/volume (PaddleOCR ~ a few hundred MB); version-pinned to avoid silent accuracy drift.
- **Telemetry:** `ocr_engine`, `ocr_confidence`, `ocr_duration_ms`, `pages_ocr` per invoice → Prometheus + cost dashboard.

## 9. Accuracy validation (ties to docs/16)

- Golden set stratified: digital/scanned/photo/rotated/low-DPI/handwritten-annotation.
- Nightly eval: char accuracy + field-level F1 per stratum; engine version bumps gated on eval deltas.
- Real-world regression: every `OCR_NO_TEXT`/reviewed-wrong-field is a candidate golden entry.
