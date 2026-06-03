"""
Tests for M5 QA Engine — Context Fusion (fusion.py).

WHAT: Unit tests for fuse_context() which merges M3 retrieved chunks and
      M4 knowledge graph results into a single context string for the LLM prompt.

WHY: The fusion module is the final formatting step before the retrieval context
     enters the LLM prompt. It must handle chunk-only, graph-only, and mixed
     scenarios, and must respect the token budget to avoid overflowing the
     context window.
"""

from contracts.document import Chunk, DocumentMetadata
from contracts.knowledge_graph import Entity, Relation, Subgraph
from contracts.retrieval import ScoredChunk


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


def _make_scored_chunk(
    chunk_id: str, text: str, score: float = 0.9, citation: str = ""
) -> ScoredChunk:
    """Create a minimal ScoredChunk for testing."""
    return ScoredChunk(
        chunk=_make_chunk(chunk_id, text),
        score=score,
        source="dense",
        citation=citation or f"[{chunk_id}]",
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


def _make_retrieval_context(chunks=None, graph=None):
    """Create a RetrievalContext with minimal defaults."""
    from m5_qa.context.retriever import RetrievalContext
    return RetrievalContext(chunks=chunks or [], graph=graph)


# ---------------------------------------------------------------------------
# Tests: fuse_context
# ---------------------------------------------------------------------------

class TestFuseChunksOnly:
    """Tests for fuse_context() — chunks-only input (no graph)."""

    def test_fuse_chunks_only_formats_source_blocks(self):
        """
        WHAT: fuse_context() with only M3 chunks produces a "## Document Context"
              section with each chunk formatted as a [Source] block.

        WHY: When no knowledge graph data is available (simple mode), the
             context must still be well-formatted for the LLM prompt. Each
             chunk gets a citation prefix and chunks are separated by blank lines.
        """
        from m5_qa.context.fusion import fuse_context

        ctx = _make_retrieval_context(
            chunks=[
                _make_scored_chunk("c1", "DNV Pt.4 Ch.3 requires steel grade DH36", citation="DNV-Pt4Ch3-2024"),
                _make_scored_chunk("c2", "ABS Part 3 Ch.2 specifies welding procedures", citation="ABS-Pt3Ch2-2024"),
            ]
        )

        result = fuse_context(ctx, max_retrieval_tokens=1000)

        # Should contain the document context heading
        assert "## Document Context" in result

        # Each chunk should have a [Source ...] prefix
        assert "[Source DNV-Pt4Ch3-2024]" in result
        assert "[Source ABS-Pt3Ch2-2024]" in result

        # Should NOT contain knowledge graph section
        assert "## Knowledge Graph" not in result


class TestFuseGraphOnly:
    """Tests for fuse_context() — graph-only input (no chunks)."""

    def test_fuse_graph_only_formats_entities_and_relations(self):
        """
        WHAT: fuse_context() with only M4 graph data produces a
              "## Knowledge Graph" section with entities and relations.

        WHY: Even without semantic search results, the knowledge graph
             provides valuable structured information that helps the LLM
             understand domain relationships (e.g., "DH36 is constrained by
             DNV Pt.4 Ch.3").
        """
        from m5_qa.context.fusion import fuse_context

        entities = [
            _make_entity("e1", "DNV Pt.4 Ch.3", "regulation_clause"),
            _make_entity("e2", "DH36", "steel_grade"),
            _make_entity("e3", "ABS Part 3", "regulation_clause"),
        ]
        relations = [
            _make_relation("r1", "e1", "e2", "constrains"),
        ]
        subgraph = Subgraph(entities=entities, relations=relations, query_context="steel grade")

        ctx = _make_retrieval_context(graph=subgraph)
        result = fuse_context(ctx, max_retrieval_tokens=1000)

        # Should contain the knowledge graph section
        assert "## Knowledge Graph" in result

        # Should contain entities subsection
        assert "### Entities" in result
        assert "- DNV Pt.4 Ch.3 (regulation_clause)" in result
        assert "- DH36 (steel_grade)" in result
        assert "- ABS Part 3 (regulation_clause)" in result

        # Should contain relations subsection
        assert "### Relations" in result
        assert "e1" in result
        assert "constrains" in result
        assert "e2" in result

        # Should NOT contain document context (no chunks provided)
        assert "## Document Context" not in result


class TestFuseTruncation:
    """Tests for fuse_context() — token budget truncation."""

    def test_fuse_truncation_respects_token_budget(self):
        """
        WHAT: fuse_context() stops adding chunks once the token budget is exceeded.

        WHY: The LLM context window is finite (4K/8K/16K tokens). If retrieval
             returns too many chunks, the fusion module must truncate to fit
             within the allocated retrieval token budget. Chunks are included
             in order (highest score first, as returned by M3).

             Each chunk adds roughly: len("[Source X] ") + len(chunk.text) chars
             → estimated tokens = chars // 4.
        """
        from m5_qa.context.fusion import fuse_context

        # Create 3 chunks with known text lengths
        chunks = [
            # ~40 chars → ~10 tokens
            _make_scored_chunk("c1", "A" * 40, citation="ref1"),
            # ~60 chars → ~15 tokens
            _make_scored_chunk("c2", "B" * 60, citation="ref2"),
            # ~80 chars → ~20 tokens
            _make_scored_chunk("c3", "C" * 80, citation="ref3"),
        ]

        ctx = _make_retrieval_context(chunks=chunks)

        # Set budget to ~15 tokens: should fit only first 2 chunks
        # First chunk: "[Source ref1] " (15 chars) + 40 chars = 55 chars → ~13 tokens
        # Adding second chunk: total ~28 tokens > 15 — so only first chunk included
        result = fuse_context(ctx, max_retrieval_tokens=15)

        # First chunk should be present
        assert "[Source ref1]" in result
        # Third chunk should NOT be present (budget exhausted)
        assert "[Source ref3]" not in result
