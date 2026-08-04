"""Invoice upload (skeleton): multipart upload -> store -> enqueue pipeline."""

from __future__ import annotations

import hashlib
import io
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from ...core.errors import ConflictError, ValidationFailure
from ...db import session_scope
from ...models import Invoice
from ...settings import get_settings
from ...storage import get_storage
from ...workers import run_pipeline
from ..deps import Principal, get_principal

router = APIRouter(prefix="/v1", tags=["invoices"])

ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".heic", ".zip"}


class UploadResult(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    duplicate_of: uuid.UUID | None = None


@router.post("/invoices", response_model=list[UploadResult], status_code=202)
async def upload_invoices(
    files: list[UploadFile] = File(...),
    principal: Principal = Depends(get_principal),
) -> list[UploadResult]:
    settings = get_settings()
    if not files or len(files) > settings.max_files_per_batch:
        raise ValidationFailure(f"expected 1..{settings.max_files_per_batch} files")
    if len(files) > 1:
        # Skeleton: single-file fast path; ZIP/multi-file expansion lands in Phase 1.
        raise ValidationFailure("bulk/zip upload arrives in Phase 1; upload one file for now")

    storage = get_storage()
    results: list[UploadResult] = []
    for upload in files:
        suffix = "." + (upload.filename or "").split(".")[-1].lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise ValidationFailure(f"unsupported format: {suffix}")
        data = await upload.read()
        if len(data) > settings.max_upload_bytes:
            raise ValidationFailure("file exceeds 20 MB limit")
        sha256 = hashlib.sha256(data).hexdigest()

        invoice_id = uuid.uuid4()
        with session_scope(org_id=str(principal.org_id)) as session:
            dup = (
                session.query(Invoice)
                .filter(Invoice.org_id == principal.org_id, Invoice.sha256 == sha256)
                .first()
            )
            if dup is not None:
                raise ConflictError("duplicate upload", detail={"duplicate_of": str(dup.id)})
            object_key = f"{principal.org_id}/{invoice_id}/{upload.filename}"
            invoice = Invoice(
                id=invoice_id,
                org_id=principal.org_id,
                object_key=object_key,
                sha256=sha256,
                filename=upload.filename or "unnamed",
                file_size=len(data),
                mime_type=upload.content_type or "application/octet-stream",
                source="upload",
                status="queued",
            )
            session.add(invoice)

        storage.put(object_key, io.BytesIO(data), content_type=upload.content_type)
        run_pipeline(str(invoice_id), str(principal.org_id), object_key, upload.filename or "unnamed")
        results.append(UploadResult(id=invoice_id, filename=upload.filename or "unnamed", status="queued"))
    return results
