"""
Tests for graph_search (graph_search.py).

WHAT: 2 test cases covering:
  1. Successful entity lookup by topic and BFS expansion.
  2. No-match case returning an empty Subgraph with query_context set.

WHY: graph_search is the primary M4 query interface that powers both user-facing
     graph exploration and the M5 QA pipeline's graph context retrieval. It must
     correctly locate seed entities and return connected subgraphs.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from contracts.knowledge_graph import Entity, Relation, Subgraph
from m4_kg.graph.kuzu_store import KuzuStore
from m4_kg.search.graph_search import graph_search


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
    tmpdir = Path(tempfile.mkdtemp(prefix="kuzu_search_test_"))
    db = KuzuStore(db_path=str(tmpdir / "test.db"))
    yield db
    db._conn = None
    db._db = None
    shutil.rmtree(str(tmpdir), ignore_errors=True)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestGraphSearch:
    """Test suite for graph_search function."""

    # ------------------------------------------------------------------
    # Test 1: Search finds matching entities and returns a Subgraph
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_graph_search_finds_entities(self, store: KuzuStore):
        """
        Insert entities with a matching name, search returns non-empty Subgraph.

        WHAT:
        - Insert 3 entities: one matching "welding", two unrelated.
        - Insert relations from "welding" entity to the other two.
        - Call graph_search(topic="welding", depth=1).
        - Verify Subgraph contains the welding entity and its neighbors.

        WHY:
        - This is the primary user flow: enter a topic, get back a connected
          subgraph of related entities. Verify that graph_search correctly:
          (a) locates seed entities by name, (b) expands via BFS, (c) sets
          query_context on the result.
        """
        # Build graph: welding_ent -> steel_ent, equip_ent
        entities = [
            Entity(
                entity_id="welding_ent",
                name="Welding Preheat Requirements",
                entity_type="regulation_clause",
                properties={"section": "Pt.2 Ch.3"},
                source_doc_id="doc_001",
            ),
            Entity(
                entity_id="steel_ent",
                name="EH36 Steel Plate",
                entity_type="steel_grade",
                properties={"yield_strength": "355MPa"},
                source_doc_id="doc_001",
            ),
            Entity(
                entity_id="equip_ent",
                name="Welding Torch Type-A",
                entity_type="equipment",
                properties={"model": "Type-A"},
                source_doc_id="doc_001",
            ),
        ]
        await store.insert_entities(entities)

        relations = [
            Relation(
                relation_id="rel_weld_steel",
                source_entity_id="welding_ent",
                target_entity_id="steel_ent",
                relation_type="requires",
                properties={"condition": "t <= 50mm"},
                confidence=0.95,
            ),
            Relation(
                relation_id="rel_weld_equip",
                source_entity_id="welding_ent",
                target_entity_id="equip_ent",
                relation_type="applies_to",
                properties={},
                confidence=0.90,
            ),
        ]
        await store.insert_relations(relations)

        # Execute graph search — topic must match case because Kuzu's
        # CONTAINS operator is case-sensitive. Entity names in this test
        # use "Welding" (capital W), so the topic must match that case.
        result: Subgraph = await graph_search(
            store=store,
            topic="Welding",
            depth=1,
            max_entities=20,
        )

        # Verify result type
        assert isinstance(result, Subgraph)

        # Verify at least the welding entity is found
        assert len(result.entities) >= 1
        entity_ids = {e.entity_id for e in result.entities}
        assert "welding_ent" in entity_ids

        # Verify relations to neighbors are included
        assert len(result.relations) >= 1
        rel_ids = {r.relation_id for r in result.relations}
        assert "rel_weld_steel" in rel_ids

        # Verify query_context is set
        assert "topic=Welding" in result.query_context

    # ------------------------------------------------------------------
    # Test 2: Search with no matching topic returns empty Subgraph
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_graph_search_no_match(self, store: KuzuStore):
        """
        Search for a nonexistent topic returns an empty Subgraph with context.

        WHAT:
        - Insert some entities into the graph.
        - Call graph_search with a topic string that matches none of them.
        - Verify the returned Subgraph has zero entities and zero relations,
          and query_context describes the no-match situation.

        WHY:
        - Callers (M5 QA pipeline in particular) must gracefully handle the
          case where no entities match the search, rather than crashing or
          returning an uninitialized object.
        - query_context must relay the reason for emptiness so the UI or QA
          engine can inform the user.
        """
        # Insert some data so the graph is non-empty
        entities = [
            Entity(
                entity_id="test_ent",
                name="Some Regulation",
                entity_type="regulation_clause",
                properties={},
                source_doc_id="doc_001",
            ),
        ]
        await store.insert_entities(entities)

        # Search for a topic that definitely does not exist
        result: Subgraph = await graph_search(
            store=store,
            topic="NonexistentTopic_12345",
        )

        # Verify empty result
        assert isinstance(result, Subgraph)
        assert len(result.entities) == 0, (
            f"Expected 0 entities, got {len(result.entities)}"
        )
        assert len(result.relations) == 0, (
            f"Expected 0 relations, got {len(result.relations)}"
        )
        # query_context should indicate no match found
        assert isinstance(result.query_context, str)
        assert len(result.query_context) > 0
        assert "NonexistentTopic_12345" in result.query_context or "No entities" in result.query_context
