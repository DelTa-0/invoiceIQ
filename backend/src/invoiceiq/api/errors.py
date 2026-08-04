"""FastAPI exception handlers mapping domain errors to the error envelope."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..core.errors import DomainError


def _body(exc: DomainError, request_id: str | None) -> dict:
    return {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "detail": exc.detail or {},
            "request_id": request_id,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        request_id = request.headers.get("x-request-id")
        return JSONResponse(status_code=exc.http_status, content=_body(exc, request_id))
