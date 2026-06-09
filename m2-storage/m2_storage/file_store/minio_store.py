"""
MinIO / AWS S3 implementation of BaseFileStore.

WHAT: Implements BaseFileStore using minio-py (MinIO Python SDK) for
      S3-compatible object storage. Single implementation handles both:
      - MinIO: self-hosted, S3-compatible object store (Enterprise)
      - AWS S3: cloud object storage (SaaS)

WHY: MinIO/S3 is the recommended file store for Enterprise and SaaS
     deployments. Files stored in object storage are:
     - Shared across multiple application instances
     - Independently backed up (no data loss on instance restart)
     - Accessible via presigned URLs (no file server needed)

MINIO vs S3: Both use the same S3 API. The only difference is:
     - MinIO: endpoint = "minio.internal:9000", secure = False
     - AWS S3: endpoint = "" (auto-resolve), region = "us-east-1", secure = True
"""

from __future__ import annotations

import io
import logging
from typing import Any

from .base import BaseFileStore

logger = logging.getLogger(__name__)


class MinioS3Store(BaseFileStore):
    """File store backed by MinIO / AWS S3 object storage.

    WHAT: Stores files as S3 objects in a configurable bucket. Supports
          put/get/delete/list operations + presigned URLs for direct
          browser access without proxying through the application.

    PRESIGNED URLS: get_url() generates time-limited presigned download
    URLs. This is critical for the web UI — the browser downloads files
    directly from MinIO/S3, not through the M8 gateway, eliminating
    unnecessary network hops and memory usage.

    SECURITY: Access keys are stored in config (never in code). In
    production, use environment variable injection (${VAR} syntax)
    to avoid committing secrets to deploy.yaml.
    """

    def __init__(self, config):
        """Store config; client is created lazily in initialize()."""
        self._config = config
        self._client = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Connect to MinIO/S3 and ensure the bucket exists.

        WHAT:
        1. Create the Minio client with endpoint/credentials
        2. Check if the bucket exists; create it if not

        WHY idempotent: called at startup. Must not fail or create
        duplicate buckets if called multiple times.
        """
        try:
            from minio import Minio
        except ImportError:
            raise ImportError(
                "minio package not installed. "
                "Install with: pip install minio>=7.0.0"
            )

        cfg = self._config
        # Build endpoint: if endpoint is set, use it (MinIO).
        # If empty, region is used for AWS S3 auto-resolution.
        if cfg.endpoint:
            self._client = Minio(
                endpoint=cfg.endpoint,
                access_key=cfg.access_key,
                secret_key=cfg.secret_key,
                secure=cfg.secure,
            )
        else:
            # AWS S3: use region-based endpoint resolution
            self._client = Minio(
                endpoint=f"s3.{cfg.region}.amazonaws.com",
                access_key=cfg.access_key,
                secret_key=cfg.secret_key,
                secure=True,
            )

        # Ensure the bucket exists
        found = await self._run_sync(
            self._client.bucket_exists, cfg.bucket
        )
        if not found:
            await self._run_sync(
                self._client.make_bucket, cfg.bucket
            )
            logger.info("MinIO/S3 bucket created: %s", cfg.bucket)
        else:
            logger.info("MinIO/S3 bucket exists: %s", cfg.bucket)

    async def health_check(self) -> bool:
        """Verify bucket is accessible via bucket_exists().

        WHY: Uses bucket_exists (HEAD /bucket) which is O(1). More
             lightweight than listing objects and validates both
             connectivity AND permissions.
        """
        try:
            if self._client is None:
                return False
            result = await self._run_sync(
                self._client.bucket_exists, self._config.bucket
            )
            return result is True
        except Exception:
            logger.warning("MinIO/S3 health check failed")
            return False

    async def close(self) -> None:
        """Release the Minio client connection pool.

        WHAT: Minio client uses httpx connection pooling internally.
              Setting to None lets GC reclaim the pool.
        """
        self._client = None
        logger.info("MinIO/S3 store closed")

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    async def put(
        self, key: str, data: bytes,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Store a file as an S3 object.

        WHAT: Uploads data bytes as an S3 object with the given key.
              Optional metadata is stored as S3 object metadata.

        Returns the key on success.
        """
        self._require_safe_key(key)
        data_stream = io.BytesIO(data)

        await self._run_sync(
            self._client.put_object,
            bucket_name=self._config.bucket,
            object_name=key,
            data=data_stream,
            length=len(data),
            metadata=metadata or {},
        )
        return key

    async def get(self, key: str) -> bytes | None:
        """Retrieve a file's contents by key.

        Returns None if the object does not exist.
        """
        self._require_safe_key(key)

        try:
            response = await self._run_sync(
                self._client.get_object,
                bucket_name=self._config.bucket,
                object_name=key,
            )
            return response.read()
        except Exception as e:
            # Minio raises S3Error with code 'NoSuchKey' for missing objects
            if "NoSuchKey" in str(e) or "NoSuchBucket" in str(e):
                return None
            raise

    async def delete(self, key: str) -> bool:
        """Delete a file from the bucket.

        Returns True if deleted, False if it didn't exist.
        """
        self._require_safe_key(key)

        try:
            await self._run_sync(
                self._client.remove_object,
                bucket_name=self._config.bucket,
                object_name=key,
            )
            return True
        except Exception as e:
            if "NoSuchKey" in str(e):
                return False
            raise

    async def list(self, prefix: str = "") -> list[str]:
        """List all object keys under a given prefix.

        WHAT: Lists objects in the bucket with the given prefix.
              An empty prefix lists all objects.

        WHY: Used by admin UI to browse stored documents.
        """
        if prefix:
            self._require_safe_key(prefix.rstrip("/"))

        objects = await self._run_sync(
            self._client.list_objects,
            bucket_name=self._config.bucket,
            prefix=prefix or None,
            recursive=True,
        )

        keys = [obj.object_name for obj in objects]
        keys.sort()
        return keys

    async def get_url(self, key: str, expires_in: int = 3600) -> str | None:
        """Generate a presigned GET URL for the object.

        WHAT: Creates a time-limited presigned URL that allows direct
              browser download from MinIO/S3 without proxying through
              the M8 gateway.

        Returns None if the object doesn't exist.
        """
        self._require_safe_key(key)

        try:
            # First check if object exists
            await self._run_sync(
                self._client.stat_object,
                bucket_name=self._config.bucket,
                object_name=key,
            )
        except Exception:
            return None

        url = await self._run_sync(
            self._client.presigned_get_object,
            bucket_name=self._config.bucket,
            object_name=key,
            expires=self._config.presigned_expiry,
        )
        return url

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous minio-py method in the default executor.

        WHAT: Wraps minio-py's synchronous API with asyncio.to_thread
              so it doesn't block the event loop.

        WHY: minio-py is synchronous. We wrap it in asyncio.to_thread
             rather than using run_in_executor directly because it's
             cleaner and has proper cancellation support.
        """
        import asyncio
        return await asyncio.to_thread(func, *args, **kwargs)

    def _require_safe_key(self, key: str) -> None:
        """Reject S3 keys that contain obvious path traversal patterns.

        WHAT: S3 keys are object identifiers, not real filesystem paths,
              so the risk is lower than with LocalFS. However, we still
              reject '..' patterns because they can cause confusion when
              keys are downloaded to local filesystems.

        WHY: Defense-in-depth. Even though S3 doesn't have a directory
             tree to escape, rejecting '..' prevents confused deputy
             problems when keys are used as filenames on disk.
        """
        if ".." in key:
            raise ValueError(
                f"Unsafe storage key: '{key}'. "
                f"Keys must not contain '..' sequences."
            )
        if key.startswith("/"):
            raise ValueError(
                f"Unsafe storage key: '{key}'. "
                f"Keys must be relative (no leading slash)."
            )
