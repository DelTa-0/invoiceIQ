from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DocType(StrEnum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    PURCHASE_ORDER = "purchase_order"
    PROFORMA = "proforma"
    CREDIT_NOTE = "credit_note"
    CONTRACT = "contract"
    SHIPPING_DOCUMENT = "shipping_document"
    CUSTOMS_FORM = "customs_form"
    BANK_STATEMENT = "bank_statement"
    TAX_DOCUMENT = "tax_document"
    EMPLOYEE_DOCUMENT = "employee_document"
    INSURANCE_CLAIM = "insurance_claim"
    LAND_REGISTRY = "land_registry"
    COURT_ORDER = "court_order"
    FINANCIAL_REPORT = "financial_report"
    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Classification:
    doc_type: DocType
    confidence: float
    keywords_matched: tuple[str, ...] | None = None
    page_hint: int | None = None