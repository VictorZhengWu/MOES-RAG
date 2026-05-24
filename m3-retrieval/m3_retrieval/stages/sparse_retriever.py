# -*- coding: utf-8 -*-
"""
Sparse Retriever — BM25 full-text search via Meilisearch (M3 pipeline stage).

WHAT: Wraps the M2 StorageManager's DocumentIndexProtocol (backed by
Meilisearch) to perform BM25 keyword search. Takes a list of extracted
keywords (from the QueryAnalyzer), joins them with spaces, and queries
the full-text index.

Returns a list of ScoredChunk objects with source="bm25" and a
human-readable citation for each result.

WHY: Dense/semantic retrieval is weak on exact technical codes,
abbreviations, and domain-specific identifiers (e.g. "AH36", "DNV",
"Pt.3 Ch.2"). BM25 excels at precise keyword matching, making the
sparse retriever the primary backend for regulation-code queries and
technical keyword lookups.

Key design decisions:
  - Operates on keywords (list[str]), NOT raw query text. The
    QueryAnalyzer upstream separates technical keywords from the
    semantic core. This retriever only handles the former.
  - Short-circuits on empty/whitespace-only keywords. Sending an
    empty query to Meilisearch would return all documents, which
    pollutes the fusion stage with noise.
  - Passes filters through to the storage backend unchanged. Filter
    format is backend-specific (Meilisearch filter expressions).
  - _citation() is a module-level function (not a method) because
    it has no dependency on instance state and is useful for testing
    in isolation.
"""

from __future__ import annotations

from contracts.document import Chunk
from contracts.retrieval import ScoredChunk


def _citation(chunk: Chunk) -> str:
    """
    Build a human-readable citation string for a retrieved chunk.

    WHAT: Produces a string in the format:
        "{source_filename}" [domain] chunk_type

    Example: '"DNV-ST-N001.pdf" [structure] clause'

    This gives users provenance information at a glance: which
    document the chunk came from, what engineering domain it belongs
    to, and what kind of content it represents.

    WHY module-level function: no dependency on SparseRetriever
    instance state. Kept separate for testability and potential
    reuse by other retrieval stages that need the same format
    (e.g. the fusion stage for merged results).

    Args:
        chunk: The Chunk to generate a citation for.

    Returns:
        A formatted citation string.
    """
    filename: str = chunk.metadata.source_filename
    domain: str = chunk.metadata.domain.value  # Use the string value, not enum name
    chunk_type: str = chunk.chunk_type
    return f'"{filename}" [{domain}] {chunk_type}'


class SparseRetriever:
    """
    Full-text / BM25 search via Meilisearch through M2 StorageManager.

    WHAT: Takes extracted keywords (from QueryAnalyzer) and queries the
    M2 document index for exact/fuzzy keyword matches using BM25 scoring.
    Returns ranked ScoredChunk results with source="bm25".

    This is one of two parallel retrieval backends. It runs alongside
    the DenseRetriever (embedding-based semantic search), and their
    outputs are combined in the fusion stage.

    WHY class (not function): holds the storage_manager reference and
    top_k configuration as instance state. The search() method is
    async because it calls the async storage backend.

    Usage:
        sm = StorageManager(...)
        retriever = SparseRetriever(sm, top_k=20)
        results = await retriever.search(["hull", "welding", "AH36"])
    """

    def __init__(self, storage_manager, top_k: int = 20) -> None:
        """
        Initialize the sparse retriever.

        WHAT: Stores the storage manager reference and top_k setting.

        Args:
            storage_manager: M2 StorageManager instance. Must expose a
                ``doc_index`` attribute implementing DocumentIndexProtocol
                (i.e. has an async ``search(query, top_k, filters)`` method).
            top_k: Maximum number of results to return. Default 20,
                matching RetrievalConfig.sparse_top_k.
        """
        self._sm = storage_manager
        self.top_k: int = top_k

    async def search(
        self, keywords: list[str], filters: dict | None = None
    ) -> list[ScoredChunk]:
        """
        Execute BM25 full-text search for the given keywords.

        WHAT: Joins the keyword list into a space-separated query string
        and sends it to the M2 document index. Wraps each result in a
        ScoredChunk with source="bm25" and a human-readable citation.

        Short-circuits to [] when keywords are empty or contain only
        whitespace — an empty Meilisearch query would match everything
        and pollute the fusion stage.

        Args:
            keywords: Extracted technical keywords (steel grades,
                temperature values, classification societies, etc.)
                from the QueryAnalyzer stage.
            filters: Optional metadata filters to scope the search
                (e.g. classification_society, chapter_section).
                Passed through to the storage backend unchanged.

        Returns:
            List of ScoredChunk objects ordered by BM25 relevance score
            (descending). Empty list if no keywords or no matches.
        """
        # Join keywords into a single query string
        query: str = " ".join(keywords) if keywords else ""

        # Short-circuit: empty or whitespace-only query would match all
        # documents in Meilisearch. Return nothing instead.
        if not query.strip():
            return []

        # Delegate to storage backend (Meilisearch via DocumentIndexProtocol)
        results = await self._sm.doc_index.search(
            query=query, top_k=self.top_k, filters=filters,
        )

        # Wrap each (Chunk, score) tuple into a ScoredChunk with citation
        return [
            ScoredChunk(chunk=c, score=s, source="bm25", citation=_citation(c))
            for c, s in results
        ]
