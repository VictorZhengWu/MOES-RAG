# -*- coding: utf-8 -*-
"""
Tests for M3 Context Expander and Deduplication stage (context_expander.py).

WHAT: Validates five behaviours:
  1. test_jaccard_identical: Jaccard similarity of identical strings = 1.0.
  2. test_jaccard_different: Jaccard similarity of completely different
     strings = 0.0.
  3. test_dedup_removes_similar: Adjacent similar chunks (Jaccard >=
     threshold) are removed, keeping the first one.
  4. test_dedup_keeps_different: Adjacent different chunks (Jaccard <
     threshold) are both kept.
  5. test_single_element_passthrough: A list of 0 or 1 chunks is returned
     unchanged.

WHY: After fusion and reranking, multiple chunks from the same
document section may be nearly identical (e.g. overlapping chunks
from different retrieval backends, or adjacent chunks with very
similar content). Deduplication removes this redundancy so the LLM
context window is used efficiently and the user sees diverse results.
"""

from __future__ import annotations

import pytest

from contracts.document import Chunk, DocumentMetadata, Domain
from contracts.retrieval import ScoredChunk


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
    """Create a minimal Chunk for testing."""
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        metadata=DocumentMetadata(
            source_filename=source_filename,
            domain=domain,
        ),
        chunk_type=chunk_type,
    )


def _make_scored(
    chunk_id: str = "c001",
    text: str = "test text",
    score: float = 0.9,
    source: str = "fusion",
    source_filename: str = "test.pdf",
    domain: Domain = Domain.GENERAL,
    chunk_type: str = "clause",
) -> ScoredChunk:
    """Create a ScoredChunk for testing."""
    chunk = _make_chunk(
        chunk_id=chunk_id,
        text=text,
        source_filename=source_filename,
        domain=domain,
        chunk_type=chunk_type,
    )
    citation = f'"{source_filename}" [{domain.value}] {chunk_type}'
    return ScoredChunk(chunk=chunk, score=score, source=source, citation=citation)


# =============================================================================
# Jaccard similarity tests
# =============================================================================


class TestJaccardSimilarity:
    """Test the _jaccard() helper function."""

    def test_jaccard_identical(self) -> None:
        """
        WHAT: Jaccard similarity of two identical strings must be 1.0.

        WHY: The Jaccard coefficient for two identical sets is always 1.0
        (intersection equals union). This is the upper bound of the metric.
        """
        from m3_retrieval.stages.context_expander import _jaccard

        text = "The hull structural requirements specify minimum plate thickness"
        result = _jaccard(text, text)
        assert result == pytest.approx(1.0, abs=0.001)

    def test_jaccard_different(self) -> None:
        """
        WHAT: Jaccard similarity of two texts with no common words must
        be 0.0.

        WHY: When two texts share no words (after tokenization), the
        intersection is empty, making the Jaccard coefficient 0.0.
        This is the lower bound of the metric.
        """
        from m3_retrieval.stages.context_expander import _jaccard

        text_a = "hull structural strength requirements for bulk carriers"
        text_b = "only completely unrelated different words here"
        result = _jaccard(text_a, text_b)
        assert result == pytest.approx(0.0, abs=0.001)

    def test_jaccard_partial_overlap(self) -> None:
        """
        WHAT: Jaccard similarity of two texts with partial word overlap
        should be between 0.0 and 1.0.

        WHY: Real-world adjacent chunks often share some but not all
        vocabulary. The Jaccard coefficient should reflect this partial
        similarity.
        """
        from m3_retrieval.stages.context_expander import _jaccard

        text_a = "welding procedure specification for AH36 steel plate"
        text_b = "welding requirements for DH36 steel plate thickness"
        result = _jaccard(text_a, text_b)
        # Should be between 0.0 and 1.0 (some overlap but not identical)
        assert 0.0 < result < 1.0, (
            f"Expected 0.0 < Jaccard < 1.0 for partial overlap, got {result:.4f}"
        )


# =============================================================================
# Deduplication tests
# =============================================================================


