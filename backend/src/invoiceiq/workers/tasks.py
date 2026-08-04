"""Pipeline task stubs (Phase 0 skeleton).

The real OCR/extract/validate chain lands in Phase 1. Here we wire the
task DAG shape + state transitions so the API can enqueue and the worker
can run end-to-end against the queue.
"""

from __future__ import annotations

import uuid

import structlog
from celery.canvas import chain

from ..db import session_scope
from ..models import Invoice, ProcessingJob

logger = structlog.get_logger("invoiceiq.workers")


def _set_invoice_status(invoice_id: str, org_id: str, status: str) -> None:
    with session_scope(org_id=org_id) as session:
        invoice = session.get(Invoice, uuid.UUID(invoice_id))
        if invoice is None:
            return
        invoice.status = status
        invoice.total_conf = 0.0 if status == "processing" else invoice.total_conf


def _touch_job(invoice_id: str, org_id: str, stage: str, status: str, error: str | None = None) -> None:
    with session_scope(org_id=org_id) as session:
        job = ProcessingJob(
            invoice_id=uuid.UUID(invoice_id), stage=stage, status=status, error=error, attempt=1
        )
        session.add(job)


from .app import celery_app  # noqa: E402


@celery_app.task(bind=True, name="invoiceiq.ingest", max_retries=3, default_retry_delay=5)
def ingest(self, invoice_id: str, org_id: str, object_key: str, filename: str) -> dict:
    """Stage 1: claim the invoice and begin processing.

    Phase 1 replaces this with real normalization (zip/HEIC/PDF handling).
    """
    try:
        _set_invoice_status(invoice_id, org_id, "processing")
        _touch_job(invoice_id, org_id, "ingest", "done")
        logger.info("ingest ok", invoice_id=invoice_id, org_id=org_id, filename=filename)
        return {"invoice_id": invoice_id, "stage": "ingest", "status": "done"}
    except Exception as exc:
        _touch_job(invoice_id, org_id, "ingest", "failed", str(exc))
        raise self.retry(exc=exc) from exc


@celery_app.task(name="invoiceiq.finalize")
def finalize(invoice_id: str, org_id: str) -> dict:
    """Stage N (skeleton): mark the invoice completed.

    Phase 1 inserts ocr -> classify -> extract -> validate -> confidence
    between ingest and finalize (see docs/12 pipeline table).
    """
    _set_invoice_status(invoice_id, org_id, "completed")
    _touch_job(invoice_id, org_id, "finalize", "done")
    logger.info("finalize ok", invoice_id=invoice_id)
    return {"invoice_id": invoice_id, "stage": "finalize", "status": "done"}


def run_pipeline(invoice_id: str, org_id: str, object_key: str, filename: str):
    """Kick off the task chain for an invoice (immutable signatures, bound to our app)."""
    first = celery_app.signature(
        "invoiceiq.ingest",
        kwargs={"invoice_id": invoice_id, "org_id": org_id, "object_key": object_key, "filename": filename},
        immutable=True,
    )
    last = celery_app.signature(
        "invoiceiq.finalize", kwargs={"invoice_id": invoice_id, "org_id": org_id}, immutable=True
    )
    return chain(first, last).apply_async()
