"""Extraction orchestrator tests: rules-only and rules+LLM merge paths."""

from __future__ import annotations

from invoiceiq.extract import extract_from_pages, numeric, scalar
from invoiceiq.llm.client import MockClient
from invoiceiq.ocr import DigitalPDFEngine

from tests.helpers.pdf import make_invoice_pdf


def _result(client=None):
    pages = DigitalPDFEngine().extract(make_invoice_pdf())
    return extract_from_pages(pages, client=client)


def test_rules_only_extraction():
    result = _result()
    assert result.doc_type == "invoice"
    assert result.language == "de"
    assert result.country == "DE"
    assert scalar(result.fields["total"]) == "1190,00"
    assert numeric(result.fields["total"]) == 1190.0
    assert scalar(result.fields["supplier_vat"]) == "DE123456789"
    assert len(result.line_items) == 1
    assert all(c.method == "rules" for c in result.fields.values())


def test_llm_merge_grounds_and_agrees():
    payload = (
        '{"doc_type": "invoice", "language": "de", "country": "DE", '
        '"fields": {"total": {"value": "1190,00", "source_text": "Gesamtbetrag 1190,00 EUR"}}, '
        '"line_items": []}'
    )
    result = _result(client=MockClient(payload))
    total = result.fields["total"]
    assert numeric(total) == 1190.0
    assert total.bbox is not None, "LLM value should be grounded to a block bbox"
    assert total.method == "rules"  # agreement keeps the rule as authoritative
