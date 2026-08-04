"""S3-compatible storage backend (MinIO / Hetzner Object Storage / AWS S3).

boto3 is an optional runtime dependency, installed via the `s3` extra:
    pip install -e ".[s3]"
"""

from __future__ import annotations

import os
from typing import BinaryIO

from .base import Storage


class S3Storage(Storage):
    def __init__(self) -> None:
        import boto3  # pyright: ignore[reportMissingImports]  (optional 's3' extra)

        self._bucket = os.environ.get("IIQ_STORAGE_BUCKET", "invoices")
        self._client = boto3.client(
            "s3",
            endpoint_url=os.environ.get("IIQ_S3_ENDPOINT"),  # MinIO etc.
            region_name=os.environ.get("IIQ_S3_REGION", "eu-central-1"),
            aws_access_key_id=os.environ.get("IIQ_S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("IIQ_S3_SECRET_KEY"),
        )

    def put(self, key: str, data: BinaryIO, *, content_type: str | None = None) -> None:
        kwargs = {"ContentType": content_type} if content_type else {}
        self._client.upload_fileobj(data, self._bucket, key, ExtraArgs=kwargs or None)

    def get(self, key: str) -> bytes:
        body = self._client.get_object(Bucket=self._bucket, Key=key)["Body"]
        return body.read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def presign(self, key: str, *, ttl_seconds: int = 300) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )
