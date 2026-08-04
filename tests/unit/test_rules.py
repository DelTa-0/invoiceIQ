"""Deterministic rules engine tests — verified against the generated PDF."""

from __future__ import annotations

from invoiceiq.extract.rules import (
    extract_line_items,
    find_currency,
    find_dates,
    find_iban,
    find_invoice_number,
    find_money,
    find_supplier_name,
    find_vat,
    iso_value,
    numeric,
    parse_decimal,
    scalar,
)
from invoiceiq.ocr import DigitalPDFEngine

from tests.helpers.pdf import make_invoice_pdf


def _blocks_and_pages():
    pages = DigitalPDFEngine().extract(make_invoice_pdf())
    blocks = [(page_no, b) for page_no, page in enumerate(pages) for b in page.blocks]
    return blocks, pages


def test_parse_decimal_locales():
    assert parse_decimal("1.234,56") == 1234.56
    assert parse_decimal("1234.56") == 1234.56
    assert parse_decimal("1,000.00") == 1000.0
    assert parse_decimal("1.000") == 1000.0
    assert parse_decimal("-5,00") == -5.0
    assert parse_decimal("0") == 0.0


def test_vat_rule():
    blocks, _ = _blocks_and_pages()
    candidate = find_vat(blocks)
    assert scalar(candidate) == "DE123456789"
    assert candidate.method == "rules"
    assert candidate.source_text


def test_iban_rule():
    blocks, _ = _blocks_and_pages()
    candidate = find_iban(blocks)
    assert scalar(candidate) == "DE89370400440532013000"


def test_invoice_number_rule():
    blocks, _ = _blocks_and_pages()
    candidate = find_invoice_number(blocks)
    assert scalar(candidate) == "2024-0147"


def test_dates_rule():
    blocks, _ = _blocks_and_pages()
    invoice_date, due_date = find_dates(blocks)
    assert iso_value(invoice_date) == "2024-01-15"
    assert iso_value(due_date) == "2024-02-14"


def test_currency_rule():
    blocks, _ = _blocks_and_pages()
    assert scalar(find_currency(blocks)) == "EUR"


def test_money_rules():
    blocks, _ = _blocks_and_pages()
    money = find_money(blocks)
    assert numeric(money["subtotal"]) == 1000.0
    assert numeric(money["total_vat"]) == 190.0
    assert numeric(money["total"]) == 1190.0


def test_supplier_name_rule():
    blocks, _ = _blocks_and_pages()
    assert scalar(find_supplier_name(blocks)) == "ACME Muster GmbH"


def test_line_items_from_table():
    _, pages = _blocks_and_pages()
    items = extract_line_items(pages)
    assert len(items) == 1
    item = items[0]
    assert item.description == "Werkzeug-Set"
    assert item.quantity == 2.0
    assert item.unit_price == 500.0
    assert item.net == 1000.0
    assert item.vat_rate == 19.0
    assert item.vat_amount == 190.0
    assert item.gross == 1190.0
