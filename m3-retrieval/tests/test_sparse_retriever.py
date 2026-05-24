# -*- coding: utf-8 -*-
"""
Tests for M3 Sparse Retriever (sparse_retriever.py).

WHAT: Validates that SparseRetriever correctly wraps Meilisearch BM25
full-text search via M2 StorageManager, handles empty keyword input
gracefully, and produces ScoredChunk results with source="bm25" and
human-readable citations.

WHY: The sparse retriever is one of two parallel retrieval backends
(dense + sparse) that feed into the fusion stage. Its correctness is
critical for keyword-based queries and domain-specific technical
terminology that BM25 handles best.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from contracts.document import Chunk, DocumentMetadata, Domain
from contracts.retrieval import ScoredChunk
from m3_retrieval.stages.sparse_retriever import SparseRetriever, _citation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    chunk_id: str = "c001",
    text: str = "test text",
    source_filename: str = "test.pdf",
    domain: Domain = Domain.GENERAL,
    chunk_type: str = "clause",
) -> Chunk:
    """
    Create a minimal Chunk for testing without touching real storage.

    WHAT: Factory function that builds a Chunk with only the fields
    needed by the citation and ScoredChunk construction.

    WHY helper: avoids boilerplate in every test case. Not a fixture
    because different tests need different param combinations.
    """
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        metadata=DocumentMetadata(
            source_filename=source_filename,
            domain=domain,
        ),
        chunk_type=chunk_type,
    )


# ---------------------------------------------------------------------------
# Citation tests
# ---------------------------------------------------------------------------


class TestCitation:
    """Test the _citation() helper that builds human-readable citations."""

    def test_citation_format(self) -> None:
        """
        WHAT: _citation() produces the format:
            "{source_filename}" [{domain}] {chunk_type}

        WHY: This format gives users provenance info at a glance:
        which document, what domain, and what content type.
        """
        chunk = _make_chunk(
            source_filename="DNV-ST-N001.pdf",
            domain=Domain.STRUCTURE,
            chunk_type="clause",
        )
        result = _citation(chunk)
        assert result == '"DNV-ST-N001.pdf" [structure] clause'

    def test_citation_machinery_domain(self) -> None:
        """
        WHAT: Citation shows the domain value (not the enum name) for
        different engineering domains.
        """
        chunk = _make_chunk(
            source_filename="ABS-Rules-2023.pdf",
            domain=Domain.MACHINERY,
            chunk_type="table",
        )
        result = _citation(chunk)
        assert result == '"ABS-Rules-2023.pdf" [machinery] table'

    def test_citation_figure_type(self) -> None:
        """
        WHAT: Citation for figure-type chunks.
        """
        chunk = _make_chunk(
            source_filename="CCS-Guideline.pdf",
            domain=Domain.PIPING,
            chunk_type="figure",
        )
        result = _citation(chunk)
        assert result == '"CCS-Guideline.pdf" [piping] figure'


# ---------------------------------------------------------------------------
# SparseRetriever tests
# ---------------------------------------------------------------------------


class TestSparseRetrieverInit:
    """Test SparseRetriever initialisation."""

    def test_sparse_retriever_init(self) -> None:
        """
        WHAT: Constructor accepts a storage_manager mock and optional top_k.

        Expected: instance is created without error, top_k is stored.
        """
        mock_sm = MagicMock()
        retriever = SparseRetriever(mock_sm, top_k=15)
        assert retriever.top_k == 15
        assert retriever._sm is mock_sm

    def test_sparse_retriever_default_top_k(self) -> None:
        """
        WHAT: When top_k is not provided, the default should be 20
        (matching the RetrievalConfig.sparse_top_k default).

        WHY: Consistency with the config default prevents surprises
        when the retriever is instantiated without explicit top_k.
        """
        mock_sm = MagicMock()
        retriever = SparseRetriever(mock_sm)
        assert retriever.top_k == 20


class TestSparseRetrieverSearch:
    """Test the search() method behaviour."""

    @pytest.mark.asyncio
    async def test_empty_keywords_returns_empty(self) -> None:
        """
        WHAT: Passing an empty keyword list must return an empty list
        immediately, without calling the storage backend.

        WHY: An empty keyword list means the user query contained no
        extractable technical keywords. Rather than searching for an
        empty string (which Meilisearch would treat as a match-all),
        we short-circuit and return nothing. This prevents noise in
        the fusion stage.
        """
        mock_sm = MagicMock()
        retriever = SparseRetriever(mock_sm, top_k=20)
        result = await retriever.search([])
        assert result == []

        # The storage backend must NOT have been called
        assert not mock_sm.doc_index.search.called

    @pytest.mark.asyncio
    async def test_empty_string_keywords_returns_empty(self) -> None:
        """
        WHAT: Passing a list with only whitespace strings should also
        return empty.

        WHY: Whitespace-only keywords produce an effectively empty
        query after joining. Same rationale as empty list.
        """
        mock_sm = MagicMock()
        retriever = SparseRetriever(mock_sm, top_k=20)
        result = await retriever.search(["   ", "\t"])
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_scored_chunks(self) -> None:
        """
        WHAT: Normal keyword search returns a list of ScoredChunk
        objects with source="bm25" and correct citation strings.

        Expected: each ScoredChunk has correct fields, the storage
        backend is called with the joined keywords as the query.
        """
        chunk1 = _make_chunk(
            chunk_id="c001",
            text="Hull structural requirements for DNV classification",
            source_filename="DNV-ST-N001.pdf",
            domain=Domain.STRUCTURE,
            chunk_type="clause",
        )
        chunk2 = _make_chunk(
            chunk_id="c002",
            text="Welding procedure specification for AH36 steel",
            source_filename="DNV-ST-N001.pdf",
            domain=Domain.STRUCTURE,
            chunk_type="general",
        )

        # Wire up the async mock: storage_manager.doc_index.search()
        mock_search = AsyncMock()
        mock_search.return_value = [(chunk1, 0.95), (chunk2, 0.72)]

        mock_sm = MagicMock()
        mock_sm.doc_index.search = mock_search

        retriever = SparseRetriever(mock_sm, top_k=20)
        result = await retriever.search(["hull", "welding"])

        # Verify the storage backend was called correctly
        mock_search.assert_called_once_with(
            query="hull welding", top_k=20, filters=None,
        )

        # Verify result type and content
        assert len(result) == 2
        assert all(isinstance(r, ScoredChunk) for r in result)

        # First result
        assert result[0].chunk is chunk1
        assert result[0].score == 0.95
        assert result[0].source == "bm25"
        assert result[0].citation == _citation(chunk1)

        # Second result
        assert result[1].chunk is chunk2
        assert result[1].score == 0.72
        assert result[1].source == "bm25"
        assert result[1].citation == _citation(chunk2)

    @pytest.mark.asyncio
    async def test_search_with_filters(self) -> None:
        """
        WHAT: When filters dict is provided, it is passed through to
        the storage backend.

        WHY: Metadata filtering (e.g. by classification_society,
        chapter_section) is critical for scoping the BM25 search to
        relevant documents only.
        """
        chunk = _make_chunk(chunk_id="c001", text="DNV hull welding")

        mock_search = AsyncMock()
        mock_search.return_value = [(chunk, 0.88)]

        mock_sm = MagicMock()
        mock_sm.doc_index.search = mock_search

        retriever = SparseRetriever(mock_sm, top_k=15)
        filters = {"classification_society": "DNV", "chapter_section": "Pt.3 Ch.2"}
        result = await retriever.search(["hull"], filters=filters)

        # Verify filters were passed through
        mock_search.assert_called_once_with(
            query="hull", top_k=15, filters=filters,
        )
        assert len(result) == 1
        assert result[0].source == "bm25"

    @pytest.mark.asyncio
    async def test_search_with_custom_top_k(self) -> None:
        """
        WHAT: Search with a non-default top_k value.

        Expected: the custom top_k is passed to the storage backend.
        """
        chunk = _make_chunk(chunk_id="c001", text="pipe stress analysis")

        mock_search = AsyncMock()
        mock_search.return_value = [(chunk, 0.91)]

        mock_sm = MagicMock()
        mock_sm.doc_index.search = mock_search

        retriever = SparseRetriever(mock_sm, top_k=10)
        await retriever.search(["pipe", "stress"])

        mock_search.assert_called_once_with(
            query="pipe stress", top_k=10, filters=None,
        )

    @pytest.mark.asyncio
    async def test_search_empty_backend_result(self) -> None:
        """
        WHAT: When the storage backend returns no results, return an
        empty list without error.

        WHY: No-match queries are normal (users search for things not
        in the database). The retriever must handle this gracefully,
        returning [] so the fusion stage can fall back to dense results.
        """
        mock_search = AsyncMock()
        mock_search.return_value = []

        mock_sm = MagicMock()
        mock_sm.doc_index.search = mock_search

        retriever = SparseRetriever(mock_sm, top_k=20)
        result = await retriever.search(["nonexistent", "keyword"])

        assert result == []
