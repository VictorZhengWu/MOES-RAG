"""
Local filesystem implementation of BaseFileStore.

WHY: LocalFS is the primary file store for Personal deployments. It
provides direct filesystem access with zero external dependencies,
storing files in a configurable root directory with metadata stored
as JSON sidecar files (.meta.json). Path traversal protection is
non-negotiable because user-provided keys are used to construct
filesystem paths.

Design decisions:
- Metadata is stored as .meta.json sidecar files -- no separate
  metadata database needed for Personal mode. This keeps the
  architecture simple and avoids introducing a DB dependency for
  what is fundamentally a filesystem concern.
- _is_safe_key() is a module-level function so it can be tested
  independently without constructing a store instance.
- _require_safe_key() is called at the top of every public method
  as a defense-in-depth measure alongside _resolve()'s realpath check.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import aiofiles
import aiofiles.os as aio_os

from .base import BaseFileStore


# =============================================================================
# Path safety utilities
# =============================================================================


def _is_safe_key(key: str) -> bool:
    """
    Check whether a user-provided key is safe for filesystem use.

    WHAT: Validates that a key does not contain path traversal sequences
    (..), is not an absolute path, and does not include Windows drive
    letters. Safe keys are relative paths using forward slashes.

    WHY: User-provided keys become filesystem paths. Without this check,
    a malicious key like '../../../etc/passwd' could read or overwrite
    arbitrary files outside the storage root.

    Args:
        key: The user-provided storage key to validate.

    Returns:
        True if the key is safe, False otherwise.
    """
    # Reject empty keys -- must identify a specific file
    if not key or not key.strip():
        return False

    # Normalize backslashes to forward slashes for consistent checking
    normalized = key.replace("\\", "/")

    # Reject absolute Unix paths (start with /)
    if normalized.startswith("/"):
        return False

    # Reject Windows drive letters (e.g., "C:" or "C:/")
    # A drive letter is a single alphabetic character followed by ':'
    if len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha():
        return False

    # Strip trailing slash for segment analysis -- prefix keys like
    # "docs/" are valid and should not trigger the empty-segment check.
    # The trailing slash only indicates a directory-like key.
    if normalized.endswith("/"):
        normalized = normalized.rstrip("/")

    # Reject path traversal: split on forward slash, check for ".." segments
    segments = normalized.split("/")
    if ".." in segments:
        return False

    # Reject empty segments (e.g., "foo//bar" or leading slashes that
    # survived earlier checks)
    if "" in segments:
        return False

    return True


# =============================================================================
# Main implementation
# =============================================================================


class LocalFSStore(BaseFileStore):
    """
    File store backed by the local filesystem.

    LocalFS was chosen as the Personal-mode default because it provides
    direct filesystem access with zero dependencies and no external
    services. Files are stored directly in a configurable root directory
    with metadata stored as .meta.json sidecar files alongside the data.

    Security: Every public method validates keys via _require_safe_key()
    and _resolve() performs a realpath check as defense-in-depth.
    """

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def __init__(self, config):
        """
        Initialize the LocalFS store with configuration.

        WHAT: Stores the config and computes the root Path object.
        WHY: We resolve root_dir eagerly so that any invalid path
        configuration is caught early, not lazily during first use.

        Args:
            config: A LocalFSConfig instance with root_dir set.
        """
        self._config = config
        self._root = Path(config.root_dir).resolve()

    async def initialize(self) -> None:
        """
        Ensure the storage root directory exists.

        WHAT: Creates the root directory (and all parent directories)
        if they do not already exist.
        WHY: Failing early if the directory cannot be created prevents
        silent errors during actual file operations. The exist_ok=True
        flag makes this idempotent -- safe to call multiple times.
        """
        self._root.mkdir(parents=True, exist_ok=True)

    async def health_check(self) -> bool:
        """
        Verify that the storage root is readable and writable.

        WHAT: Writes a small probe file to the root directory and
        immediately deletes it. Returns True if both operations succeed.
        WHY: A real read-write test catches filesystem mount issues,
        permission problems, and disk-full conditions that a simple
        os.access() check would miss.

        Returns:
            True if the root directory is accessible and writable.
        """
        probe = self._root / ".health_check_probe"
        try:
            # Write a small probe to confirm the filesystem is writable
            async with aiofiles.open(probe, "wb") as f:
                await f.write(b"ok")
            # Clean up immediately -- probe should not persist
            await aio_os.remove(probe)
            return True
        except (OSError, IOError):
            return False

    async def close(self) -> None:
        """
        Release any held resources.

        WHAT: No-op for local filesystem. There are no connection pools
        or file handles to release.
        WHY: The method exists to satisfy the BaseFileStore lifecycle
        contract. S3/MinIO backends use it to close HTTP pools.
        """
        pass

    # -------------------------------------------------------------------------
    # CRUD operations
    # -------------------------------------------------------------------------

    async def put(
        self, key: str, data: bytes,
        metadata: dict[str, str] | None = None
    ) -> str:
        """
        Store a file on the local filesystem.

        WHAT: Writes the given data bytes to a file at the resolved path
        under the storage root. If metadata is provided, writes it as a
        JSON sidecar file at ``{key}.meta.json``. Returns the key
        unchanged on success.

        WHY: Asynchronous I/O via aiofiles prevents blocking the event
        loop during disk writes. The sidecar pattern keeps metadata
        alongside the file without requiring a separate database.

        Args:
            key: Relative storage key (e.g., "docs/report.pdf").
                 Must pass _is_safe_key validation.
            data: Raw bytes to store.
            metadata: Optional dict of string key-value pairs stored
                      alongside the file as JSON.

        Returns:
            The storage key (identical to the input key).

        Raises:
            ValueError: If the key contains path traversal sequences.
        """
        self._require_safe_key(key)
        file_path = self._resolve(key)

        # Ensure parent directories exist before writing the file
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file contents asynchronously
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(data)

        # Write metadata sidecar if provided
        if metadata is not None:
            meta_path = file_path.parent / (file_path.name + ".meta.json")
            async with aiofiles.open(meta_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(metadata, ensure_ascii=False))

        return key

    async def get(self, key: str) -> bytes | None:
        """
        Retrieve a file's contents by key.

        WHAT: Reads the file at the resolved path and returns its raw
        bytes. Returns None if the file does not exist.
        WHY: None-return semantics (rather than raising an exception)
        match the FileStoreProtocol contract and let callers distinguish
        "file not found" from "I/O error" without try/except.

        Args:
            key: The storage key to retrieve.

        Returns:
            File contents as bytes, or None if the file does not exist.

        Raises:
            ValueError: If the key contains path traversal sequences.
        """
        self._require_safe_key(key)
        file_path = self._resolve(key)

        # Return None for missing files -- not an error condition
        if not file_path.is_file():
            return None

        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> bool:
        """
        Delete a file and its metadata sidecar.

        WHAT: Removes the file at the resolved path and, if present,
        its associated .meta.json sidecar file. Returns True if the
        data file existed and was deleted.
        WHY: Deleting the sidecar along with the data prevents orphaned
        metadata files from accumulating. The method is tolerant of
        missing files -- it returns False rather than raising.

        Args:
            key: The storage key to delete.

        Returns:
            True if the file existed and was deleted, False if it
            did not exist.

        Raises:
            ValueError: If the key contains path traversal sequences.
        """
        self._require_safe_key(key)
        file_path = self._resolve(key)

        existed = file_path.is_file()

        # Remove the data file if it exists
        if existed:
            await aio_os.remove(file_path)

        # Remove the metadata sidecar if it exists (best-effort)
        meta_path = file_path.parent / (file_path.name + ".meta.json")
        if meta_path.is_file():
            await aio_os.remove(meta_path)

        return existed

    async def list(self, prefix: str = "") -> list[str]:
        """
        List all file keys under a given prefix.

        WHAT: Walks the filesystem tree under the resolved prefix
        directory and returns relative keys for all regular files,
        excluding .meta.json sidecar files.

        WHY: Excluding .meta.json files prevents the sidecars from
        appearing alongside their data files in listings. Callers
        should only see the actual data keys.

        Args:
            prefix: Optional directory prefix (e.g., "docs/").
                    An empty string lists all files.

        Returns:
            List of relative storage keys (using forward slashes).

        Raises:
            ValueError: If the key contains path traversal sequences.
        """
        # Allow empty prefix (list all files)
        if prefix:
            self._require_safe_key(prefix)

        base_dir = self._resolve(prefix) if prefix else self._root

        # If the prefix directory does not exist, there are no files to list
        if not base_dir.is_dir():
            return []

        keys: list[str] = []
        base_str = str(self._root)

        for dirpath, _dirnames, filenames in os.walk(str(base_dir)):
            for fname in filenames:
                # Skip metadata sidecar files -- these are internal
                if fname.endswith(".meta.json"):
                    continue
                full_path = os.path.join(dirpath, fname)
                # Compute the relative key from the storage root
                rel = os.path.relpath(full_path, base_str)
                # Normalize Windows backslashes to forward slashes
                key = rel.replace("\\", "/")
                keys.append(key)

        # Sort for deterministic output
        keys.sort()
        return keys

    async def get_url(self, key: str, expires_in: int = 3600) -> str | None:
        """
        Return a file:// URI for the stored file.

        WHAT: Converts the resolved absolute path to a file:// URI.
        The expires_in parameter is accepted for protocol compliance
        but has no effect -- local files do not expire.
        WHY: file:// URIs allow the web UI to display local files
        without copying them. Other backends (S3/MinIO) use this
        method to generate time-limited presigned URLs.

        Args:
            key: The storage key.
            expires_in: Ignored for local files (no expiry).

        Returns:
            A file:// URI string, or None if the file does not exist.

        Raises:
            ValueError: If the key contains path traversal sequences.
        """
        self._require_safe_key(key)
        file_path = self._resolve(key)

        if not file_path.is_file():
            return None

        # Path.as_uri() produces "file:///C:/..." on Windows and
        # "file:///path/to/file" on Unix -- both are valid.
        return file_path.as_uri()

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _resolve(self, key: str) -> Path:
        """
        Resolve a storage key to an absolute path under the root.

        WHAT: Joins the key with the storage root, then calls
        realpath() to resolve any symlinks. Finally validates that
        the resolved path is still within the storage root.
        WHY: This is defense-in-depth against path traversal. Even if
        _is_safe_key() were bypassed, realpath() + prefix check would
        catch symlink-based escapes.

        Args:
            key: A relative storage key.

        Returns:
            An absolute Path within the storage root.

        Raises:
            ValueError: If the resolved path escapes the storage root.
        """
        raw = self._root / key
        resolved = Path(os.path.realpath(str(raw)))

        # Defense-in-depth: ensure the resolved path (after symlink
        # expansion) is still within the storage root.
        root_resolved = Path(os.path.realpath(str(self._root)))
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            raise ValueError(
                f"Path traversal detected: key '{key}' resolves to "
                f"'{resolved}' which is outside the storage root "
                f"'{root_resolved}'."
            )

        return resolved

    def _require_safe_key(self, key: str) -> None:
        """
        Validate that a key is safe for filesystem use.

        WHAT: Calls _is_safe_key() and raises ValueError if the key
        is unsafe. Called at the top of every public method.
        WHY: This is the first line of defense -- it catches obviously
        malicious keys before any filesystem operation is attempted.

        Args:
            key: The storage key to validate.

        Raises:
            ValueError: If the key contains path traversal sequences,
                        is absolute, or includes Windows drive letters.
        """
        if not _is_safe_key(key):
            raise ValueError(
                f"Unsafe storage key (path traversal): '{key}'. "
                f"Keys must not contain '..', be absolute paths, or "
                f"include Windows drive letters. Use relative paths "
                f"with forward slashes, e.g. 'docs/report.pdf'."
            )
