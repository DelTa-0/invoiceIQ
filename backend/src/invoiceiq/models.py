"""SQLAlchemy ORM models — mirrors docs/04-database-schema.md.

Types are kept engine-portable (SQLite-compatible for tests). In production
PostgreSQL renders JSONB via variant; `citext` and RLS policies are applied
in the initial Alembic migration as database-specific steps.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JsonType = JSON().with_variant(JSONB(), "postgresql")


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


# ---------------------------------------------------------------------------
# Identity & tenancy
# ---------------------------------------------------------------------------


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(16), default="free")
    data_residency: Mapped[str] = mapped_column(String(16), default="eu_only")
    confidence_threshold: Mapped[float] = mapped_column(Numeric(5, 4), default=0.85)
    settings: Mapped[dict] = mapped_column(JsonType, default=dict)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    locale: Mapped[str] = mapped_column(String(8), default="en")
    mfa_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="active")


class OrgMember(Base):
    __tablename__ = "org_members"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_org_member"),)

    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="member")  # owner|admin|member|viewer
    status: Mapped[str] = mapped_column(String(16), default="active")


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))


# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("org_id", "normalized_name", name="uq_org_supplier"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255))
    vat_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    address: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    iban: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile: Mapped[dict] = mapped_column(JsonType, default=dict)
    flags: Mapped[dict] = mapped_column(JsonType, default=dict)


# ---------------------------------------------------------------------------
# Invoices & processing
# ---------------------------------------------------------------------------


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("suppliers.id"), nullable=True)
    object_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    file_size: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(16), default="upload")
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    doc_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    language: Mapped[str | None] = mapped_column(String(4), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    invoice_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supplier_vat: Mapped[str | None] = mapped_column(String(32), nullable=True)
    subtotal: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_vat: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    total: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_conf: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    review_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    review_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InvoicePage(Base):
    __tablename__ = "invoice_pages"
    __table_args__ = (UniqueConstraint("invoice_id", "page_no", name="uq_invoice_page"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    page_no: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    text_layer: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_engine: Mapped[str] = mapped_column(String(24), default="none")


class ProcessingJob(Base, TimestampMixin):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(24))  # ingest|ocr|classify|extract|validate|finalize
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExtractionField(Base, TimestampMixin):
    __tablename__ = "extraction_fields"
    __table_args__ = (UniqueConstraint("invoice_id", "field", name="uq_invoice_field"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    method: Mapped[str | None] = mapped_column(String(16), nullable=True)  # rules|llm|vlm|user
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    validator_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    validator_detail: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="accepted")
    edited_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LineItem(Base):
    __tablename__ = "line_items"
    __table_args__ = (UniqueConstraint("invoice_id", "position", name="uq_line_item_pos"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    discount_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    net: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    vat_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    vat_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    gross: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)


class ValidationCheck(Base, TimestampMixin):
    __tablename__ = "validation_checks"
    __table_args__ = (UniqueConstraint("invoice_id", "check_name", name="uq_invoice_check"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    check_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(8))  # pass|warn|fail
    severity: Mapped[str] = mapped_column(String(8), default="info")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JsonType, nullable=True)


class Correction(Base, TimestampMixin):
    __tablename__ = "corrections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(String(64))
    old_value: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    new_value: Mapped[dict] = mapped_column(JsonType)
    context: Mapped[dict] = mapped_column(JsonType, default=dict)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    applied: Mapped[bool] = mapped_column(Boolean, default=True)
    eval_candidate: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------------------
# API, webhooks, usage, billing
# ---------------------------------------------------------------------------


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    key_hash: Mapped[str] = mapped_column(String(64))
    key_prefix: Mapped[str] = mapped_column(String(16))
    scopes: Mapped[list] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Webhook(Base, TimestampMixin):
    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)
    secret: Mapped[str] = mapped_column(Text)
    events: Mapped[list] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class WebhookEvent(Base, TimestampMixin):
    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    webhook_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("webhooks.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JsonType)
    signature: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Export(Base, TimestampMixin):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(8))  # csv|xlsx|json|xml
    filters: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))  # page_processed|llm_call|export|api_call
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    meta: Mapped[dict] = mapped_column(JsonType, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(16), default="stripe")
    provider_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # free|starter|pro|enterprise
    pages_month: Mapped[int] = mapped_column(Integer)
    price_eur: Mapped[float] = mapped_column(Numeric(10, 2))
    features: Mapped[dict] = mapped_column(JsonType, default=dict)


# ---------------------------------------------------------------------------
# Audit (append-only)
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    actor_type: Mapped[str] = mapped_column(String(16))  # user|api_key|system
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delta: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
