"""Auth dependencies: JWT bearer, org context, RBAC."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.errors import ForbiddenError, UnauthorizedError
from ..settings import get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str
    token_type: str  # access | api_key


def _decode(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("invalid token") from exc


async def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None:
        raise UnauthorizedError("missing credentials")
    claims = _decode(credentials.credentials)
    if claims.get("type") not in ("access", "api_key"):
        raise UnauthorizedError("invalid token type")
    try:
        return Principal(
            user_id=uuid.UUID(claims["sub"]),
            org_id=uuid.UUID(claims["org_id"]),
            role=claims.get("role", "member"),
            token_type=claims["type"],
        )
    except KeyError as exc:
        raise UnauthorizedError("malformed token") from exc


def require_role(*roles: str):
    def dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in roles:
            raise ForbiddenError(f"requires role in {roles}")
        return principal

    return dep


def require_org_membership(request: Request, principal: Principal = Depends(get_principal)) -> Principal:
    """Skeleton: org scope comes from the token. Full membership re-check +
    RLS enforcement arrive with the DB-backed auth (Phase 0 hardening)."""
    if not request:
        raise ForbiddenError("request required")
    return principal
