"""Digital PDF engine tests (docs/14 §2, §5)."""

from __future__ import annotations

import pytest
from invoiceiq.ocr import DigitalPDFEngine, OCRNoTextError

from tests.helpers.pdf import make_invoice_pdf


def test_text_layer_page_and_blocks():
    pages = DigitalPDFEngine().extract(make_invoice_pdf())
    assert len(pages) == 1
    page = pages[0]
    assert page.text_layer is True
    assert page.engine == "pdfplumber"
    assert page.avg_confidence == 1.0
    assert page.blocks, "expected text blocks"
    assert page.blocks[0].bbox, "expected a normalized bbox"

    text = page.text
    assert "ACME Muster GmbH" in text
    assert "DE123456789" in text
    assert "2024-0147" in text


def test_blocks_are_single_lines_in_reading_order():
    page = DigitalPDFEngine().extract(make_invoice_pdf())[0]
    tops = [b.bbox[1] for b in page.blocks if b.bbox]
    assert tops == sorted(tops)
    assert all(len(b.bbox) == 4 for b in page.blocks)


def test_tables_extracted_with_cells():
    page = DigitalPDFEngine().extract(make_invoice_pdf())[0]
    assert page.tables
    cells = [c.text for t in page.tables for row in t.rows for c in row]
    assert "Werkzeug-Set" in cells
    assert "1190,00" in cells


def test_non_pdf_bytes_raise_no_text():
    with pytest.raises(OCRNoTextError):
        DigitalPDFEngine().extract(b"definitely not a pdf")
