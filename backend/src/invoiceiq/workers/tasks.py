"""Pipeline tasks: ingest -> extract -> validate -> confidence -> finalize.

Replaces the Phase 0 stubs with the real chain (docs/12 §1). The digital
text-layer path is live; scanned/image OCR escalates via `OCRNoTextError`.
Domain failures mark the invoice `failed` and short-circuit the rest of the
chain (each later stage skips invoices already `failed`).
"""

from __future__ import annotations

import uuid
from datetime import date

import structlog
from celery.canvas import chain

from ..core.audit import write as audit_write
from ..db import session_scope
from ..extract import extract_from_pages, numeric, scalar
from ..extract.rules import iso_value
from ..llm import get_client, resolve_provider
from ..models import (
    ExtractionField,
    Invoice,
    InvoicePage,
    LineItem,
    Organization,
    ProcessingJob,
    ValidationCheck,
)
from ..ocr import OCRNoTextError, OCRPage, normalize_document
from ..settings import get_settings
from ..storage import get_storage
from ..validate.engine import check_arithmetic, check_iban, check_vat_format
from .app import celery_app

logger = structlog.get_logger("invoiceiq.workers")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _invoice(session, invoice_id: str) -> Invoice | None:
    try:
        return session.get(Invoice, uuid.UUID(invoice_id))
    except ValueError:
        return None


def _set_invoice_status(invoice_id: str, org_id: str, status: str) -> None:
    with session_scope(org_id=org_id) as session:
        invoice = _invoice(session, invoice_id)
        if invoice is None:
            return
        invoice.status = status
        if status == "processing":
            invoice.total_conf = 0.0


def _append_job(
    invoice_id: str,
    org_id: str,
    stage: str,
    status: str,
    *,
    error: str | None = None,
    payload: dict | None = None,
) -> None:
    with session_scope(org_id=org_id) as session:
        session.add(
            ProcessingJob(
                invoice_id=uuid.UUID(invoice_id),
                stage=stage,
                status=status,
                error=error,
                payload=payload,
                attempt=1,
            )
        )


def _read_job_payload(invoice_id: str, org_id: str, stage: str) -> dict | None:
    with session_scope(org_id=org_id) as session:
        job = (
            session.query(ProcessingJob)
            .filter(
                ProcessingJob.invoice_id == uuid.UUID(invoice_id),
                ProcessingJob.stage == stage,
                ProcessingJob.status == "done",
            )
            .order_by(ProcessingJob.created_at.desc())
            .first()
        )
        return job.payload if job is not None else None


def _read_pages(invoice_id: str, org_id: str) -> list[OCRPage] | None:
    payload = _read_job_payload(invoice_id, org_id, "ingest")
    if payload is None:
        return None
    return [OCRPage.model_validate(p) for p in payload.get("pages", [])]


def _llm_client(org_id: str):
    settings = get_settings()
    if not settings.llm_api_key:
        return None
    with session_scope(org_id=org_id) as session:
        org = session.get(Organization, uuid.UUID(org_id))
        policy = org.data_residency if org is not None else "eu_only"
    route = resolve_provider(policy, "extract")
    return get_client(route, api_key=settings.llm_api_key)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _persist_pages(invoice_id: str, org_id: str, pages: list[OCRPage]) -> None:
    with session_scope(org_id=org_id) as session:
        for page in pages:
            session.add(
                InvoicePage(
                    invoice_id=uuid.UUID(invoice_id),
                    page_no=page.page_no,
                    width=page.width,
                    height=page.height,
                    text_layer=page.text_layer,
                    ocr_engine=page.engine,
                )
            )


