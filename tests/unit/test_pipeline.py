"""End-to-end worker chain tests (eager mode, SQLite + local storage).

Verifies the real pipeline: upload-adjacent run_pipeline -> ingest -> extract
-> validate -> confidence -> finalize, plus the money-field floor and the
no-text escalation ladder (docs/08 A4/A5, docs/14 §7).
"""

from __future__ import annotations

import hashlib
import io
import uuid

import pytest
from invoiceiq.db import session_scope
from invoiceiq.models import (
    ExtractionField,
    Invoice,
    InvoicePage,
    LineItem,
    Organization,
    ProcessingJob,
    ValidationCheck,
)
from invoiceiq.ocr import paddle_available, tesseract_available
from invoiceiq.storage import get_storage
from invoiceiq.storage.local import build_key
from invoiceiq.workers import run_pipeline

from tests.helpers.pdf import GERMAN_INVOICE, make_invoice_pdf, make_scanned_pdf


def _make_org() -> str:
    with session_scope() as session:
        org = Organization(slug=f"org-{uuid.uuid4().hex[:8]}", name="Test GmbH")
        session.add(org)
        session.flush()
        return str(org.id)


def _upload(org_id: str, data: bytes, filename: str = "invoice.pdf") -> tuple[uuid.UUID, str]:
    invoice_id = uuid.uuid4()
    object_key = build_key(org_id, str(invoice_id), filename)
    with session_scope(org_id=org_id) as session:
        session.add(
            Invoice(
                id=invoice_id,
                org_id=uuid.UUID(org_id),
                object_key=object_key,
                sha256=hashlib.sha256(data).hexdigest(),
                filename=filename,
                file_size=len(data),
                mime_type="application/pdf",
                status="queued",
            )
        )
    get_storage().put(object_key, io.BytesIO(data), content_type="application/pdf")
    return invoice_id, object_key


def test_pipeline_completes_digital_invoice():
    org_id = _make_org()
    invoice_id, object_key = _upload(org_id, make_invoice_pdf())
    run_pipeline(str(invoice_id), org_id, object_key, "invoice.pdf")

    with session_scope(org_id=org_id) as session:
        invoice = session.get(Invoice, invoice_id)
        assert invoice.status == "completed"
        assert invoice.total_conf >= 0.85
        assert invoice.invoice_number == "2024-0147"
        assert str(invoice.invoice_date) == "2024-01-15"
        assert invoice.currency == "EUR"
        assert invoice.doc_type == "invoice"
        assert invoice.language == "de"
        assert invoice.country == "DE"

        fields = {
            f.field: f for f in session.query(ExtractionField).filter_by(invoice_id=invoice_id)
        }
        expected = {
            "supplier_name", "supplier_vat", "iban", "invoice_number",
            "invoice_date", "due_date", "currency", "subtotal", "total_vat", "total",
        }
        assert set(fields) >= expected
        assert fields["total"].validator_status == "pass"
        assert fields["iban"].validator_status == "pass"

        assert session.query(LineItem).filter_by(invoice_id=invoice_id).count() == 1
        checks = {
            c.check_name: c
            for c in session.query(ValidationCheck).filter_by(invoice_id=invoice_id)
        }
        assert checks["grand_total"].status == "pass"
        assert checks["subtotal"].status == "pass"
        assert checks["vat_total"].status == "pass"
        assert checks["vat_format"].status == "pass"
        assert checks["iban"].status == "pass"


def test_mismatched_total_flags_requires_review():
    org_id = _make_org()
    bad = dict(GERMAN_INVOICE, total="1500,00")
    invoice_id, object_key = _upload(org_id, make_invoice_pdf(bad))
    run_pipeline(str(invoice_id), org_id, object_key, "invoice.pdf")

    with session_scope(org_id=org_id) as session:
        invoice = session.get(Invoice, invoice_id)
        assert invoice.status == "requires_review"
        assert invoice.total_conf < 0.85
        checks = {
            c.check_name: c
            for c in session.query(ValidationCheck).filter_by(invoice_id=invoice_id)
        }
        assert checks["grand_total"].status == "fail"


def test_corrupt_pdf_escalates_to_failed():
    org_id = _make_org()
    invoice_id, object_key = _upload(org_id, b"not a pdf at all", "bad.pdf")
    run_pipeline(str(invoice_id), org_id, object_key, "bad.pdf")

    with session_scope(org_id=org_id) as session:
        invoice = session.get(Invoice, invoice_id)
        assert invoice.status == "failed"
        failed = (
            session.query(ProcessingJob)
            .filter_by(invoice_id=invoice_id, stage="ingest")
            .order_by(ProcessingJob.created_at.desc())
            .first()
        )
        assert failed.status == "failed"
        assert failed.error == "OCR_NO_TEXT"


def test_scanned_pdf_runs_scan_path():
    if not (paddle_available() or tesseract_available()):
        pytest.skip("no OCR engine installed")
    org_id = _make_org()
    invoice_id, object_key = _upload(org_id, make_scanned_pdf(), "scan.pdf")
    run_pipeline(str(invoice_id), org_id, object_key, "scan.pdf")

    with session_scope(org_id=org_id) as session:
        invoice = session.get(Invoice, invoice_id)
        assert invoice.status in ("completed", "requires_review")

        pages = session.query(InvoicePage).filter_by(invoice_id=invoice_id).all()
        assert pages, "scanned PDF should produce InvoicePage rows"
        assert all(p.ocr_engine in ("paddleocr", "tesseract") for p in pages)

        fields = {
            f.field: f for f in session.query(ExtractionField).filter_by(invoice_id=invoice_id)
        }
        assert fields, "scan path should extract at least some fields"
