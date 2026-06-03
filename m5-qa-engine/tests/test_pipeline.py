"""
Tests for m5_qa.pipelines.pipeline — Pipeline RAG (M3+M4 parallel).

WHAT: Unit tests for execute_pipeline() using mock LLM, retriever, and prompt
      manager. All tests use mocks — no real M3/M4/LLM calls.
WHY: TDD ensures the pipeline correctly orchestrates parallel retrieval,
     fusion, prompt building, LLM generation, and citation processing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from contracts.document import Chunk, DocumentMetadata
from contracts.knowledge_graph import Entity, Relation, Subgraph
from contracts.retrieval import ScoredChunk

from m5_qa.pipelines.pipeline import execute_pipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_client():
    """Mock LLMClient that returns a canned response."""
    client = MagicMock()
    client.complete = AsyncMock(return_value={
        "choices": [{"message": {"content": "Per DNV-OS-C101 [1], the preheat temperature is 150°C."}}],
    })
    return client


@pytest.fixture
def mock_retriever():
    """Mock RetrievalClient supporting parallel_retrieve."""
    from m5_qa.context.retriever import RetrievalContext

    client = MagicMock()
    # Default: both M3 and M4 return data
    client.parallel_retrieve = AsyncMock()
    return client


@pytest.fixture
def mock_prompt_manager():
    """Mock PromptManager with canned template."""
    manager = MagicMock()
    manager.get_prompt = AsyncMock(
        return_value="Expert. Context: {retrieved_context} Graph: {graph_context}"
    )
    manager.fill_template = MagicMock(
        return_value="Expert. Context: [Source 1] ... Graph: - DNV-OS-C101 (regulation_clause)"
    )
    return manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scored_chunk(text: str, score: float, source: str, citation: str) -> ScoredChunk:
    """Factory for ScoredChunk with minimal metadata."""
    meta = DocumentMetadata(
        source_filename="dnv_rules.pdf",
        regulation_name="DNV-OS-C101",
        chapter_section="Sec.2 Ch.3",
    )
    chunk = Chunk(
        chunk_id=f"chunk-{citation}",
        text=text,
        metadata=meta,
        chunk_type="clause",
    )
    return ScoredChunk(chunk=chunk, score=score, source=source, citation=citation)


def _make_entity(entity_id: str, name: str, entity_type: str) -> Entity:
    """Factory for a knowledge graph Entity."""
    return Entity(
        entity_id=entity_id,
        name=name,
        entity_type=entity_type,
        source_doc_id="doc-001",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExecutePipeline:
    """
    WHAT: Test suite for execute_pipeline() — the Pro-tier pipeline.
    WHY: Ensures the pipeline RAG correctly handles M3+M4 parallel retrieval,
         graph text formatting, and citation attachment.
    """

    @pytest.mark.asyncio
    async def test_pipeline_parallel(
        self, mock_llm_client, mock_retriever, mock_prompt_manager
    ):
        """
        WHAT: Verify that execute_pipeline returns answer with attached
              citations when both M3 and M4 return data.
        WHY: This is the happy-path for Pro tier users. Both retrieval
             sources should be fused and citations attached.
        """
        from m5_qa.context.retriever import RetrievalContext

        # Arrange: M3 returns 2 chunks, M4 returns a subgraph
        chunks = [
            _make_scored_chunk(
                "Preheat temperature: min 100°C for thickness > 30mm.",
                score=0.88, source="dense", citation="1"
            ),
            _make_scored_chunk(
                "Post-weld heat treatment per DNV-OS-C101 Sec.5.",
                score=0.82, source="dense", citation="2"
            ),
        ]
        graph = Subgraph(
            entities=[
                _make_entity("e1", "DNV-OS-C101", "regulation_clause"),
                _make_entity("e2", "Preheat Temperature", "parameter"),
            ],
            relations=[
                Relation(
                    relation_id="r1",
                    source_entity_id="e1",
                    target_entity_id="e2",
                    relation_type="constrains",
                ),
            ],
            query_context="preheat temperature requirements",
        )
        mock_retriever.parallel_retrieve.return_value = RetrievalContext(
            chunks=chunks, graph=graph
        )

        # Act
        result = await execute_pipeline(
            query="What is the preheat temperature for thick plates?",
            llm_client=mock_llm_client,
            retriever=mock_retriever,
            prompt_manager=mock_prompt_manager,
            tier="pro",
            kg_depth=3,
        )

        # Assert
        assert "answer" in result
        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0
        assert "citations" in result
        assert isinstance(result["citations"], list)
        # Verify parallel_retrieve was called with correct args
        mock_retriever.parallel_retrieve.assert_awaited_once_with(
            "What is the preheat temperature for thick plates?", kg_depth=3
        )
        # LLM was called
        mock_llm_client.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pipeline_no_graph(
        self, mock_llm_client, mock_retriever, mock_prompt_manager
    ):
        """
        WHAT: Verify that execute_pipeline handles missing M4 data gracefully,
              producing "no graph insights" placeholder text.
        WHY: M4 may be unavailable or return nothing for certain queries.
             The pipeline should not fail — it should continue with M3-only
             context and indicate that no graph data was found.
        """
        from m5_qa.context.retriever import RetrievalContext

        # Arrange: M3 returns chunks, but M4 returns None (or empty subgraph)
        chunks = [
            _make_scored_chunk(
                "General welding requirements.",
                score=0.75, source="dense", citation="1"
            ),
        ]
        # graph=None simulates M4 being unavailable or returning no results
        mock_retriever.parallel_retrieve.return_value = RetrievalContext(
            chunks=chunks, graph=None
        )

        # Act
        result = await execute_pipeline(
            query="General welding requirements?",
            llm_client=mock_llm_client,
            retriever=mock_retriever,
            prompt_manager=mock_prompt_manager,
            tier="pro",
        )

        # Assert: pipeline should not fail
        assert "answer" in result
        assert isinstance(result["answer"], str)
        # Citations should still be built from M3 chunks
        assert "citations" in result
        # The fill_template should have been called with a graph_context
        # containing "no graph insights"
        call_kwargs = mock_prompt_manager.fill_template.call_args
        assert call_kwargs is not None
        # graph_context should contain the "no graph insights" text
        assert "no graph insights" in call_kwargs[1]["graph_context"].lower()
