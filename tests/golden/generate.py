"""Golden-set scaffolding (docs/07, docs/16).

Generates deterministic PDF fixtures into `tests/golden/fixtures/` plus a
`expected.json` manifest of the ground truth the eval harness checks against.

Usage: python -m tests.golden.generate
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.pdf import GERMAN_INVOICE, make_invoice_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"

EXPECTED: dict = {
    "de-invoice-2024-0147": {
        "filename": "de-invoice-2024-0147.pdf",
        "doc_type": "invoice",
        "language": "de",
        "country": "DE",
        "fields": {
            "supplier_name": "ACME Muster GmbH",
            "supplier_vat": "DE123456789",
            "invoice_number": "2024-0147",
            "invoice_date": "2024-01-15",
            "due_date": "2024-02-14",
            "currency": "EUR",
            "subtotal": 1000.0,
            "total_vat": 190.0,
            "total": 1190.0,
            "iban": "DE89370400440532013000",
        },
        "line_items": [
            {
                "position": 1,
                "description": "Werkzeug-Set",
                "quantity": 2.0,
                "unit_price": 500.0,
                "net": 1000.0,
                "vat_rate": 19.0,
                "vat_amount": 190.0,
                "gross": 1190.0,
            }
        ],
    }
}


def generate() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for _key, entry in EXPECTED.items():
        (FIXTURES_DIR / entry["filename"]).write_bytes(make_invoice_pdf(GERMAN_INVOICE))
    (FIXTURES_DIR.parent / "expected.json").write_text(
        json.dumps(EXPECTED, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {len(EXPECTED)} fixtures to {FIXTURES_DIR}")


if __name__ == "__main__":
    generate()
