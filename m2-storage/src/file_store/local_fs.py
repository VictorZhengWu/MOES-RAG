"""
Local filesystem implementation of BaseFileStore (STUB -- real impl in Task 7).

WHY: This stub allows factory.py to import LocalFSStore without needing
the full filesystem operations. Task 7 replaces this with the complete
implementation including path traversal protection, atomic writes, and
directory sharding for large file counts.

All stub methods return empty/false/None values that satisfy the type
contract without touching the filesystem.
"""

from __future__ import annotations

from .base import BaseFileStore


class LocalFSStore(BaseFileStore):
    """
    File store backed by the local filesystem.

    LocalFS was chosen as the Personal-mode default because it provides
    direct filesystem access with zero dependencies and no external
    services. Files are stored directly in a configurable root directory.

    Full implementation in Task 7 will add:
    - Path traversal protection (reject ".." and absolute paths)
    - Atomic writes via temp file + os.replace
    - Directory sharding (split keys into subdirectories)
    - File metadata storage alongside content
    - Content-type detection and storage
    """

    def __init__(self, config):
        self._config = config

    async def initialize(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def close(self) -> None:
        pass

    async def put(
        self, key: str, data: bytes,
        metadata: dict[str, str] | None = None
    ) -> str:
        return key

    async def get(self, key: str) -> bytes | None:
        return None

    async def delete(self, key: str) -> bool:
        return False

    async def list(self, prefix: str = "") -> list[str]:
        return []

    async def get_url(self, key: str, expires_in: int = 3600) -> str | None:
        return None
