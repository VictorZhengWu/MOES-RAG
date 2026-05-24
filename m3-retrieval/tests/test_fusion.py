# -*- coding: utf-8 -*-
"""
Tests for M3 RRF Fusion stage (fusion.py).

WHAT: Validates four behaviours of rrf_fusion():
  1. test_dedup_by_chunk_id: Chunks with the same chunk_id appearing in
     multiple result sets are deduplicated and their RRF scores are
     accumulated correctly.
  2. test_empty_input: Passing an empty list returns an empty list.
  3. test_single_input_passthrough: Passing a single result set returns
     its chunks unchanged (re-scored via RRF, source="fusion").
  4. test_score_decreases_with_rank: RRF formula 1/(k + rank) produces
     monotonically decreasing scores for increasing ranks.

WHY: RRF (Reciprocal Rank Fusion) is the standard method for merging
results from multiple retrieval backends (dense, sparse, kg). It is
parameter-free and proven to produce better results than linear
combination of scores. Correctness of the fusion stage directly
impacts the quality of the final retrieval output consumed by M5.
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
    """
    Create a minimal Chunk for testing without touching real storage.

    WHAT: Factory function that builds a Chunk with only the fields
    needed for testing.

    WHY helper: avoids boilerplate in every test case.
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


def _make_scored(
    chunk_id: str = "c001",
    text: str = "test text",
    score: float = 0.9,
    source: str = "dense",
    source_filename: str = "test.pdf",
    domain: Domain = Domain.GENERAL,
    chunk_type: str = "clause",
) -> ScoredChunk:
    """
    Create a ScoredChunk for testing.

    WHAT: Factory that builds a ScoredChunk with a Chunk inside.
    """
    chunk = _make_chunk(
        chunk_id=chunk_id,
        text=text,
        source_filename=source_filename,
        domain=domain,
        chunk_type=chunk_type,
    )
    citation = f'"{source_filename}" [{domain.value}] {chunk_type}'
    return ScoredChunk(chunk=chunk, score=score, source=source, citation=citation)


# ---------------------------------------------------------------------------
# RRF Fusion tests
# ---------------------------------------------------------------------------


