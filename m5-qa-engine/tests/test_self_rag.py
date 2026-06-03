"""
Tests for m5_qa.pipelines.self_rag — Self-RAG (iterative retrieval with quality check).

WHAT: Unit tests for execute_self_rag() using mock LLM, retriever, and prompt
      manager. All tests use mocks — no real M3/M4/LLM calls.
WHY: Self-RAG iterates retrieval with synonym expansion until the best
     chunk score meets a threshold, handling insufficient scores, retries,
     and max-iteration termination.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from contracts.document import Chunk, DocumentMetadata
from contracts.knowledge_graph import Entity, Subgraph
from contracts.retrieval import ScoredChunk

from m5_qa.pipelines.self_rag import execute_self_rag, _expand_query


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_client():
    """Mock LLMClient that returns a canned response."""
    client = MagicMock()
    client.complete = AsyncMock(return_value={
        "choices": [{"message": {"content": "Preheat temperature: 100-150°C per DNV-OS-C101."}}],
    })
    return client


@pytest.fixture
def mock_retriever():
    """Mock RetrievalClient with configurable parallel_retrieve."""
    from m5_qa.context.retriever import RetrievalContext

    client = MagicMock()
    client.parallel_retrieve = AsyncMock()
    return client


@pytest.fixture
def mock_prompt_manager():
    """Mock PromptManager."""
    manager = MagicMock()
    manager.get_prompt = AsyncMock(
        return_value="Expert. Context: {retrieved_context} Graph: {graph_context}"
    )
    manager.fill_template = MagicMock(
        return_value="Expert. Context: ... Graph: ..."
    )
    return manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context_with_score(score: float, query_context: str = "test query") -> "RetrievalContext":
    """
    WHAT: Build a RetrievalContext with a single chunk having the given score
          and a minimal graph subgraph.
    WHY: Self-RAG checks the top chunk score; this helper makes it easy to
         control the score in tests.
    """
    from m5_qa.context.retriever import RetrievalContext

    meta = DocumentMetadata(
        source_filename="dnv_rules.pdf",
        regulation_name="DNV-OS-C101",
        chapter_section="Sec.2",
    )
    chunk = Chunk(
        chunk_id="chunk-001",
        text="Preheat temperature shall be at least 100°C.",
        metadata=meta,
        chunk_type="clause",
    )
    scored = ScoredChunk(chunk=chunk, score=score, source="dense", citation="1")
    graph = Subgraph(
        entities=[
            Entity(entity_id="e1", name="DNV-OS-C101", entity_type="regulation_clause"),
        ],
        relations=[],
        query_context=query_context,
    )
    return RetrievalContext(chunks=[scored], graph=graph)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExecuteSelfRag:
    """
    WHAT: Test suite for execute_self_rag() — the Enterprise-tier pipeline.
    WHY: Ensures the iterative retrieval pipeline correctly decides when to
         stop, retry with synonym expansion, or give up after max iterations.
    """

    @pytest.mark.asyncio
    async def test_self_rag_sufficient_first_try(
        self, mock_llm_client, mock_retriever, mock_prompt_manager
    ):
        """
        WHAT: Verify that Self-RAG stops after the first retrieval when
              the chunk score already exceeds the threshold.
        WHY: The most common path — when good documents exist, we should
             not waste time on unnecessary re-retrievals.
        """
        # Arrange: first retrieval score 0.85 >= threshold 0.5
        ctx = _make_context_with_score(score=0.85)
        mock_retriever.parallel_retrieve.return_value = ctx

        # Act
        result = await execute_self_rag(
            query="preheat temperature requirement?",
            llm_client=mock_llm_client,
            retriever=mock_retriever,
            prompt_manager=mock_prompt_manager,
            tier="enterprise",
            score_threshold=0.5,
            max_iterations=3,
        )

        # Assert
        assert "answer" in result
        assert result["iterations"] == 1
        # Should be called exactly once (no retry)
        assert mock_retriever.parallel_retrieve.call_count == 1
        mock_llm_client.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_self_rag_retry(
        self, mock_llm_client, mock_retriever, mock_prompt_manager
    ):
        """
        WHAT: Verify that Self-RAG retries with synonym-expanded query when
              the first retrieval score is below threshold.
        WHY: When initial retrieval fails to find high-quality matches,
             synonym expansion should broaden the search and find better
             chunks on the second attempt.
        """
        from m5_qa.context.retriever import RetrievalContext

        # Arrange: first try returns low score (0.2), second try gets 0.75
        low_score_ctx = _make_context_with_score(score=0.2)
        high_score_ctx = _make_context_with_score(score=0.75)

        # The retriever returns different results on each call
        mock_retriever.parallel_retrieve.side_effect = [
            low_score_ctx,
            high_score_ctx,
        ]

        # Act
        result = await execute_self_rag(
            query="welding requirement for thick plates?",
            llm_client=mock_llm_client,
            retriever=mock_retriever,
            prompt_manager=mock_prompt_manager,
            tier="enterprise",
            score_threshold=0.5,
            max_iterations=3,
        )

        # Assert
        assert "answer" in result
        assert result["iterations"] == 2
        assert result["best_score"] == 0.75
        # Called twice — first try + one retry
        assert mock_retriever.parallel_retrieve.call_count == 2
        mock_llm_client.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_self_rag_max_iterations(
        self, mock_llm_client, mock_retriever, mock_prompt_manager
    ):
        """
        WHAT: Verify that Self-RAG stops after max_iterations even when
              scores never reach the threshold, and still returns the best
              result from all attempts.
        WHY: Prevents infinite looping when no relevant documents exist.
             The user should still get an answer based on the best
             available retrieval.
        """
        # Arrange: all retrievals return low scores (below threshold)
        ctx1 = _make_context_with_score(score=0.1)
        ctx2 = _make_context_with_score(score=0.15)
        ctx3 = _make_context_with_score(score=0.12)

        mock_retriever.parallel_retrieve.side_effect = [ctx1, ctx2, ctx3]

        # Act
        result = await execute_self_rag(
            query="very obscure topic with no documents",
            llm_client=mock_llm_client,
            retriever=mock_retriever,
            prompt_manager=mock_prompt_manager,
            tier="enterprise",
            score_threshold=0.5,
            max_iterations=3,
        )

        # Assert
        assert "answer" in result
        assert result["iterations"] == 3
        # Best score should be the highest across all attempts (0.15)
        assert result["best_score"] == 0.15
        # Called max_iterations times
        assert mock_retriever.parallel_retrieve.call_count == 3
        # LLM should still get the best available context
        mock_llm_client.complete.assert_awaited_once()


class TestExpandQuery:
    """
    WHAT: Unit tests for _expand_query(), the synonym expansion helper.
    WHY: _expand_query is a pure function — no mocks needed. Testing it
         in isolation is the simplest and most reliable approach.
    """

    def test_expand_query_adds_synonym(self):
        """
        WHAT: Verify that _expand_query appends the correct synonym based
              on the iteration index.
        WHY: On iteration 0, "welding" should expand to include "weld".
        """
        result = _expand_query("welding procedure", iteration=0)
        # Should contain original + first synonym for "welding"
        assert "welding" in result.lower()
        assert "weld" in result.lower()

    def test_expand_query_no_match(self):
        """
        WHAT: Verify that _expand_query returns the original query unchanged
              when no known synonym keywords are found.
        WHY: If the query doesn't contain any known domain term, there's
             nothing to expand — return as-is.
        """
        result = _expand_query("how are you today", iteration=0)
        assert result == "how are you today"

    def test_expand_query_preheat_synonym(self):
        """
        WHAT: Verify preheat synonym expansion on iteration 0.
        WHY: "preheat" should expand to add "pre-heat" (iteration 0).
        """
        result = _expand_query("preheat temperature", iteration=0)
        assert "preheat" in result.lower()
        assert "pre-heat" in result.lower()

    def test_expand_query_thickness_synonym(self):
        """
        WHAT: Verify thickness synonym expansion.
        WHY: "thickness" should expand to add "plate thickness" (iteration 0).
        """
        result = _expand_query("minimum thickness value", iteration=0)
        assert "thickness" in result.lower()
        assert "plate thickness" in result.lower()
