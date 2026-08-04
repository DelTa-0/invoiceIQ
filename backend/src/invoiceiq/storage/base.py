"""Object storage abstraction. Prod uses S3-compatible (MinIO/Hetzner/AWS);
dev uses the local disk backend to save RAM."""

from abc import ABC, abstractmethod
from typing import BinaryIO


class Storage(ABC):
    @abstractmethod
    def put(self, key: str, data: BinaryIO, *, content_type: str | None = None) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def presign(self, key: str, *, ttl_seconds: int = 300) -> str: ...


def get_storage() -> Storage:
    from ..settings import get_settings

    settings = get_settings()
    if settings.storage_backend == "s3":
        from .s3 import S3Storage

        return S3Storage()
    from .local import LocalStorage

    return LocalStorage()
