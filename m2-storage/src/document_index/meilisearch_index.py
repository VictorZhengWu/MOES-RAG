"""
Meilisearch implementation of BaseDocumentIndex (STUB -- real impl in Task 5).

WHY: This stub allows factory.py to import MeilisearchIndex without
requiring the Meilisearch Python SDK to be installed. The full
implementation in Task 5 will add real indexing with configurable
ranking rules, filterable attributes, and hybrid search support.

All stub methods are no-ops that satisfy the type contract.
"""

from __future__ import annotations

from typing import Any

from contracts.document import Chunk

from .base import BaseDocumentIndex


class MeilisearchIndex(BaseDocumentIndex):
    """
    Document index backed by Meilisearch (self-hosted or Cloud).

    Meilisearch was chosen as the Personal-mode default because it runs
    as a single binary with near-zero configuration, provides typo-tolerant
    full-text search out of the box, and supports filtering/faceting
    needed for regulation metadata search.

    Full implementation in Task 5 will add:
    - meilisearch.Client initialization with API key auth
    - Index creation with filterable/sortable attribute configuration
    - Document-level upsert (creates or replaces)
    - Typo-tolerant search with metadata filtering
    - Deletion by document ID filter
    """

    def __init__(self, config):
        self._config = config
        self._client = None

    async def initialize(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def close(self) -> None:
        pass

    async def index(self, chunks: list[Chunk]) -> None:
        pass

    async def search(
        self, query: str, top_k: int = 50,
        filters: dict[str, Any] | None = None
    ) -> list[tuple[Chunk, float]]:
        return []

    async def delete(self, doc_id: str) -> int:
        return 0