def _persist_extraction(invoice_id: str, org_id: str, result) -> None:
    with session_scope(org_id=org_id) as session:
        invoice = _invoice(session, invoice_id)
        if invoice is None:
            return
        for field, candidate in result.fields.items():
            session.add(
                ExtractionField(
                    invoice_id=invoice.id,
                    field=field,
                    value=candidate.value,
                    confidence=candidate.confidence,
                    method=candidate.method,
                    source_text=candidate.source_text,
                    bbox=candidate.bbox.model_dump() if candidate.bbox else None,
                    validator_status=candidate.validator.status,
                    validator_detail=(
                        candidate.validator.detail if candidate.validator.status else None
                    ),
                    status=candidate.status,
                )
            )
        for item in result.line_items:
            session.add(
                LineItem(
                    invoice_id=invoice.id,
                    position=item.position,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    discount_pct=item.discount_pct,
                    net=item.net,
                    vat_rate=item.vat_rate,
                    vat_amount=item.vat_amount,
                    gross=item.gross,
                    sku=item.sku,
                    confidence=item.confidence,
                )
            )

        def field_value(name: str):
            candidate = result.fields.get(name)
            return candidate if candidate is not None else None

        invoice.doc_type = result.doc_type
        invoice.language = result.language
        invoice.country = result.country
        invoice.invoice_number = scalar(field_value("invoice_number"))
        invoice.invoice_date = _to_date(iso_value(field_value("invoice_date")))
        invoice.due_date = _to_date(iso_value(field_value("due_date")))
        invoice.supplier_name = scalar(field_value("supplier_name"))
        invoice.supplier_vat = scalar(field_value("supplier_vat"))
        invoice.currency = scalar(field_value("currency"))
        invoice.subtotal = numeric(field_value("subtotal"))
        invoice.total_vat = numeric(field_value("total_vat"))
        invoice.total = numeric(field_value("total"))


def _to_date(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso)
    except ValueError:
        return None


def _persist_validation(invoice_id: str, org_id: str, checks) -> None:
    with session_scope(org_id=org_id) as session:
        existing = {
            (c.invoice_id, c.check_name)
            for c in session.query(ValidationCheck).filter(
                ValidationCheck.invoice_id == uuid.UUID(invoice_id)
            )
        }
        invoice_id_uuid = uuid.UUID(invoice_id)
        for check in checks:
            if (invoice_id_uuid, check.check_name) in existing:
                continue
            session.add(
                ValidationCheck(
                    invoice_id=invoice_id_uuid,
                    check_name=check.check_name,
                    status=check.status,
                    severity=check.severity,
                    reason=check.reason,
                    evidence=check.evidence,
                )
            )


_FIELD_CHECK_MAP = {
    "subtotal": "subtotal",
    "total_vat": "vat_total",
    "total": "grand_total",
    "supplier_vat": "vat_format",
    "iban": "iban",
}


def _apply_validator_status(invoice_id: str, org_id: str, checks) -> None:
    status_by_name = {c.check_name: c for c in checks}
    with session_scope(org_id=org_id) as session:
        fields = (
            session.query(ExtractionField)
            .filter(ExtractionField.invoice_id == uuid.UUID(invoice_id))
            .all()
        )
        for field in fields:
            check = status_by_name.get(_FIELD_CHECK_MAP.get(field.field, ""))
            if check is None:
                continue
            field.validator_status = check.status
            field.validator_detail = {"rule": check.reason, "evidence": check.evidence}


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@celery_app.task(name="invoiceiq.ingest", max_retries=3, default_retry_delay=5)
def ingest(invoice_id: str, org_id: str, object_key: str, filename: str) -> dict:
    """Stage 1: claim, normalize, route, and persist OCR pages."""
    try:
        _set_invoice_status(invoice_id, org_id, "processing")
        data = get_storage().get(object_key)
        pages = normalize_document(data, filename)
        if not any(p.blocks for p in pages):
            raise OCRNoTextError("no readable text found in any page")
        _persist_pages(invoice_id, org_id, pages)
        engines = {p.engine for p in pages}
        _append_job(
            invoice_id,
            org_id,
            "ingest",
            "done",
            payload={
                "pages": [p.model_dump() for p in pages],
                "engine": ",".join(sorted(engines)),
                "n_pages": len(pages),
            },
        )
        logger.info("ingest ok", invoice_id=invoice_id, filename=filename, n_pages=len(pages))
        return {"invoice_id": invoice_id, "stage": "ingest", "status": "done"}
    except OCRNoTextError as exc:
        _set_invoice_status(invoice_id, org_id, "failed")
        _append_job(invoice_id, org_id, "ingest", "failed", error="OCR_NO_TEXT")
        logger.warning("ingest failed: no text layer", invoice_id=invoice_id, error=str(exc))
        return {"invoice_id": invoice_id, "stage": "ingest", "status": "failed", "reason": "OCR_NO_TEXT"}
    except Exception as exc:
        _set_invoice_status(invoice_id, org_id, "failed")
        _append_job(invoice_id, org_id, "ingest", "failed", error=str(exc))
        logger.exception("ingest failed", invoice_id=invoice_id)
        return {"invoice_id": invoice_id, "stage": "ingest", "status": "failed", "reason": "INGEST_ERROR"}


