"""Local disk storage backend (dev only). Keys are org-scoped by convention."""

import uuid
from pathlib import Path
from typing import BinaryIO

from .base import Storage


class LocalStorage(Storage):
    def __init__(self, root: str | None = None, bucket: str | None = None):
        from ..settings import get_settings

        settings = get_settings()
        self._root = Path(root or settings.storage_root)
        self._bucket = bucket or settings.storage_bucket
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = Path(key)
        target = (self._root / self._bucket / safe).resolve()
        if not target.is_relative_to(self._root.resolve()):
            raise ValueError(f"unsafe storage key: {key}")
        return target

    def put(self, key: str, data: BinaryIO, *, content_type: str | None = None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            f.write(data.read())

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def presign(self, key: str, *, ttl_seconds: int = 300) -> str:
        # Dev only: return a tokenized local path. Real backends produce real presigned URLs.
        token = uuid.uuid4().hex
        path = self._path(key)
        return f"local://{token}?path={path}"


def build_key(org_id: str, invoice_id: str, filename: str) -> str:
    return f"{org_id}/{invoice_id}/{filename}"
