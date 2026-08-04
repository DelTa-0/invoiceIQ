# Golden test set

Ground-truth invoices the eval harness measures field-F1 and STP rate against
(`docs/08` §4, `docs/16`). Each fixture is generated deterministically by
`python -m tests.golden.generate` — the manifest `expected.json` is the label.

Stratification (per docs/14 §9): digital text-layer PDF, scanned, photo,
rotated, low-DPI, and handwritten-annotation. Currently only the digital layer
is generated; the others fill in as the OCR path lands.