class TestDeduplicateChunks:
    """Test the deduplicate_chunks() function."""

    def test_single_element_passthrough(self) -> None:
        """
        WHAT: A list with 0 or 1 elements is returned unchanged.

        WHY: With 0 or 1 elements, there is nothing to deduplicate
        against. The function should short-circuit and return as-is.
        """
        from m3_retrieval.stages.context_expander import deduplicate_chunks

        # Empty list
        result_empty = deduplicate_chunks([])
        assert result_empty == []

        # Single element
        sc = _make_scored("c001", "only one chunk")
        result_single = deduplicate_chunks([sc])
        assert len(result_single) == 1
        assert result_single[0] is sc

    def test_dedup_removes_similar(self) -> None:
        """
        WHAT: When two adjacent chunks have Jaccard similarity above
        the threshold (default 0.85), the second one is removed.

        WHY: Adjacent chunks from the same document section often contain
        nearly duplicate text (e.g. overlapping chunks from chunking
        with overlap, or the same chunk retrieved by both dense and
        sparse backends). The deduplication keeps the first occurrence
        and removes near-duplicates to avoid wasting context window.
        """
        from m3_retrieval.stages.context_expander import deduplicate_chunks

        # Two chunks with very similar text (high Jaccard)
        text = "The hull structural requirements for ocean-going vessels specify minimum plate thickness values based on frame spacing and design pressure loads"
        # Nearly identical text (just changed one word)
        text_similar = "The hull structural requirements for ocean-going vessels specify minimum steel thickness values based on frame spacing and design pressure loads"

        chunks = [
            _make_scored("c001", text, score=0.95),
            _make_scored("c002", text_similar, score=0.90),  # Nearly duplicate
        ]

        result = deduplicate_chunks(chunks, threshold=0.85)

        # Only the first chunk should remain
        assert len(result) == 1
        assert result[0].chunk.chunk_id == "c001"

    def test_dedup_keeps_different(self) -> None:
        """
        WHAT: When two adjacent chunks have Jaccard similarity below
        the threshold, both are kept.

        WHY: Chunks from different sections or documents should not be
        deduplicated. Only true near-duplicates should be removed.
        """
        from m3_retrieval.stages.context_expander import deduplicate_chunks

        text_a = "Welding procedure specification for AH36 steel plate requires preheat temperature of 100 degrees Celsius minimum for all thicknesses"
        text_b = "Electrical system installation requirements for offshore platforms specify cable routing through designated trays with fire-rated barriers at compartment boundaries"

        chunks = [
            _make_scored("c001", text_a, score=0.95),
            _make_scored("c002", text_b, score=0.90),  # Completely different topic
        ]

        result = deduplicate_chunks(chunks, threshold=0.85)

        # Both chunks should remain since they are very different
        assert len(result) == 2
        assert result[0].chunk.chunk_id == "c001"
        assert result[1].chunk.chunk_id == "c002"

    def test_dedup_multiple_similar_in_sequence(self) -> None:
        """
        WHAT: When three consecutive chunks are similar, only the first
        one is kept; the second and third are removed.

        WHY: The deduplication algorithm is a single-pass neighbour
        comparison, O(n). When chunk B is similar to chunk A, B is
        removed. Then chunk C is compared to chunk A (the last kept
        chunk), and if similar, C is also removed.
        """
        from m3_retrieval.stages.context_expander import deduplicate_chunks

        text_base = (
            "The piping system design must comply with IACS UR P2 requirements "
            "for pressure testing and material certification"
        )
        text_similar_1 = (
            "The piping system design must comply with IACS UR P2 requirements "
            "for pressure testing and material certificates"
        )
        text_similar_2 = (
            "The piping system design must comply with IACS UR P2 requirements "
            "for pressure tests and material certification"
        )
        text_different = (
            "Communication equipment shall meet GMDSS requirements for sea area A3 "
            "with redundant power supply and automatic switchover capability"
        )

        chunks = [
            _make_scored("c001", text_base, score=0.95),
            _make_scored("c002", text_similar_1, score=0.90),  # Similar to c001
            _make_scored("c003", text_similar_2, score=0.85),  # Similar to c001
            _make_scored("c004", text_different, score=0.80),   # Different
        ]

        result = deduplicate_chunks(chunks, threshold=0.85)

        # c001 (kept), c002 (removed, similar to c001), c003 (removed, similar to c001), c004 (kept)
        assert len(result) == 2
        assert result[0].chunk.chunk_id == "c001"
        assert result[1].chunk.chunk_id == "c004"


# =============================================================================
# Context expansion tests (placeholder)
# =============================================================================


class TestExpandContext:
    """Test the expand_context() function (placeholder implementation)."""

    def test_expand_context_placeholder_returns_original(self) -> None:
        """
        WHAT: The current placeholder implementation of expand_context()
        returns the original chunk list unchanged.

        WHY: Context expansion (fetching neighbouring chunks for each
        result) requires the storage manager to query chunk adjacency.
        Until that integration is ready, the function is a passthrough
        so the pipeline composes correctly without it.
        """
        from m3_retrieval.stages.context_expander import expand_context

        chunks = [
            _make_scored("c001", "chunk 1 text", score=0.95),
            _make_scored("c002", "chunk 2 text", score=0.90),
            _make_scored("c003", "chunk 3 text", score=0.85),
        ]

        result = expand_context(chunks, storage_manager=None, window=3)

        assert len(result) == 3
        # The returned list should be the same elements
        for i, sc in enumerate(chunks):
            assert result[i] is sc
