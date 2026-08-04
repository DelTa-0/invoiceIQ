"""Auth + account endpoints (skeleton): register, login, refresh, me."""

from __future__ import annotations

import time
import uuid

import jwt
import pwdlib
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from ...core.errors import ConflictError, UnauthorizedError, ValidationFailure
from ...db import session_scope
from ...models import Organization, OrgMember, User
from ...settings import get_settings
from ..deps import Principal, get_principal

router = APIRouter(prefix="/v1/auth", tags=["auth"])

password_hasher = pwdlib.PasswordHash.recommended()


def _make_token(user_id: uuid.UUID, org_id: uuid.UUID, role: str, type_: str) -> str:
    settings = get_settings()
    ttl = (
        settings.access_token_ttl_minutes * 60
        if type_ == "access"
        else settings.refresh_token_ttl_days * 24 * 3600
    )
    return jwt.encode(
        {"sub": str(user_id), "org_id": str(org_id), "role": role, "type": type_, "exp": time.time() + ttl},
        settings.secret_key,
        algorithm="HS256",
    )


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = ...  # type: ignore[assignment]
    full_name: str
    org_name: str


class RegisterResponse(BaseModel):
    access_token: str
    refresh_token: str
    org_id: uuid.UUID


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(body: RegisterRequest) -> RegisterResponse:
    if len(body.password) < 10:
        raise ValidationFailure("password must be at least 10 characters")
    with session_scope() as session:
        if session.query(User).filter(User.email == body.email).first():
            raise ConflictError("email already registered")
        user = User(
            email=str(body.email).lower(),
            password_hash=password_hasher.hash(body.password),
            full_name=body.full_name,
        )
        session.add(user)
        session.flush()

        slug_base = "".join(c for c in body.org_name.lower() if c.isalnum() or c == "-") or "org"
        org = Organization(slug=f"{slug_base}-{uuid.uuid4().hex[:6]}", name=body.org_name)
        session.add(org)
        session.flush()
        session.add(OrgMember(org_id=org.id, user_id=user.id, role="owner"))
        org_id = org.id
        user_id = user.id
    return RegisterResponse(
        access_token=_make_token(user_id, org_id, "owner", "access"),
        refresh_token=_make_token(user_id, org_id, "owner", "refresh"),
        org_id=org_id,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    with session_scope() as session:
        user = session.query(User).filter(User.email == str(body.email).lower()).first()
        if user is None or user.password_hash is None or not password_hasher.verify(body.password, user.password_hash):
            raise UnauthorizedError("invalid credentials")
        membership = (
            session.query(OrgMember).filter(OrgMember.user_id == user.id, OrgMember.status == "active").first()
        )
        if membership is None:
            raise UnauthorizedError("no active membership")
        org_id, role, user_id = membership.org_id, membership.role, user.id
    return TokenResponse(
        access_token=_make_token(user_id, org_id, role, "access"),
        refresh_token=_make_token(user_id, org_id, role, "refresh"),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest) -> TokenResponse:
    settings = get_settings()
    try:
        claims = jwt.decode(body.refresh_token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("invalid refresh token") from exc
    if claims.get("type") != "refresh":
        raise UnauthorizedError("not a refresh token")
    return TokenResponse(
        access_token=_make_token(uuid.UUID(claims["sub"]), uuid.UUID(claims["org_id"]), claims.get("role", "member"), "access"),
        refresh_token=_make_token(uuid.UUID(claims["sub"]), uuid.UUID(claims["org_id"]), claims.get("role", "member"), "refresh"),
    )


@router.get("/me")
def me(principal: Principal = Depends(get_principal)) -> dict:
    with session_scope() as session:
        user = session.get(User, principal.user_id)
        if user is None:
            raise UnauthorizedError("user not found")
        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "locale": user.locale,
            "org_id": str(principal.org_id),
            "role": principal.role,
        }
