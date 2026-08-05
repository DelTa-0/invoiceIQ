"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import errors as api_errors
from .api.routers import auth_router, invoices_router, orgs_router, ws_router
from .settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="InvoiceIQ backend — EU-first AI accounts payable platform. "
        "OpenAPI: /v1/openapi.json",
        docs_url="/v1/docs" if not settings.is_production else None,
        redoc_url="/v1/redoc" if not settings.is_production else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_errors.register_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(invoices_router)
    app.include_router(orgs_router)
    app.include_router(ws_router)

    @app.get("/healthz", tags=["ops"], include_in_schema=False)
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/v1/openapi.json", include_in_schema=False)
    def openapi_json() -> dict:
        return app.openapi()

    return app


app = create_app()
