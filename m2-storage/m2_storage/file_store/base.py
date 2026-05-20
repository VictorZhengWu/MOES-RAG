"""
Base class for file store backends.

WHY: Adds lifecycle methods to FileStoreProtocol. File storage is the
most security-sensitive backend (direct filesystem or object store
access), so all implementations must include path traversal protection
and access control. The base class enforces this by documenting the
security contract that all subclasses must fulfill.
"""

from abc import ABC, abstractmethod

from contracts.storage import FileStoreProtocol


class BaseFileStore(FileStoreProtocol, ABC):
    """
    Abstract file store with lifecycle management.

    All file store backends (Local FS, MinIO/S3, etc.) inherit from
    this class. Implementations are responsible for:
    - Path traversal prevention (reject ".." and absolute paths in keys)
    - Storage root isolation (no access outside configured root_dir)
    - Consistent key-to-path mapping

    Lifecycle hooks:
    - initialize(): ensure storage root exists and is writable
    - health_check(): verify storage is accessible
    - close(): release any held resources
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Ensure storage root exists and is writable.

        Creates the root directory if it does not exist. Fails early
        if the configured path is not writable, preventing silent
        failures during actual file operations.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify storage is accessible.

        Typically writes and deletes a small test file to confirm
        the filesystem is mounted and writable.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """
        Release any held resources.

        For local filesystem backends this is usually a no-op.
        For S3/MinIO backends this closes the HTTP connection pool.
        """
        ...
