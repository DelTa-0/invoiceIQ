"""Organization endpoints (skeleton): me + list invoices for the org."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...core.errors import NotFoundError
from ...db import session_scope
from ...models import Invoice, Organization
from ..deps import Principal, get_principal

router = APIRouter(prefix="/v1/orgs", tags=["orgs"])


class OrgOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    plan: str
    data_residency: str
    confidence_threshold: float


class InvoiceSummary(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    supplier_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    total: float | None = None
    total_conf: float | None = None


@router.get("/{org_id}", response_model=OrgOut)
def get_org(org_id: uuid.UUID, principal: Principal = Depends(get_principal)) -> OrgOut:
    if principal.org_id != org_id:
        raise NotFoundError("org not found")
    with session_scope() as session:
        org = session.get(Organization, org_id)
        if org is None:
            raise NotFoundError("org not found")
        return OrgOut(
            id=org.id,
            slug=org.slug,
            name=org.name,
            plan=org.plan,
            data_residency=org.data_residency,
            confidence_threshold=float(org.confidence_threshold),
        )


@router.get("/{org_id}/invoices", response_model=list[InvoiceSummary])
def list_invoices(org_id: uuid.UUID, principal: Principal = Depends(get_principal)) -> list[InvoiceSummary]:
    if principal.org_id != org_id:
        raise NotFoundError("org not found")
    with session_scope(org_id=str(org_id)) as session:
        rows = (
            session.query(Invoice)
            .filter(Invoice.org_id == org_id, Invoice.deleted_at.is_(None))
            .order_by(Invoice.created_at.desc())
            .limit(100)
            .all()
        )
        return [
            InvoiceSummary(
                id=r.id,
                filename=r.filename,
                status=r.status,
                supplier_name=r.supplier_name,
                invoice_number=r.invoice_number,
                invoice_date=str(r.invoice_date) if r.invoice_date else None,
                total=float(r.total) if r.total is not None else None,
                total_conf=float(r.total_conf) if r.total_conf is not None else None,
            )
            for r in rows
        ]
