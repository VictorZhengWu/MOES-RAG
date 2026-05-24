# -*- coding: utf-8 -*-
"""
Tests for M3 Cross-Encoder Reranker stage (reranker.py).

WHAT: Validates three behaviours of the Reranker class:
  1. test_rerank_empty_returns_empty: Passing an empty list returns
     an empty list without loading the model.
  2. test_lazy_load: Constructing a Reranker does NOT load the model
     eagerly. The model is loaded only on the first call to rerank().
  3. test_rerank_changes_order: Reranking with high-quality query-document
     pairs should reorder chunks, placing more relevant ones first.

WHY: Cross-encoder reranking is the final precision filter in the
retrieval pipeline. It compares each query-chunk pair directly rather
than relying solely on embedding similarity. Lazy loading is critical
because the BGE reranker model is ~2GB and should not load at module
import or construction time.
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
    Create a minimal Chunk for testing.
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
# Reranker skip marker
# =============================================================================

# WHAT: uses a subprocess to check if FlagEmbedding can actually be imported
# without crashing. Does NOT import FlagEmbedding in the current process.
# WHY: on some Windows + Python 3.13 environments, importing FlagEmbedding
# triggers sklearn -> pandas -> pyarrow which segfaults due to DLL conflicts.
# Running the import check in a subprocess isolates the crash: if the subprocess
# crashes, we correctly treat FlagEmbedding as unavailable.
import subprocess
import sys


def _flagembedding_available() -> bool:
    """
    Check if FlagEmbedding can be safely imported.

    WHAT: spawns a subprocess to try importing FlagReranker. If the
    subprocess exits with code 0, FlagEmbedding is available.

    WHY: importing FlagEmbedding in-process crashes on some environments.
    Using a subprocess isolates the crash and lets us safely detect
    whether the import works.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-c", "from FlagEmbedding import FlagReranker"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return False


FLAGEMBEDDING_AVAILABLE = _flagembedding_available()
FLAGEMBEDDING_REASON = (
    "FlagEmbedding is not available in this environment (either not installed "
    "or cannot be imported due to native dependency issues). "
    "Install it with: pip install FlagEmbedding>=1.2.0"
)


# =============================================================================
# Reranker tests — no FlagEmbedding needed
# =============================================================================


class TestRerankerEmpty:
    """Test rerank() edge cases that do NOT require the model."""

    def test_rerank_empty_returns_empty(self) -> None:
        """
        WHAT: Calling rerank() with an empty list must return an empty
        list immediately, without loading the model.

        WHY: Empty input is normal when previous stages found nothing.
        We must not load the model (expensive ~2GB) for a no-op.
        """
        from m3_retrieval.stages.reranker import Reranker

        reranker = Reranker(model_name="BAAI/bge-reranker-v2-m3", top_k=20)
        result = reranker.rerank_sync("test query", [])

        assert result == []
        assert isinstance(result, list)


class TestRerankerLazyLoad:
    """Test that the Reranker does NOT eagerly load the model."""

    def test_constructor_does_not_load_model(self) -> None:
        """
        WHAT: After constructing a Reranker, the internal _model attribute
        must be None, proving that the model was NOT loaded eagerly.

        WHY: The constructor is called during pipeline assembly. If it
        loaded the model, every import and test would incur a 3--5 second
        penalty. Lazy loading ensures the model loads only on first use.
        """
        from m3_retrieval.stages.reranker import Reranker

        reranker = Reranker(model_name="BAAI/bge-reranker-v2-m3")
        assert reranker._model is None, (
            "Reranker.__init__ loaded the model eagerly. "
            "Model must load on first rerank(), not on construction."
        )
        assert reranker.top_k == 20


# =============================================================================
# Reranker tests — require FlagEmbedding
# =============================================================================


@pytest.mark.skipif(not FLAGEMBEDDING_AVAILABLE, reason=FLAGEMBEDDING_REASON)
class TestRerankerModel:
    """Test rerank() with the real BGE-Reranker model."""

    def test_rerank_changes_order(self) -> None:
        """
        WHAT: Given two chunks -- one relevant to the query and one
        irrelevant -- the reranker should place the relevant chunk
        before the irrelevant one.

        The test constructs:
          - query: "welding procedure specification for AH36 steel"
          - relevant chunk: contains welding and steel content
          - irrelevant chunk: contains unrelated content about food

        WHY: The cross-encoder directly compares the query with each
        chunk's text, producing a relevance score more accurate than
        embedding similarity. The reranker must reorder chunks so the
        most relevant appears first.

        Note: This is a best-effort test. Very small cross-encoders
        or edge cases may not produce the expected ordering. The test
        validates the pipeline integration (correct input/output types,
        source annotation, score transformation), not that every pair
        is perfectly ordered.
        """
        from m3_retrieval.stages.reranker import Reranker

        # Create a relevant chunk (about welding and steel)
        relevant = _make_scored(
            chunk_id="c_relevant",
            text=(
                "Welding procedure specification for AH36 steel plate. "
                "Preheat temperature shall be 100 degrees Celsius minimum. "
                "Interpass temperature shall not exceed 250 degrees Celsius. "
                "Post-weld heat treatment is required for thicknesses above 50mm."
            ),
            score=0.75,
            source="fusion",
            source_filename="DNV-ST-N001.pdf",
            domain=Domain.STRUCTURE,
        )

        # Create an irrelevant chunk (about food, completely unrelated)
        irrelevant = _make_scored(
            chunk_id="c_irrelevant",
            text=(
                "The cafeteria serves lunch from 11:30 AM to 1:30 PM daily. "
                "Menu items include sandwiches, salads, and hot entrees. "
                "Vegetarian and vegan options are available upon request. "
                "Payment is accepted via meal card or credit card."
            ),
            score=0.80,  # Higher initial score from fusion
            source="fusion",
            source_filename="office-guide.pdf",
            domain=Domain.GENERAL,
        )

        chunks = [irrelevant, relevant]  # Irrelevant first (higher pre-rerank score)
        reranker = Reranker(model_name="BAAI/bge-reranker-v2-m3", top_k=20)

        result = reranker.rerank_sync(
            "welding procedure specification for AH36 steel", chunks
        )

        assert len(result) == 2

        # The relevant chunk should now be first
        assert result[0].chunk.chunk_id == "c_relevant", (
            f"Expected relevant chunk first, got '{result[0].chunk.chunk_id}'"
        )
        assert result[1].chunk.chunk_id == "c_irrelevant"

        # Verify source annotation: should contain reranked(...)
        assert "reranked" in result[0].source, (
            f"Expected source to contain 'reranked', got '{result[0].source}'"
        )
        assert "reranked" in result[1].source

        # Verify scores are floats
        assert isinstance(result[0].score, float)
        assert isinstance(result[1].score, float)
