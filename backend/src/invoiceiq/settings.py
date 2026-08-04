"""Application settings, driven by environment variables (prefix IIQ_)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="IIQ_",
        extra="ignore",
    )

    # Core
    app_env: str = "development"  # development | staging | production
    app_name: str = "InvoiceIQ API"
    api_prefix: str = "/v1"
    debug: bool = False

    # Security
    secret_key: str = "dev-secret-change-me"
    encryption_key: str = "dev-encryption-key-32-bytes-minimum!!"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # Database / queue
    # App connects as a NON-superuser (RLS is bypassed for superusers) —
    # role created by infra/docker/init-db.sql.
    database_url: str = "postgresql+psycopg://invoiceiq_app:invoiceiq@localhost:5433/invoiceiq"
    redis_url: str = "redis://localhost:6379/0"

    # Storage
    storage_backend: str = "local"  # local | s3
    storage_root: str = "./var/storage"
    storage_bucket: str = "invoices"

    # LLM (default: EU — Mistral)
    llm_default_provider: str = "mistral"
    llm_api_key: str = ""

    # CORS (comma-separated; pydantic-settings parses list[str])
    cors_origins: list[str] = ["http://localhost:3000"]

    # Upload limits
    max_upload_bytes: int = 20 * 1024 * 1024
    max_files_per_batch: int = 100

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
