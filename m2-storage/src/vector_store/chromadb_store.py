"""
ChromaDB implementation of BaseVectorStore (STUB -- real impl in Task 4).

WHY: This stub exists so factory.py can import ChromaDBStore without
needing the full ChromaDB dependency installed. When Task 4 implements
the real backend, it replaces this file with the full version.

All methods return empty/false values that satisfy the type contract
without requiring any external services. This allows unit tests for
the factory and manager to run without ChromaDB installed.
"""

from __future__ import annotations

from typing import Any

from contracts.document import Chunk

from .base import BaseVectorStore


class ChromaDBStore(BaseVectorStore):
    """
    Vector store backed by ChromaDB (embedded, persistent).

    ChromaDB was chosen as the Personal-mode default because it runs
    embedded in-process with no separate server dependency, supports
    persistent on-disk storage, and provides automatic index management.

    Full implementation in Task 4 will add:
    - chromadb.PersistentClient initialization
    - Collection create/load with HNSW index parameters
    - Batched insert with automatic ID generation
    - Cosine similarity search with metadata filtering
    - Bulk delete by document ID
    - Collection count with optional filter predicates
    """

    def __init__(self, config):
        self._config = config
        self._client = None
        self._collection = None

    async def initialize(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def close(self) -> None:
        pass

    async def insert(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> list[str]:
        return []

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        return []

    async def delete(self, doc_id: str) -> int:
        return 0

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        return 0
