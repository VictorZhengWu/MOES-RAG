"""
Storage abstraction protocols (M2).

Defines the four storage interfaces that M2 implements
and all upper modules consume.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .document import Chunk, ParsedDocument


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """Interface for vector similarity search."""

    async def insert(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> list[str]:
        """Insert chunks with their embeddings. Returns chunk IDs."""
        ...

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Search by vector similarity. Returns (chunk, score) pairs."""
        ...

    async def delete(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document. Returns count deleted."""
        ...

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count total chunks, optionally filtered."""
        ...


@runtime_checkable
class DocumentIndexProtocol(Protocol):
    """Interface for full-text / keyword search (BM25, SPLADE, etc.)."""

    async def index(self, chunks: list[Chunk]) -> None:
        """Index chunks for full-text search."""
        ...

    async def search(
        self, query: str, top_k: int = 50, filters: dict[str, Any] | None = None
    ) -> list[tuple[Chunk, float]]:
        """Full-text search. Returns (chunk, score) pairs."""
        ...

    async def delete(self, doc_id: str) -> int:
        """Remove all entries for a document."""
        ...


@runtime_checkable
class RelationalDBProtocol(Protocol):
    """Interface for structured data (users, sessions, config, metadata).

    Implementations use SQLAlchemy under the hood.
    This protocol defines the lifecycle management methods.
    """

    async def get_session(self):
        """Return an async database session."""
        ...

    async def initialize(self) -> None:
        """Create all tables and run migrations."""
        ...

    async def health_check(self) -> bool:
        """Verify database connectivity."""
        ...


@runtime_checkable
class FileStoreProtocol(Protocol):
    """Interface for raw file storage."""

    async def put(self, key: str, data: bytes, metadata: dict[str, str] | None = None) -> str:
        """Store a file. Returns the storage key/path."""
        ...

    async def get(self, key: str) -> bytes | None:
        """Retrieve a file by key."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete a file by key."""
        ...

    async def list(self, prefix: str = "") -> list[str]:
        """List all keys under a prefix."""
        ...

    async def get_url(self, key: str, expires_in: int = 3600) -> str | None:
        """Get a presigned URL for the file (if supported by backend)."""
        ...
