"""
Tests for cross_reference (cross_reference.py).

WHAT: 3 test cases covering:
  1. Graph lookup: existing similar_to relation found with high confidence.
  2. LLM fallback: no graph match, LLM returns result, result cached as edge.
  3. No match at all: no graph match and no LLM backend, returns None.

WHY: cross_reference is the core inter-society regulation mapping feature.
     The hybrid strategy (graph first, LLM fallback) must correctly:
     - Return fast when a cached similar_to edge exists.
     - Fall back to LLM when no cached edge is available.
     - Cache LLM results for future fast lookups.
     - Return None gracefully when neither method succeeds.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from contracts.knowledge_graph import (
    CrossReferenceResult,
    Entity,
    Relation,
)
from m4_kg.graph.kuzu_store import KuzuStore


# ---------------------------------------------------------------------------
# Fixture: create a fresh KuzuStore backed by a temporary directory
# ---------------------------------------------------------------------------

@pytest.fixture
def store():
    """
    Create a KuzuStore with a fresh temporary database for test isolation.

    WHAT:
    - Creates a temp directory unique to each test.
    - Instantiates KuzuStore pointing at a test.db inside that directory.
    - Yields the store for the test to use.
    - Cleans up the temp directory after the test completes.

    WHY:
    - Each test must start with an empty graph to be independent.
    - Temp directory isolation prevents cross-test data leakage.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="kuzu_xref_test_"))
    db = KuzuStore(db_path=str(tmpdir / "test.db"))
    yield db
    db._conn = None
    db._db = None
    shutil.rmtree(str(tmpdir), ignore_errors=True)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestCrossReference:
    """Test suite for cross_reference function (hybrid strategy)."""

    # ------------------------------------------------------------------
    # Test 1: Graph lookup finds existing similar_to relation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_graph_lookup_found(self, store: KuzuStore):
        """
        Insert a similar_to relation, cross_reference returns it with high confidence.

        WHAT:
        - Insert a DNV entity matching the source clause.
        - Insert an ABS entity in the target society.
        - Insert a similar_to relation between them with confidence=0.95.
        - Call cross_reference — should find via graph lookup directly.

        WHY:
        - The graph lookup path is the fast path: sub-millisecond via Kuzu
          indexes vs. seconds for LLM calls. This test proves the cached
          edge is correctly detected and returned without invoking LLM.
        """
        from m4_kg.search.cross_reference import cross_reference

        # Insert source entity in DNV society
        source_entity = Entity(
            entity_id="dnv_preheat",
            name="DNV Pt.2 Ch.3 §2.1 Preheat Requirements",
            entity_type="regulation_clause",
            properties={"section": "Pt.2 Ch.3 §2.1"},
            source_doc_id="doc_dnv_001",
        )
        await store.insert_entities([source_entity], doc_society="DNV")

        # Insert target entity in ABS society
        target_entity = Entity(
            entity_id="abs_preheat",
            name="ABS Part 2 Chapter 1 Section 5 - Preheat",
            entity_type="regulation_clause",
            properties={"section": "Pt.2 Ch.1 §5"},
            source_doc_id="doc_abs_001",
        )
        await store.insert_entities([target_entity], doc_society="ABS")

        # Insert a similar_to relation between them (cached cross-reference)
        relation = Relation(
            relation_id="xref_dnv_abs_preheat",
            source_entity_id="dnv_preheat",
            target_entity_id="abs_preheat",
            relation_type="similar_to",
            properties={"method": "expert_review"},
            confidence=0.95,
        )
        await store.insert_relations([relation])

        # Execute cross_reference — should find via graph lookup
        result = await cross_reference(
            store=store,
            source_clause="Preheat",
            source_society="DNV",
            target_society="ABS",
        )

        # Verify result
        assert result is not None, "Graph lookup should find the similar_to relation"
        assert isinstance(result, CrossReferenceResult)
        assert result.source_society == "DNV"
        assert result.target_society == "ABS"
        assert result.confidence == 0.95
        assert result.relation_type in ("equivalent", "similar", "related")
        # The result should come from graph lookup (not LLM fallback)
        assert "graph" in result.notes.lower()

    # ------------------------------------------------------------------
    # Test 2: No graph match, LLM fallback returns result, edge is cached
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_llm_fallback(self, store: KuzuStore):
        """
        No similar_to relation exists; mock LLM returns a result, verify caching.

        WHAT:
        - Insert entities in DNV and ABS societies with NO similar_to relation.
        - Mock _llm_cross_reference to return a CrossReferenceResult.
        - Call cross_reference with a mock LLM backend.
        - Verify the LLM fallback result is returned.
        - Verify a new similar_to relation was cached in the graph.

        WHY:
        - The LLM fallback path is essential for new clause pairs that have
          never been cross-referenced before. After the LLM computes the
          equivalence, caching as a graph edge ensures future queries are
          fast (graph lookup) and free (no LLM cost).
        """
        from m4_kg.search.cross_reference import cross_reference

        # Insert source entity in DNV society
        source_entity = Entity(
            entity_id="dnv_steel",
            name="DNV EH36 Steel Plate Requirements",
            entity_type="steel_grade",
            properties={"grade": "EH36"},
            source_doc_id="doc_dnv_001",
        )
        await store.insert_entities([source_entity], doc_society="DNV")

        # Insert target entity in ABS society (name must match LLM result)
        target_entity = Entity(
            entity_id="abs_steel",
            name="ABS Grade AH36 High Strength Steel",
            entity_type="steel_grade",
            properties={"grade": "AH36"},
            source_doc_id="doc_abs_001",
        )
        await store.insert_entities([target_entity], doc_society="ABS")

        # Verify no similar_to relation exists yet
        relations_before = await store.query_relations(
            ["dnv_steel"], relation_types=["similar_to"]
        )
        assert len(relations_before) == 0, "No similar_to relation should exist yet"

        # Mock LLM backend result
        mock_llm_result = CrossReferenceResult(
            source_society="DNV",
            source_clause="EH36 Steel Plate",
            target_society="ABS",
            target_clause="AH36 High Strength Steel",
            relation_type="equivalent",
            confidence=0.88,
            notes="LLM-based cross reference: both are high-strength structural steels",
        )

        # Call cross_reference with a mock LLM backend
        # The llm_backend is passed through to _llm_cross_reference
        async def mock_llm_fn(source_clause, source_society, target_society, llm_backend):
            return mock_llm_result

        with patch(
            "m4_kg.search.cross_reference._llm_cross_reference",
            side_effect=mock_llm_fn,
        ):
            result = await cross_reference(
                store=store,
                source_clause="EH36",
                source_society="DNV",
                target_society="ABS",
                llm_backend={"provider": "mock", "model": "mock-model"},
            )

        # Verify LLM fallback result
        assert result is not None, "LLM fallback should return a result"
        assert result.source_society == "DNV"
        assert result.target_society == "ABS"
        assert result.confidence == 0.88
        assert result.relation_type == "equivalent"

        # Verify caching: a similar_to relation was created
        relations_after = await store.query_relations(
            ["dnv_steel"], relation_types=["similar_to"]
        )
        assert len(relations_after) == 1, (
            f"LLM result should be cached as a similar_to edge, "
            f"got {len(relations_after)} relations"
        )
        assert relations_after[0].relation_type == "similar_to"
        assert relations_after[0].target_entity_id == "abs_steel"

    # ------------------------------------------------------------------
    # Test 3: No graph match, no LLM backend — returns None
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_no_match_at_all(self, store: KuzuStore):
        """
        No similar_to relation and no LLM backend provided, returns None.

        WHAT:
        - Insert entities in DNV and ABS societies with NO similar_to relation.
        - Call cross_reference WITHOUT providing an LLM backend.
        - Verify the function returns None gracefully.

        WHY:
        - When neither graph lookup nor LLM fallback is available, the
          function must return None rather than raising an error. This
          allows callers to handle the "not found" case declaratively
          without try/except blocks.
        """
        from m4_kg.search.cross_reference import cross_reference

        # Insert entities in both societies but NO similar_to relation
        entities = [
            Entity(
                entity_id="dnv_clause",
                name="DNV Hull Construction Rule",
                entity_type="regulation_clause",
                properties={},
                source_doc_id="doc_dnv_001",
            ),
            Entity(
                entity_id="abs_clause",
                name="ABS Hull Construction Rule",
                entity_type="regulation_clause",
                properties={},
                source_doc_id="doc_abs_001",
            ),
        ]
        await store.insert_entities(entities[:1], doc_society="DNV")
        await store.insert_entities(entities[1:], doc_society="ABS")

        # Call cross_reference WITHOUT LLM backend
        result = await cross_reference(
            store=store,
            source_clause="Hull Construction",
            source_society="DNV",
            target_society="ABS",
            llm_backend=None,  # No LLM fallback available
        )

        # Should return None gracefully
        assert result is None, (
            "Without graph match or LLM backend, cross_reference should return None"
        )
