"""Audit logging — append-only by contract (DB trigger in migration)."""

from __future__ import annotations

import uuid
from typing import Any

from ..db import session_scope
from ..models import AuditLog


def write(
    *,
    org_id: uuid.UUID,
    action: str,
    resource: str,
    resource_id: str | None = None,
    delta: dict | None = None,
    actor_type: str = "user",
    actor_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Append an audit event. Best-effort: never raises into the caller's flow."""
    try:
        with session_scope() as session:
            session.add(
                AuditLog(
                    org_id=org_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action=action,
                    resource=resource,
                    resource_id=resource_id,
                    delta=delta,
                    ip=ip,
                    user_agent=user_agent,
                )
            )
    except Exception:  # pragma: no cover - audit must never break business flow
        # Structured logging hook point; swap to structlog in prod.
        import logging

        logging.getLogger("invoiceiq.audit").exception("failed to write audit log")


def record_from_request(
    org_id: uuid.UUID,
    action: str,
    resource: str,
    resource_id: str | None = None,
    delta: dict | None = None,
    actor_type: str = "user",
    actor_id: uuid.UUID | None = None,
    request: Any | None = None,
) -> None:
    """Convenience wrapper extracting ip/user_agent from a Starlette Request."""
    ip = user_agent = None
    if request is not None:
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    write(
        org_id=org_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        delta=delta,
        actor_type=actor_type,
        actor_id=actor_id,
        ip=ip,
        user_agent=user_agent,
    )
