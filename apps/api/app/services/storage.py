"""Object storage for recordings and knowledge documents.

Local filesystem by default so development and tests need no cloud credentials; S3 when
the STORAGE_* settings are present. The interface is small on purpose: put, get a signed
URL, delete.
"""

from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("storage")


class StorageError(Exception):
    pass


class StorageProvider(ABC):
    @abstractmethod
    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        """Store bytes and return the key."""

    @abstractmethod
    def url_for(self, key: str) -> str:
        """A retrievable URL for the stored object."""

    @abstractmethod
    async def delete(self, key: str) -> None: ...


class LocalStorage(StorageProvider):
    """Filesystem-backed storage rooted at `LOCAL_STORAGE_DIR`."""

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.local_storage_dir).resolve()

    def _path(self, key: str) -> Path:
        # Reject traversal: keys come from user-supplied filenames.
        safe = Path(key).as_posix().lstrip("/")
        target = (self.root / safe).resolve()
        if not target.is_relative_to(self.root):
            raise StorageError(f"Refusing to write outside the storage root: {key}")
        return target

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def url_for(self, key: str) -> str:
        return f"/files/{self._path(key).relative_to(self.root).as_posix()}"

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()


class S3Storage(StorageProvider):
    """S3-compatible object storage (AWS S3, MinIO, R2)."""

    def __init__(
        self,
        *,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self._client: object | None = None

    def _get_client(self) -> Any:
        """Lazily build the boto3 S3 client. Typed as Any: boto3 ships no stubs."""
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - depends on optional extra
                raise StorageError("boto3 is required for S3 storage") from exc
            self._client = boto3.client(
                "s3",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                endpoint_url=self.endpoint_url,
            )
        return self._client

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        extra = {"ContentType": content_type} if content_type else {}
        self._get_client().put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
        return key

    def url_for(self, key: str) -> str:
        # Presigned GET so recordings stay private to the tenant.
        return str(
            self._get_client().generate_presigned_url(
                "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=3600
            )
        )

    async def delete(self, key: str) -> None:
        self._get_client().delete_object(Bucket=self.bucket, Key=key)


@lru_cache
def get_storage() -> StorageProvider:
    """S3 when configured, otherwise local filesystem."""
    if settings.storage_bucket and settings.storage_access_key:
        logger.info("storage_s3_enabled", bucket=settings.storage_bucket)
        return S3Storage(
            bucket=settings.storage_bucket,
            access_key=settings.storage_access_key,
            secret_key=settings.storage_secret_key,
            region=settings.storage_region or None,
            endpoint_url=settings.storage_endpoint_url or None,
        )
    logger.info("storage_local_enabled", root=settings.local_storage_dir)
    return LocalStorage()
