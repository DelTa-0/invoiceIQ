"""Composite confidence engine tests (docs/12 §5)."""

from invoiceiq.confidence import document_confidence, field_confidence


def test_high_confidence_field():
    conf = field_confidence(method_conf=1.0, ocr_conf=0.99, consistency=1.0, validator_status="pass", field="supplier_name")
    assert conf >= 0.9


def test_failed_validator_penalizes_money():
    conf = field_confidence(method_conf=0.95, ocr_conf=0.95, consistency=1.0, validator_status="fail", field="total")
    assert conf < 0.5


def test_low_ocr_conf():
    conf = field_confidence(method_conf=0.5, ocr_conf=0.4, consistency=0.5, field="invoice_number")
    assert conf < 0.7


def test_money_floor_drives_document_status():
    fields = {
        "supplier_name": 0.99,
        "invoice_number": 0.95,
        "total": 0.60,  # below threshold -> requires review despite high mean
        "subtotal": 0.99,
    }
    doc = document_confidence(fields, threshold=0.85)
    assert doc.status == "requires_review"
    assert doc.min_money_conf == 0.60


def test_high_confidence_document_completes():
    fields = {"supplier_name": 0.99, "total": 0.98, "subtotal": 0.97}
    doc = document_confidence(fields, threshold=0.85)
    assert doc.status == "completed"