@celery_app.task(name="invoiceiq.extract")
def extract(invoice_id: str, org_id: str, filename: str) -> dict:
    """Stage 2: rules-first extraction (LLM merge when a key is configured)."""
    with session_scope(org_id=org_id) as session:
        invoice = _invoice(session, invoice_id)
        if invoice is None:
            return {"status": "missing"}
        if invoice.status == "failed":
            return {"invoice_id": invoice_id, "stage": "extract", "status": "skipped"}
    try:
        pages = _read_pages(invoice_id, org_id)
        if not pages:
            raise OCRNoTextError("no pages from ingest stage")
        client = _llm_client(org_id)
        result = extract_from_pages(pages, client=client)
        _persist_extraction(invoice_id, org_id, result)
        _append_job(
            invoice_id,
            org_id,
            "extract",
            "done",
            payload={
                "result": result.model_dump(),
                "llm_used": client is not None,
                "n_fields": len(result.fields),
                "n_line_items": len(result.line_items),
            },
        )
        logger.info(
            "extract ok",
            invoice_id=invoice_id,
            llm_used=client is not None,
            n_fields=len(result.fields),
        )
        return {"invoice_id": invoice_id, "stage": "extract", "status": "done"}
    except Exception as exc:
        _set_invoice_status(invoice_id, org_id, "failed")
        _append_job(invoice_id, org_id, "extract", "failed", error=str(exc))
        logger.exception("extract failed", invoice_id=invoice_id)
        return {"invoice_id": invoice_id, "stage": "extract", "status": "failed", "reason": "EXTRACT_ERROR"}


@celery_app.task(name="invoiceiq.validate")
def validate(invoice_id: str, org_id: str) -> dict:
    """Stage 3: deterministic validation; flagged fields are never auto-fixed."""
    try:
        with session_scope(org_id=org_id) as session:
            invoice = _invoice(session, invoice_id)
            if invoice is None:
                return {"status": "missing"}
            if invoice.status == "failed":
                return {"invoice_id": invoice_id, "stage": "validate", "status": "skipped"}
            lines = [
                {
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                    "discount_pct": line.discount_pct,
                    "vat_rate": line.vat_rate,
                    "gross": line.gross,
                    "net": line.net,
                }
                for line in session.query(LineItem)
                .filter(LineItem.invoice_id == invoice.id)
                .order_by(LineItem.position)
            ]
            invoice_dict = {
                "subtotal": invoice.subtotal,
                "total_vat": invoice.total_vat,
                "shipping": None,
                "other": None,
                "total": invoice.total,
            }
            checks = check_arithmetic(lines, invoice_dict)
            if invoice.supplier_vat:
                checks.append(check_vat_format(invoice.supplier_vat))
            iban_field = (
                session.query(ExtractionField)
                .filter(
                    ExtractionField.invoice_id == invoice.id,
                    ExtractionField.field == "iban",
                )
                .first()
            )
            if iban_field is not None and iban_field.value:
                raw = iban_field.value.get("value") if isinstance(iban_field.value, dict) else iban_field.value
                if raw:
                    checks.append(check_iban(str(raw)))
        _persist_validation(invoice_id, org_id, checks)
        _apply_validator_status(invoice_id, org_id, checks)
        _append_job(
            invoice_id,
            org_id,
            "validate",
            "done",
            payload={"n_checks": len(checks), "checks": [c.model_dump() for c in checks]},
        )
        logger.info("validate ok", invoice_id=invoice_id, n_checks=len(checks))
        return {"invoice_id": invoice_id, "stage": "validate", "status": "done"}
    except Exception as exc:
        _set_invoice_status(invoice_id, org_id, "failed")
        _append_job(invoice_id, org_id, "validate", "failed", error=str(exc))
        logger.exception("validate failed", invoice_id=invoice_id)
        return {"invoice_id": invoice_id, "stage": "validate", "status": "failed", "reason": "VALIDATE_ERROR"}


