"""
Meilisearch implementation of BaseDocumentIndex.

WHY: Meilisearch is the Personal-mode default full-text search engine.
It provides fast, typo-tolerant BM25 keyword search without requiring
Elasticsearch's operational complexity. For regulation clause lookups
(e.g., "DNV Pt.4 Ch.3 §5"), keyword search is more precise than
dense embeddings alone.

Key design decisions:
- Filter syntax: flat dict -> Meilisearch SQL-like filter expression
  {"domain": "structure"} becomes 'domain = "structure"'
- searchableAttributes: ["text"] -- only chunk text is searchable
- filterableAttributes: ["doc_id", "source_filename", "domain",
  "chunk_type", "language"] -- metadata columns used in WHERE clauses
- sortableAttributes: ["position"] -- for ordering by document position
- doc_id is derived from source_filename (strip ".pdf") so delete()
  by doc_id works consistently with how M1 names documents
"""

from __future__ import annotations

import logging
from typing import Any

import meilisearch

from contracts.document import Chunk, DocumentMetadata, Domain

from .base import BaseDocumentIndex

logger = logging.getLogger(__name__)


class MeilisearchIndex(BaseDocumentIndex):
    """Document index backed by Meilisearch (BM25 full-text search).

    Supports: full-text search with typo tolerance, metadata filtering,
    batch indexing, and deletion by document ID. Designed for Personal
    deployments where running a separate Elasticsearch cluster would be
    overkill.
    """

    def __init__(self, config):
        """Store config for lazy initialization in initialize()."""
        self._config = config
        self._client: meilisearch.Client | None = None
        self._index: meilisearch.Index | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Connect to Meilisearch, create or verify index, configure fields.

        WHAT:
        1. Create a Meilisearch HTTP client
        2. Get or create the named index with chunk_id as primary key
        3. Configure searchable, filterable, and sortable attributes

        WHY idempotent: called at startup. Must not reset the index
        or lose data if called multiple times (e.g., after a restart).
        """
        self._client = meilisearch.Client(self._config.host, self._config.api_key)

        # Get or create the index
        try:
            self._index = self._client.get_index(self._config.index_name)
        except meilisearch.errors.MeilisearchApiError:
            # Index does not exist yet -- create with chunk_id as primary key
            self._client.create_index(
                self._config.index_name, {"primaryKey": "chunk_id"}
            )
            self._index = self._client.get_index(self._config.index_name)

        # Configure which fields are searchable (only text)
        self._index.update_searchable_attributes(["text"])

        # Configure which fields can be used in filter expressions
        self._index.update_filterable_attributes([
            "doc_id",
            "source_filename",
            "domain",
            "chunk_type",
            "language",
        ])

        # Configure sortable fields for position-based ordering
        self._index.update_sortable_attributes(["position"])

        logger.info(
            "Meilisearch initialized: %s (index: %s)",
            self._config.host,
            self._config.index_name,
        )

    async def health_check(self) -> bool:
        """Verify Meilisearch is reachable and responsive.

        WHAT: calls the /health endpoint to confirm the server is up.
        Returns False if the client was never initialized (close()
        called before health_check) or if the health call fails.

        WHY: M2 (Storage) exposes a single /health endpoint that
        aggregates health from all 4 backends. Each backend's
        health_check() must return promptly (no retry loops) so the
        aggregate endpoint does not block.
        """
        try:
            if self._client is None:
                return False
            self._client.health()
            return True
        except Exception:
            logger.exception("Meilisearch health check failed")
            return False

    async def close(self) -> None:
        """Release the HTTP client reference.

        WHAT: sets _index and _client to None so GC can reclaim them.
        Safe to call even if initialize() was never called.

        WHY: Meilisearch Python client uses an HTTP connection pool.
        Setting to None lets the requests.Session be garbage collected,
        closing pooled connections.
        """
        self._index = None
        self._client = None

    # ------------------------------------------------------------------
    # Business operations
    # ------------------------------------------------------------------

    async def index(self, chunks: list[Chunk]) -> None:
        """Index chunks for full-text search.

        WHAT: converts Chunk objects to flat dicts and upserts them
        into the Meilisearch index. Metadata fields are stored as
        top-level keys so they can be used in filter expressions.

        WHY flat dicts: Meilisearch stores documents as JSON. We
        flatten chunk metadata into top-level fields because
        Meilisearch filter expressions operate on top-level keys,
        not nested objects. The chunk_id serves as the primary key
        so re-indexing the same chunk updates it in place.
        """
        if not chunks or self._index is None:
            return

        documents = [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                # doc_id is derived from source_filename by stripping
                # the extension -- this matches how M1 names documents
                "doc_id": c.metadata.source_filename.replace(".pdf", ""),
                "source_filename": c.metadata.source_filename,
                "domain": c.metadata.domain.value,
                "chunk_type": c.chunk_type,
                "language": c.metadata.language,
                "position": c.position_in_document,
            }
            for c in chunks
        ]

        self._index.add_documents(documents)
        logger.debug("Indexed %d chunks in Meilisearch", len(chunks))

    async def search(
        self,
        query: str,
        top_k: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Full-text search with optional metadata filtering.

        WHAT:
        1. Convert flat filter dict to Meilisearch filter expression
        2. Execute the search with the configured limit
        3. Reconstruct Chunk objects from Meilisearch hit documents

        Returns (chunk, score) pairs sorted by relevance (BM25 ranking
        score). Returns empty list if the index is not initialized.

        WHY returns Chunks: upper modules (M3, M4, M5) consume Chunk
        objects, not raw dicts. Reconstructing them here keeps the
        Chunk schema as the single source of truth for chunk data.
        """
        if self._index is None:
            return []

        # Build Meilisearch filter expression from flat dict
        filter_expr = _build_meili_filter(filters) if filters else None

        results = self._index.search(query, {
            "limit": top_k,
            "filter": filter_expr,
            "attributesToRetrieve": [
                "chunk_id", "text", "doc_id", "source_filename",
                "domain", "chunk_type", "language", "position",
            ],
        })

        # Reconstruct Chunk objects from search hits
        chunks: list[tuple[Chunk, float]] = []
        for hit in results.get("hits", []):
            chunk = Chunk(
                chunk_id=hit["chunk_id"],
                text=hit["text"],
                metadata=DocumentMetadata(
                    source_filename=hit.get("source_filename", "unknown"),
                    domain=Domain(hit.get("domain", "general")),
                    language=hit.get("language", "en"),
                ),
                chunk_type=hit.get("chunk_type", "general"),
                position_in_document=hit.get("position", 0),
            )
            # Meilisearch's _rankingScore represents BM25 relevance
            score = hit.get("_rankingScore", 0.0)
            chunks.append((chunk, score))

        return chunks

    async def delete(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document by doc_id filter.

        WHAT:
        1. Count matching documents before deletion
        2. Delete all documents matching doc_id = <value>
        3. Return the pre-deletion count

        WHY return count: callers (M1 re-indexing) need to know how
        many chunks were removed for logging and verification. The
        Meilisearch delete_documents_by_filter API only returns a
        task UID, so we count before deletion.

        Returns 0 if the index is not initialized.
        """
        if self._index is None:
            return 0

        # Count matching documents before deletion
        # (Meilisearch filter requires string values to be double-quoted)
        before = self._index.search(
            "", {"limit": 0, "filter": f'doc_id = "{doc_id}"'}
        )
        before_count = before.get("estimatedTotalHits", 0)

        # Delete all documents matching the doc_id filter
        self._index.delete_documents_by_filter(f'doc_id = "{doc_id}"')

        logger.info("Deleted ~%d chunks for doc_id=%s", before_count, doc_id)
        return before_count


# ===========================================================================
# Internal helper -- filter expression builder
# ===========================================================================


def _build_meili_filter(filters: dict[str, Any]) -> str:
    """Convert flat filter dict to Meilisearch filter expression.

    WHAT: transforms a Python dict of filter conditions into a
    Meilisearch-compatible filter string using SQL-like syntax.

    Rules:
    - String values are double-quoted: {"domain": "structure"} -> 'domain = "structure"'
    - Non-string values (int, bool) are unquoted: {"year": 2021} -> 'year = 2021'
    - Multiple conditions are AND-joined: {"domain": "s", "lang": "en"} -> 'domain = "s" AND lang = "en"'

    WHY this syntax: Meilisearch uses SQL-like filter expressions
    (not JSON, not MongoDB query objects). This is the only filter
    syntax Meilisearch accepts for the /search endpoint.

    WHY AND-joined: the contracts layer treats filters as
    intersectional (must match ALL conditions). OR semantics would
    require a different API design with explicit operator support.
    """
    parts: list[str] = []
    for key, value in filters.items():
        if isinstance(value, str):
            # String values must be double-quoted in Meilisearch filter syntax
            parts.append(f'{key} = "{value}"')
        else:
            # Non-string values (int, bool) are unquoted
            parts.append(f"{key} = {value}")
    return " AND ".join(parts)
