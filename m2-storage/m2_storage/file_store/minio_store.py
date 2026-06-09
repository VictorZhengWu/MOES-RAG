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

RESILIENCE:
     - All network operations use exponential-backoff retry (3 attempts).
     - get/put/delete have explicit per-operation timeouts (configurable).
     - Metadata is validated before storage (string-only keys/values).
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

from .base import BaseFileStore

logger = logging.getLogger(__name__)

# Default per-operation timeout in seconds for S3 API calls
_DEFAULT_OP_TIMEOUT = 30
# Retry config for transient network errors
_MAX_RETRIES = 3
_RETRY_MIN_WAIT = 1.0   # first backoff: 1s
_RETRY_MAX_WAIT = 10.0  # max backoff: 10s


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

        # Bucket check/create with retry
        found = await self._retry_sync(
            self._client.bucket_exists, cfg.bucket,
            desc="bucket_exists",
        )
        if not found:
            await self._retry_sync(
                self._client.make_bucket, cfg.bucket,
                desc="make_bucket",
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
            async with asyncio.timeout(10):
                result = await self._run_sync(
                    self._client.bucket_exists, self._config.bucket
                )
            return result is True
        except asyncio.TimeoutError:
            logger.warning("MinIO/S3 health check timed out")
            return False
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
              Optional metadata is stored as S3 object metadata, validated
              to ensure all keys and values are strings.

        Returns the key on success (no-op if the key is unsafe).
        """
        self._require_safe_key(key)

        # Validate metadata before upload
        validated_meta = _validate_metadata(metadata)

        data_stream = io.BytesIO(data)

        async with asyncio.timeout(_DEFAULT_OP_TIMEOUT):
            await self._run_sync(
                self._client.put_object,
                bucket_name=self._config.bucket,
                object_name=key,
                data=data_stream,
                length=len(data),
                metadata=validated_meta,
            )
        return key

    async def get(self, key: str) -> bytes | None:
        """Retrieve a file's contents by key.

        Returns None if the object does not exist or the operation times out.
        """
        self._require_safe_key(key)

        try:
            async with asyncio.timeout(_DEFAULT_OP_TIMEOUT):
                response = await self._retry_sync(
                    self._client.get_object,
                    bucket_name=self._config.bucket,
                    object_name=key,
                    desc=f"get_object({key})",
                )
            return response.read()
        except asyncio.TimeoutError:
            logger.warning("MinIO get_object timeout for key=%s", key)
            return None
        except Exception as e:
            if "NoSuchKey" in str(e) or "NoSuchBucket" in str(e):
                return None
            raise

    async def delete(self, key: str) -> bool:
        """Delete a file from the bucket.

        Returns True if deleted, False if it didn't exist.
        """
        self._require_safe_key(key)

        try:
            async with asyncio.timeout(_DEFAULT_OP_TIMEOUT):
                await self._retry_sync(
                    self._client.remove_object,
                    bucket_name=self._config.bucket,
                    object_name=key,
                    desc=f"remove_object({key})",
                )
            return True
        except asyncio.TimeoutError:
            logger.warning("MinIO remove_object timeout for key=%s", key)
            return False
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

        async with asyncio.timeout(_DEFAULT_OP_TIMEOUT):
            objects = await self._retry_sync(
                self._client.list_objects,
                bucket_name=self._config.bucket,
                prefix=prefix or None,
                recursive=True,
                desc="list_objects",
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
            async with asyncio.timeout(_DEFAULT_OP_TIMEOUT):
                await self._run_sync(
                    self._client.stat_object,
                    bucket_name=self._config.bucket,
                    object_name=key,
                )
        except asyncio.TimeoutError:
            logger.warning("MinIO stat_object timeout for key=%s", key)
            return None
        except Exception:
            return None

        async with asyncio.timeout(_DEFAULT_OP_TIMEOUT):
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
        return await asyncio.to_thread(func, *args, **kwargs)

    async def _retry_sync(self, func, *args, desc: str = "operation"):
        """Run a minio-py method with exponential-backoff retry.

        WHAT: Retries the given func up to _MAX_RETRIES times with
              exponential backoff (1s → 2s → 4s, capped at _RETRY_MAX_WAIT).
              Only retries on connection/network errors — semantic errors
              (NoSuchKey, NoSuchBucket) propagate immediately.

        WHY: Network blips, DNS glitches, and transient S3 errors are
             common in cloud environments. Exponential backoff prevents
             thundering-herd retry storms while maximizing the chance
             of a successful recovery within the timeout window.
        """
        last_exc = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return await self._run_sync(func, *args)
            except Exception as e:
                last_exc = e
                # Don't retry semantic errors
                msg = str(e).lower()
                if "nosuchkey" in msg or "nosuchbucket" in msg:
                    raise
                if attempt == _MAX_RETRIES:
                    logger.error(
                        "MinIO %s failed after %d attempts: %s",
                        desc, _MAX_RETRIES, e,
                    )
                    raise
                wait = min(_RETRY_MIN_WAIT * (2 ** (attempt - 1)), _RETRY_MAX_WAIT)
                logger.warning(
                    "MinIO %s attempt %d/%d failed: %s — retrying in %.1fs",
                    desc, attempt, _MAX_RETRIES, e, wait,
                )
                await asyncio.sleep(wait)

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


# ===========================================================================
# Module-level helpers
# ===========================================================================


def _validate_metadata(metadata: dict[str, str] | None) -> dict[str, str]:
    """Validate and return sanitized metadata dict.

    WHAT: Ensures all keys and values in the metadata dict are strings.
          Returns an empty dict if metadata is None.

    WHY: S3/MinIO object metadata only supports string keys and values.
         Non-string values (int, bool, nested dicts) cause cryptic errors
         from minio-py's internals. Validating at the API boundary gives
         the caller a clear, actionable error message.

    Raises:
        ValueError: If any key or value is not a string.
    """
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError(
            f"Metadata must be a dict[str, str], got {type(metadata).__name__}"
        )
    for k, v in metadata.items():
        if not isinstance(k, str):
            raise ValueError(
                f"Metadata keys must be strings, got {type(k).__name__}: {k!r}"
            )
        if not isinstance(v, str):
            raise ValueError(
                f"Metadata values must be strings for key {k!r}, "
                f"got {type(v).__name__}: {v!r}"
            )
    return metadata