class TestRRFFusion:
    """Test rrf_fusion() function for merging multi-source retrieval results."""

    def test_empty_input_returns_empty(self) -> None:
        """
        WHAT: Passing an empty list of result sets must return an empty list.

        WHY: An empty input means no retrieval backends returned results.
        The fusion stage must handle this gracefully without error.
        """
        from m3_retrieval.stages.fusion import rrf_fusion

        result = rrf_fusion([])
        assert result == []
        assert isinstance(result, list)

    def test_single_input_passthrough(self) -> None:
        """
        WHAT: Passing a single result set returns its chunks re-scored
        via RRF with source="fusion".

        WHY: When only one retriever runs (e.g. dense-only mode), the
        fusion stage should still normalize scores via RRF and mark the
        source as "fusion" so downstream stages see consistent source
        metadata.
        """
        from m3_retrieval.stages.fusion import rrf_fusion

        chunks = [
            _make_scored("c001", "chunk A", score=0.95, source="dense"),
            _make_scored("c002", "chunk B", score=0.80, source="dense"),
            _make_scored("c003", "chunk C", score=0.60, source="dense"),
        ]
        result = rrf_fusion([chunks], top_k=50)

        assert len(result) == 3
        # All results should have source="fusion"
        for r in result:
            assert r.source == "fusion", (
                f"Expected source='fusion', got '{r.source}'"
            )
        # Original order should be preserved (RRF for single list
        # produces monotonically decreasing scores following rank)
        assert result[0].chunk.chunk_id == "c001"
        assert result[1].chunk.chunk_id == "c002"
        assert result[2].chunk.chunk_id == "c003"

    def test_dedup_by_chunk_id(self) -> None:
        """
        WHAT: When the same chunk appears in multiple result sets
        (identified by chunk_id), it should appear only once in the
        fused output with accumulated RRF scores.

        WHY: A chunk that ranks highly in both dense and sparse retrieval
        is a strong signal of relevance. RRF accumulates the scores so
        that chunks appearing in multiple backends get boosted, while
        deduplicating so the user doesn't see the same chunk twice.
        """
        from m3_retrieval.stages.fusion import rrf_fusion

        # Create two result sets with overlapping chunk c002
        chunk_c001 = _make_scored("c001", "shared chunk", score=0.95, source="dense")
        chunk_c002 = _make_scored("c002", "shared chunk", score=0.85, source="dense")
        chunk_c003 = _make_scored("c003", "unique A", score=0.75, source="dense")

        # Same chunk c002 appears in sparse results too (different rank)
        chunk_c002_dup = _make_scored("c002", "shared chunk", score=0.90, source="sparse")
        chunk_c004 = _make_scored("c004", "unique B", score=0.70, source="sparse")

        dense_results = [chunk_c001, chunk_c002, chunk_c003]
        sparse_results = [chunk_c002_dup, chunk_c004]

        result = rrf_fusion([dense_results, sparse_results], top_k=50)

        # Should have 4 unique chunks (c001, c002, c003, c004)
        assert len(result) == 4

        # Verify no duplicate chunk_ids
        chunk_ids = [c.chunk.chunk_id for c in result]
        assert len(chunk_ids) == len(set(chunk_ids)), (
            f"Duplicate chunk_ids found in fused result: {chunk_ids}"
        )

        # Verify c002 appears only once
        assert chunk_ids.count("c002") == 1

        # All results should have source="fusion"
        for r in result:
            assert r.source == "fusion"

    def test_score_decreases_with_rank(self) -> None:
        """
        WHAT: RRF scores should be monotonically non-increasing as rank
        position increases within a single result set.

        WHY: RRF formula is 1/(k + rank) where rank starts at 1.
        This ensures that higher-ranked (lower rank number) items
        get higher scores, reflecting the reciprocal relationship.
        Scores must strictly decrease as rank goes up.
        """
        from m3_retrieval.stages.fusion import rrf_fusion

        # Create a single result set with 5 chunks
        chunks = [
            _make_scored("c001", "rank 1", score=0.99, source="dense"),
            _make_scored("c002", "rank 2", score=0.80, source="dense"),
            _make_scored("c003", "rank 3", score=0.60, source="dense"),
            _make_scored("c004", "rank 4", score=0.40, source="dense"),
            _make_scored("c005", "rank 5", score=0.20, source="dense"),
        ]

        result = rrf_fusion([chunks], top_k=50)

        assert len(result) == 5

        # RRF scores should be strictly decreasing
        for i in range(len(result) - 1):
            rrf_score_current = result[i].score
            rrf_score_next = result[i + 1].score
            assert rrf_score_current > rrf_score_next, (
                f"RRF scores must be strictly decreasing: "
                f"rank {i + 1}={rrf_score_current:.6f}, "
                f"rank {i + 2}={rrf_score_next:.6f}"
            )

    def test_top_k_limit(self) -> None:
        """
        WHAT: When top_k is smaller than the fused result count, only
        the top_k highest-scoring chunks are returned.

        WHY: The pipeline needs to control how many chunks flow into
        downstream stages (reranker, context expansion). top_k limits
        the fused output to avoid overwhelming later stages.
        """
        from m3_retrieval.stages.fusion import rrf_fusion

        # Create two result sets with more chunks than top_k
        dense_chunks = [
            _make_scored(f"c{i:03d}", f"dense chunk {i}", score=0.9, source="dense")
            for i in range(10)
        ]
        sparse_chunks = [
            _make_scored(f"s{i:03d}", f"sparse chunk {i}", score=0.8, source="sparse")
            for i in range(10)
        ]

        result = rrf_fusion([dense_chunks, sparse_chunks], top_k=10)

        assert len(result) == 10
        # All should be unique
        chunk_ids = [c.chunk.chunk_id for c in result]
        assert len(chunk_ids) == len(set(chunk_ids))
