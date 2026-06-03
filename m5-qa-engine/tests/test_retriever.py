"""
Tests for M5 QA Engine — Retrieval Client (retriever.py).

WHAT: Unit tests for RetrievalClient which coordinates M3 retrieval and
      M4 knowledge graph search for the RAG pipeline.

WHY: The RetrievalClient is the bridge between M5 and the lower-layer engines
     (M3 Retrieval, M4 Knowledge Graph). It must handle both simple (M3-only)
     and parallel (M3+M4) retrieval modes gracefully, including M4 failures.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from contracts.document import Chunk, DocumentMetadata
from contracts.knowledge_graph import Entity, Relation, Subgraph
from contracts.retrieval import RetrievedContext, ScoredChunk


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

def _make_chunk(chunk_id: str, text: str) -> Chunk:
    """Create a minimal Chunk for testing."""
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        metadata=DocumentMetadata(source_filename=f"{chunk_id}.pdf"),
        chunk_type="clause",
    )


def _make_scored_chunk(chunk_id: str, text: str, score: float = 0.9) -> ScoredChunk:
    """Create a minimal ScoredChunk for testing."""
    return ScoredChunk(
        chunk=_make_chunk(chunk_id, text),
        score=score,
        source="dense",
        citation=f"[{chunk_id}]",
    )


def _make_entity(entity_id: str, name: str, entity_type: str = "regulation_clause") -> Entity:
    """Create a minimal Entity for testing."""
    return Entity(entity_id=entity_id, name=name, entity_type=entity_type)


def _make_relation(
    relation_id: str, source_id: str, target_id: str, relation_type: str = "references"
) -> Relation:
    """Create a minimal Relation for testing."""
    return Relation(
        relation_id=relation_id,
        source_entity_id=source_id,
        target_entity_id=target_id,
        relation_type=relation_type,
    )


def _make_subgraph(entities: list[Entity], relations: list[Relation]) -> Subgraph:
    """Create a minimal Subgraph for testing."""
    return Subgraph(
        entities=entities,
        relations=relations,
        query_context="test query",
    )


# ---------------------------------------------------------------------------
# Tests: RetrievalClient
# ---------------------------------------------------------------------------

class TestSimpleRetrieve:
    """Tests for RetrievalClient.simple_retrieve() — M3-only mode."""

    @pytest.mark.asyncio
    async def test_simple_retrieve_returns_m3_chunks(self):
        """
        WHAT: simple_retrieve() calls M3.retrieve() and returns chunks, M4 is not called.

        WHY: The simple pipeline mode only uses M3 semantic search.
             M4 graph traversal adds cost — it should NOT be invoked
             in simple mode.
        """
        from m5_qa.context.retriever import RetrievalClient

        # Mock M3 engine that returns 2 chunks
        mock_m3 = AsyncMock()
        mock_m3.retrieve.return_value = RetrievedContext(
            chunks=[
                _make_scored_chunk("chunk_1", "DNV Pt.4 Ch.3 steel requirements"),
                _make_scored_chunk("chunk_2", "ABS steel grade DH36 specifications"),
            ],
            total_found=2,
            search_latency_ms=15.0,
        )

        # Mock M4 engine — should NOT be called in simple mode
        mock_m4 = AsyncMock()

        client = RetrievalClient(m3_engine=mock_m3, m4_engine=mock_m4)
        result = await client.simple_retrieve("steel requirements", top_k=5)

        # Verify M3 was called with correct parameters
        mock_m3.retrieve.assert_awaited_once()
        call_args = mock_m3.retrieve.call_args[0][0]
        assert call_args.query == "steel requirements"
        assert call_args.top_k == 5

        # Verify M4 was NOT called
        mock_m4.graph_search.assert_not_awaited()

        # Verify result contains M3 chunks
        assert len(result.chunks) == 2
        assert result.chunks[0].chunk.text == "DNV Pt.4 Ch.3 steel requirements"
        assert result.graph is None


class TestParallelRetrieve:
    """Tests for RetrievalClient.parallel_retrieve() — M3+M4 parallel mode."""

    @pytest.mark.asyncio
    async def test_parallel_retrieve_returns_both_results(self):
        """
        WHAT: parallel_retrieve() calls M3 and M4 via asyncio.gather, returns merged result.

        WHY: The pipeline and self_rag modes need both semantic search results
             (from M3) and knowledge graph results (from M4). Running them
             in parallel reduces latency since they are independent operations.
        """
        from m5_qa.context.retriever import RetrievalClient

        # Mock M3 engine
        mock_m3 = AsyncMock()
        mock_m3.retrieve.return_value = RetrievedContext(
            chunks=[
                _make_scored_chunk("chunk_1", "DNV Pt.4 Ch.3 steel requirements"),
            ],
            total_found=1,
            search_latency_ms=12.0,
        )

        # Mock M4 engine
        mock_m4 = AsyncMock()
        mock_m4.graph_search.return_value = _make_subgraph(
            entities=[
                _make_entity("e1", "DNV Pt.4 Ch.3", "regulation_clause"),
                _make_entity("e2", "DH36", "steel_grade"),
            ],
            relations=[
                _make_relation("r1", "e1", "e2", "constrains"),
            ],
        )

        client = RetrievalClient(m3_engine=mock_m3, m4_engine=mock_m4)
        result = await client.parallel_retrieve("steel grade DH36", top_k=20, kg_depth=2)

        # Verify both engines were called
        mock_m3.retrieve.assert_awaited_once()
        mock_m4.graph_search.assert_awaited_once()
        call_args = mock_m4.graph_search.call_args
        assert call_args.kwargs["topic"] == "steel grade DH36"
        assert call_args.kwargs["depth"] == 2

        # Verify merged result
        assert len(result.chunks) == 1
        assert result.chunks[0].chunk.text == "DNV Pt.4 Ch.3 steel requirements"
        assert result.graph is not None
        assert len(result.graph.entities) == 2
        assert result.graph.entities[0].name == "DNV Pt.4 Ch.3"
        assert len(result.graph.relations) == 1


class TestM4GracefulFailure:
    """Tests for graceful degradation when M4 fails."""

    @pytest.mark.asyncio
    async def test_m4_failure_still_returns_m3_results(self):
        """
        WHAT: When M4.graph_search() raises an exception, parallel_retrieve()
              still returns M3 chunks with graph=None.

        WHY: The knowledge graph is an enhancement, not a requirement.
             If M4 is unavailable (database down, timeout, etc.), the system
             must still provide useful answers from M3 retrieval alone.
             Graceful degradation is essential for production reliability.
        """
        from m5_qa.context.retriever import RetrievalClient

        # Mock M3 engine — works fine
        mock_m3 = AsyncMock()
        mock_m3.retrieve.return_value = RetrievedContext(
            chunks=[
                _make_scored_chunk("chunk_1", "CCS rules for bulk carriers"),
                _make_scored_chunk("chunk_2", "IMO SOLAS Chapter II-1"),
            ],
            total_found=2,
            search_latency_ms=18.0,
        )

        # Mock M4 engine — raises an exception
        mock_m4 = AsyncMock()
        mock_m4.graph_search.side_effect = RuntimeError("Kuzu database connection failed")

        client = RetrievalClient(m3_engine=mock_m3, m4_engine=mock_m4)
        result = await client.parallel_retrieve("bulk carrier rules")

        # Verify M3 results are still returned despite M4 failure
        assert len(result.chunks) == 2
        assert result.chunks[0].chunk.text == "CCS rules for bulk carriers"
        assert result.chunks[1].chunk.text == "IMO SOLAS Chapter II-1"

        # Graph should be None (M4 failed)
        assert result.graph is None
