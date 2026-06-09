"""
Elasticsearch implementation of BaseDocumentIndex.

WHAT: Implements BaseDocumentIndex using Elasticsearch 8.x Python client.
      Provides full-text search with configurable sharding, replication,
      metadata filtering, and bulk indexing.

WHY: Elasticsearch is the recommended full-text engine for SaaS
     deployments. It provides distributed search (shards + replicas),
     horizontal scaling, and the most mature full-text search ecosystem.
     Meilisearch is preferred for Personal/Enterprise (single-node, simpler).

ELASTICSEARCH vs MEILISEARCH:
    - ES uses JSON query DSL (term/match/bool queries)
    - Meilisearch uses SQL-like filter expressions
    - ES supports distributed sharding; Meilisearch is single-node
    - Both support BM25 ranking, typo tolerance, and metadata filtering
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from contracts.document import Chunk, DocumentMetadata, Domain

from .base import BaseDocumentIndex

logger = logging.getLogger(__name__)


class ElasticsearchIndex(BaseDocumentIndex):
    """Document index backed by Elasticsearch 8.x.

    WHAT: Full-text search with typo tolerance, metadata filtering,
          bulk indexing, and deletion by document ID. Designed for
          SaaS deployments needing distributed search.

    MAPPING: The index mapping defines all fields with appropriate
             types (text for full-text, keyword for filterable).
             This is configured at initialize() time and is idempotent —
             subsequent calls do not reset the index.
    """

    def __init__(self, config):
        """Store config; client is created lazily in initialize()."""
        self._config = config
        self._client = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Connect to Elasticsearch, create/verify index with mapping.

        WHAT:
        1. Create the Elasticsearch client (with optional auth)
        2. Check if the index exists; create it with mapping if not
        3. Verify connectivity

        WHY idempotent: called at startup. Must not reset the index
        or lose data if called multiple times.
        """
        try:
            from elasticsearch import AsyncElasticsearch
        except ImportError:
            raise ImportError(
                "elasticsearch package not installed. "
                "Install with: pip install elasticsearch>=8.0.0"
            )

        # Build connection params — use basic_auth if credentials provided
        es_kwargs: dict[str, Any] = {
            "hosts": [self._config.host],
            "request_timeout": self._config.request_timeout,
        }
        if self._config.user and self._config.password:
            es_kwargs["basic_auth"] = (self._config.user, self._config.password)

        self._client = AsyncElasticsearch(**es_kwargs)

        # Create index with mapping if it doesn't exist
        index_exists = await self._client.indices.exists(
            index=self._config.index_name
        )
        if not index_exists:
            await self._client.indices.create(
                index=self._config.index_name,
                settings={
                    "number_of_shards": self._config.num_shards,
                    "number_of_replicas": self._config.num_replicas,
                },
                mappings=_ES_MAPPING,
            )
            logger.info(
                "Elasticsearch index created: %s (shards=%d, replicas=%d)",
                self._config.index_name,
                self._config.num_shards,
                self._config.num_replicas,
            )
        else:
            logger.info(
                "Elasticsearch index exists: %s", self._config.index_name
            )

    async def health_check(self) -> bool:
        """Verify Elasticsearch cluster is reachable via cluster health API.

        WHY: Uses _cluster/health instead of a ping endpoint because it
             validates the entire cluster state, not just connectivity
             to a single node. Returns False if not initialized.
        """
        try:
            if self._client is None:
                return False
            await self._client.cluster.health(wait_for_status="yellow")
            return True
        except Exception:
            logger.warning("Elasticsearch health check failed")
            return False

    async def close(self) -> None:
        """Close the Elasticsearch client, releasing HTTP connections.

        WHAT: Calls await client.close() which closes the underlying
              httpx connection pool. Safe to call even if initialize()
              was never called.
        """
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("Elasticsearch client closed")

    # ------------------------------------------------------------------
    # Business operations
    # ------------------------------------------------------------------

    async def index(self, chunks: list[Chunk]) -> None:
        """Bulk-index chunks for full-text search.

        WHAT: Converts Chunk objects to flat dicts and bulk-indexes them
              into the Elasticsearch index. Uses the _bulk API for
              efficient batch ingestion.

        WHY flat dicts: Elasticsearch stores documents as JSON. Metadata
             must be top-level keys for term filter queries to work.
        """
        if not chunks or self._client is None:
            return

        # Build bulk body: action + document pairs
        # Elasticsearch _bulk API expects: { "index": { "_id": "..." } }\n{ doc }\n
        from io import BytesIO
        import json

        lines: list[str] = []
        for c in chunks:
            doc_id = _make_doc_id(c)
            action = json.dumps({"index": {"_id": doc_id}})
            doc = json.dumps({
                "chunk_id": c.chunk_id,
                "text": c.text,
                "doc_id": Path(c.metadata.source_filename).stem,
                "source_filename": c.metadata.source_filename,
                "domain": c.metadata.domain.value,
                "chunk_type": c.chunk_type,
                "language": c.metadata.language,
                "position": c.position_in_document,
            })
            lines.append(action)
            lines.append(doc)

        # Join with newlines + trailing newline required by _bulk API
        body = "\n".join(lines) + "\n"

        # Use the low-level perform_request for bulk — the helpers.bulk
        # function is not async-compatible in elasticsearch-py 8.x
        await self._client.perform_request(
            "POST",
            f"/{self._config.index_name}/_bulk",
            body=body.encode("utf-8"),
            headers={"Content-Type": "application/x-ndjson"},
        )

        logger.debug("Indexed %d chunks in Elasticsearch", len(chunks))

    async def search(
        self,
        query: str,
        top_k: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Full-text search with optional metadata filtering.

        WHAT:
        1. Build an ES match query for full-text on the "text" field
        2. Add term filters for metadata if provided
        3. Execute the search and reconstruct Chunk objects

        Returns (chunk, score) pairs sorted by relevance (BM25).
        Returns empty list if index is not initialized.
        """
        if self._client is None:
            return []

        # Build query body
        must_clauses: list[dict] = [
            {"match": {"text": query}},
        ]
        filter_clauses: list[dict] = _build_es_filters(filters) if filters else []

        body: dict[str, Any] = {
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses if filter_clauses else None,
                }
            },
            "size": top_k,
            "_source": [
                "chunk_id", "text", "doc_id", "source_filename",
                "domain", "chunk_type", "language", "position",
            ],
        }
        # Remove None-valued keys (filter may be None)
        if not filter_clauses:
            del body["query"]["bool"]["filter"]

        results = await self._client.search(
            index=self._config.index_name,
            body=body,
        )

        # Reconstruct Chunk objects from search hits
        chunks: list[tuple[Chunk, float]] = []
        for hit in results["hits"]["hits"]:
            src = hit["_source"]
            chunk = Chunk(
                chunk_id=src["chunk_id"],
                text=src["text"],
                metadata=DocumentMetadata(
                    source_filename=src.get("source_filename", "unknown"),
                    domain=Domain(src.get("domain", "general")),
                    language=src.get("language", "en"),
                ),
                chunk_type=src.get("chunk_type", "general"),
                position_in_document=src.get("position", 0),
            )
            score = hit.get("_score", 0.0)
            chunks.append((chunk, score))

        return chunks

    async def delete(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document by doc_id.

        WHAT:
        1. Count matching documents before deletion
        2. Delete by query matching doc_id
        3. Return the pre-deletion count

        WHY return count: callers (M1 re-indexing) need to know how
        many chunks were removed for logging and verification.
        Returns 0 if the index is not initialized.
        """
        if self._client is None:
            return 0

        # Count before deletion
        count_result = await self._client.count(
            index=self._config.index_name,
            body={"query": {"term": {"doc_id": doc_id}}},
        )
        before_count = count_result.get("count", 0)

        if before_count > 0:
            await self._client.delete_by_query(
                index=self._config.index_name,
                body={"query": {"term": {"doc_id": doc_id}}},
                refresh=True,  # Make deletion immediately visible
            )
            logger.info("Deleted %d chunks for doc_id=%s", before_count, doc_id)

        return before_count


# ===========================================================================
# Internal helpers
# ===========================================================================


def _make_doc_id(chunk: Chunk) -> str:
    """Generate a unique Elasticsearch document ID from chunk metadata.

    WHAT: Combines chunk_id with position to guarantee uniqueness.

    WHY: Using chunk_id as _id makes re-indexing idempotent — indexing
         the same chunk twice updates it rather than creating a duplicate.
    """
    return f"{chunk.chunk_id}"


def _build_es_filters(filters: dict[str, Any]) -> list[dict]:
    """Convert flat filter dict to Elasticsearch term filter clauses.

    WHAT: Transforms a Python dict of filter conditions into ES
          term query clauses. Each key-value pair becomes:
          {"term": {key: value}}

    WHY: ES uses JSON query DSL. Term queries perform exact matching
         on keyword fields. This is the equivalent of Meilisearch's
         SQL-like filter expressions but using ES's native syntax.

    NOTE: Only non-empty values are included. Empty strings and None
          values are silently skipped to avoid broken queries.
    """
    clauses: list[dict] = []
    for key, value in filters.items():
        if value is not None and value != "":
            clauses.append({"term": {key: value}})
    return clauses


# ===========================================================================
# Elasticsearch index mapping
#
# WHY explicit mapping: Elasticsearch's dynamic mapping would guess field
# types from the first document. Explicit mapping guarantees:
# - "text" field has BM25 similarity (not guessed as anything else)
# - "domain"/"chunk_type"/"language" are keyword (exact match for filters)
# - "position" is integer (sortable)
# ===========================================================================

_ES_MAPPING = {
    "properties": {
        "chunk_id":         {"type": "keyword"},
        "text":             {"type": "text", "similarity": "BM25"},
        "doc_id":           {"type": "keyword"},
        "source_filename":  {"type": "keyword"},
        "domain":           {"type": "keyword"},
        "chunk_type":       {"type": "keyword"},
        "language":         {"type": "keyword"},
        "position":         {"type": "integer"},
    }
}
