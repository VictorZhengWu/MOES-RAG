"""
Tests for m5_qa.pipelines.simple — Simple RAG pipeline (M3 only).

WHAT: Unit tests for execute_simple() using mock LLM, retriever, and prompt
      manager. No real API calls are made.
WHY: TDD ensures the pipeline works correctly end-to-end before integration
     with live backends.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from contracts.document import Chunk, DocumentMetadata
from contracts.retrieval import ScoredChunk

from m5_qa.pipelines.simple import execute_simple


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_client():
    """
    WHAT: Mock LLMClient that returns a canned response dict.
    WHY: Avoids real API calls during unit testing.
    """
    client = MagicMock()
    client.complete = AsyncMock(return_value={
        "choices": [{"message": {"content": "The preheat temperature is 150°C."}}],
    })
    return client


@pytest.fixture
def mock_retriever():
    """
    WHAT: Mock RetrievalClient with M3-only simple_retrieve.
    WHY: simple mode only uses M3, so parallel_retrieve is not needed.
    """
    from m5_qa.context.retriever import RetrievalContext

    client = MagicMock()
    client.simple_retrieve = AsyncMock()
    return client


@pytest.fixture
def mock_prompt_manager():
    """
    WHAT: Mock PromptManager that returns a canned template.
    WHY: Avoids SQLite dependency during unit testing.
    """
    manager = MagicMock()
    manager.get_prompt = AsyncMock(
        return_value="You are an expert. Context: {retrieved_context} Graph: {graph_context}"
    )
    manager.fill_template = MagicMock(
        return_value="You are an expert. Context: [Source 1] DNV rules... Graph: (not available)"
    )
    return manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scored_chunk(text: str, score: float, source: str, citation: str) -> ScoredChunk:
    """
    WHAT: Factory helper to create a ScoredChunk with minimal metadata.
    WHY: Reduces boilerplate in test setup; the pipeline only reads chunk.text,
         chunk.metadata.*, score, source, and citation.
    """
    meta = DocumentMetadata(
        source_filename="dnv_rules.pdf",
        regulation_name="DNV-OS-C101",
        chapter_section="Sec.2 Ch.3",
    )
    chunk = Chunk(
        chunk_id="chunk-001",
        text=text,
        metadata=meta,
        chunk_type="clause",
    )
    return ScoredChunk(chunk=chunk, score=score, source=source, citation=citation)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExecuteSimple:
    """
    WHAT: Test suite for execute_simple() — the Basic-tier pipeline.
    WHY: Ensures the simple pipeline correctly orchestrates: retrieve ->
         token budget -> prompt -> LLM -> citations.
    """

    @pytest.mark.asyncio
    async def test_simple_returns_answer(
        self, mock_llm_client, mock_retriever, mock_prompt_manager
    ):
        """
        WHAT: Verify that execute_simple returns an answer with citations
              when M3 returns chunks and LLM produces a response.
        WHY: This is the happy-path for the simple pipeline — the most
             common user scenario.
        """
        from m5_qa.context.retriever import RetrievalContext

        # Arrange: M3 returns 2 scored chunks
        chunks = [
            _make_scored_chunk(
                "Preheat temperature shall be at least 100°C.",
                score=0.85, source="dense", citation="1"
            ),
            _make_scored_chunk(
                "Welding inspection criteria per DNV-OS-C101.",
                score=0.70, source="dense", citation="2"
            ),
        ]
        mock_retriever.simple_retrieve.return_value = RetrievalContext(chunks=chunks, graph=None)

        # Act: execute the simple pipeline
        result = await execute_simple(
            query="What is the required preheat temperature?",
            llm_client=mock_llm_client,
            retriever=mock_retriever,
            prompt_manager=mock_prompt_manager,
            tier="basic",
        )

        # Assert: result has answer and citations
        assert "answer" in result
        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0
        assert "citations" in result
        assert isinstance(result["citations"], list)
        # Verify retrieval was called with correct args
        mock_retriever.simple_retrieve.assert_awaited_once_with("What is the required preheat temperature?")
        # Verify LLM was called
        mock_llm_client.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_simple_no_chunks(
        self, mock_llm_client, mock_retriever, mock_prompt_manager
    ):
        """
        WHAT: Verify that execute_simple still works when no chunks are
              retrieved from M3.
        WHY: Users may ask questions that have no matching documents. The
             LLM should still answer based on its own knowledge rather
             than returning an error.
        """
        from m5_qa.context.retriever import RetrievalContext

        # Arrange: M3 returns zero chunks
        mock_retriever.simple_retrieve.return_value = RetrievalContext(chunks=[], graph=None)

        # Act
        result = await execute_simple(
            query="What is the capital of France?",
            llm_client=mock_llm_client,
            retriever=mock_retriever,
            prompt_manager=mock_prompt_manager,
            tier="basic",
        )

        # Assert: should still get an answer (from LLM's own knowledge)
        assert "answer" in result
        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0
        # Citations should be empty (no chunks to build from)
        assert result["citations"] == []
        # LLM was still called
        mock_llm_client.complete.assert_awaited_once()