@celery_app.task(name="invoiceiq.confidence")
def confidence(invoice_id: str, org_id: str) -> dict:
    """Stage 4: composite field confidence + document gate (docs/12 §5)."""
    try:
        from ..confidence import document_confidence, field_confidence

        pages_payload = _read_job_payload(invoice_id, org_id, "ingest")
        block_confs = [
            b.get("conf", 1.0)
            for p in (pages_payload or {}).get("pages", [])
            for b in p.get("blocks", [])
        ]
        ocr_conf = sum(block_confs) / len(block_confs) if block_confs else 1.0

        with session_scope(org_id=org_id) as session:
            invoice = _invoice(session, invoice_id)
            if invoice is None:
                return {"status": "missing"}
            if invoice.status == "failed":
                return {"invoice_id": invoice_id, "stage": "confidence", "status": "skipped"}
            org = session.get(Organization, uuid.UUID(org_id))
            threshold = float(org.confidence_threshold or 0.85) if org is not None else 0.85

            fields = (
                session.query(ExtractionField)
                .filter(ExtractionField.invoice_id == invoice.id)
                .all()
            )
            confs: dict[str, float] = {}
            for field in fields:
                method_conf = float(field.confidence or 0.5)
                value = field_confidence(
                    method_conf=method_conf,
                    ocr_conf=ocr_conf,
                    consistency=1.0,
                    validator_status=field.validator_status,
                    field=field.field,
                )
                field.confidence = value
                if value < threshold:
                    field.status = "flagged"
                confs[field.field] = value

            doc = document_confidence(confs, threshold=threshold)
            invoice.total_conf = doc.score
            invoice.status = doc.status
        _append_job(
            invoice_id,
            org_id,
            "confidence",
            "done",
            payload={"score": doc.score, "min_money_conf": doc.min_money_conf, "status": doc.status},
        )
        logger.info("confidence ok", invoice_id=invoice_id, score=doc.score, status=doc.status)
        return {"invoice_id": invoice_id, "stage": "confidence", "status": doc.status}
    except Exception as exc:
        _set_invoice_status(invoice_id, org_id, "failed")
        _append_job(invoice_id, org_id, "confidence", "failed", error=str(exc))
        logger.exception("confidence failed", invoice_id=invoice_id)
        return {"invoice_id": invoice_id, "stage": "confidence", "status": "failed", "reason": "CONFIDENCE_ERROR"}


@celery_app.task(name="invoiceiq.finalize")
def finalize(invoice_id: str, org_id: str) -> dict:
    """Stage 5: settle the invoice + write the system audit event."""
    with session_scope(org_id=org_id) as session:
        invoice = _invoice(session, invoice_id)
        if invoice is None:
            return {"status": "missing"}
        if invoice.status in ("processing", "queued"):
            invoice.status = "completed"
        final_status = invoice.status
    _append_job(invoice_id, org_id, "finalize", "done", payload={"status": final_status})
    audit_write(
        org_id=uuid.UUID(org_id),
        action="invoice.processed",
        resource="invoice",
        resource_id=invoice_id,
        delta={"status": final_status},
        actor_type="system",
    )
    logger.info("finalize ok", invoice_id=invoice_id, status=final_status)
    return {"invoice_id": invoice_id, "stage": "finalize", "status": final_status}


def run_pipeline(invoice_id: str, org_id: str, object_key: str, filename: str):
    """Kick off the task chain (immutable signatures, bound to our app)."""
    first = celery_app.signature(
        "invoiceiq.ingest",
        kwargs={"invoice_id": invoice_id, "org_id": org_id, "object_key": object_key, "filename": filename},
        immutable=True,
    )
    extract_sig = celery_app.signature(
        "invoiceiq.extract",
        kwargs={"invoice_id": invoice_id, "org_id": org_id, "filename": filename},
        immutable=True,
    )
    validate_sig = celery_app.signature(
        "invoiceiq.validate", kwargs={"invoice_id": invoice_id, "org_id": org_id}, immutable=True
    )
    confidence_sig = celery_app.signature(
        "invoiceiq.confidence", kwargs={"invoice_id": invoice_id, "org_id": org_id}, immutable=True
    )
    finalize_sig = celery_app.signature(
        "invoiceiq.finalize", kwargs={"invoice_id": invoice_id, "org_id": org_id}, immutable=True
    )
    return chain(first, extract_sig, validate_sig, confidence_sig, finalize_sig).apply_async()
