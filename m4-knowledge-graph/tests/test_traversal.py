"""
Tests for BFS graph traversal (traversal.py).

WHAT: 3 test cases covering single-hop traversal, multi-hop depth limiting,
      and empty seed handling.
WHY: bfs_traverse is the core graph exploration primitive that powers
     graph_search() and user-tier-limited queries. Each test uses a fresh
     temporary Kuzu database to ensure complete isolation and repeatability.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from contracts.knowledge_graph import Entity, Relation, Subgraph
from m4_kg.graph.kuzu_store import KuzuStore
from m4_kg.graph.traversal import bfs_traverse


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
    - Automatic cleanup avoids leaving orphaned database files on disk.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="kuzu_traversal_test_"))
    db = KuzuStore(db_path=str(tmpdir / "test.db"))
    yield db
    # Release Kuzu resources before removing the temp directory.
    db._conn = None
    db._db = None
    shutil.rmtree(str(tmpdir), ignore_errors=True)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestBFSTraversal:
    """Test suite for BFS graph traversal (bfs_traverse)."""

    # ------------------------------------------------------------------
    # Helper: build a small test graph and run traversal
    # ------------------------------------------------------------------

    async def _setup_chain_graph(self, store: KuzuStore) -> None:
        """
        Build a 3-node chain graph: A --requires--> B --references--> C.

        WHAT:
        - Creates 3 entities (A, B, C) with ids "ent_a", "ent_b", "ent_c".
        - Creates 2 relations: A->B ("requires"), B->C ("references").
        - Inserts all into the KuzuStore.

        WHY:
        - A linear chain is the simplest multi-hop graph structure,
          making depth-limit verification straightforward.
        """
        entities = [
            Entity(
                entity_id="ent_a",
                name="Entity A",
                entity_type="regulation_clause",
                properties={"section": "Pt.1"},
                source_doc_id="doc_001",
            ),
            Entity(
                entity_id="ent_b",
                name="Entity B",
                entity_type="steel_grade",
                properties={"grade": "EH36"},
                source_doc_id="doc_001",
            ),
            Entity(
                entity_id="ent_c",
                name="Entity C",
                entity_type="regulation_clause",
                properties={"section": "Pt.2"},
                source_doc_id="doc_001",
            ),
        ]
        await store.insert_entities(entities)

        relations = [
            Relation(
                relation_id="rel_a_b",
                source_entity_id="ent_a",
                target_entity_id="ent_b",
                relation_type="requires",
                properties={},
                confidence=0.95,
            ),
            Relation(
                relation_id="rel_b_c",
                source_entity_id="ent_b",
                target_entity_id="ent_c",
                relation_type="references",
                properties={},
                confidence=0.90,
            ),
        ]
        await store.insert_relations(relations)

    # ------------------------------------------------------------------
    # Test 1: Single-hop traversal from one seed entity
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_single_hop(self, store: KuzuStore):
        """
        Seed entity with 2 outgoing relations returns 2 neighbors at depth=1.

        WHAT:
        - Insert 3 entities (A, B, C) with A->B and A->C relations.
        - Run bfs_traverse from "ent_a" with depth=1.
        - Verify 3 entities returned (A + 2 neighbors) and 2 relations.

        WHY:
        - Single-hop traversal is the most common graph search pattern
          (e.g., "find everything directly related to EH36").
        - This test verifies the basic BFS mechanism: seed fetch,
          relation expansion, and target entity collection.
        """
        # Build graph: A -> B, A -> C (fan-out from A)
        entities = [
            Entity(
                entity_id="ent_a",
                name="Entity A",
                entity_type="regulation_clause",
                properties={},
                source_doc_id="doc_001",
            ),
            Entity(
                entity_id="ent_b",
                name="Entity B",
                entity_type="steel_grade",
                properties={},
                source_doc_id="doc_001",
            ),
            Entity(
                entity_id="ent_c",
                name="Entity C",
                entity_type="equipment",
                properties={},
                source_doc_id="doc_001",
            ),
        ]
        await store.insert_entities(entities)

        relations = [
            Relation(
                relation_id="rel_a_b",
                source_entity_id="ent_a",
                target_entity_id="ent_b",
                relation_type="requires",
                properties={},
                confidence=0.95,
            ),
            Relation(
                relation_id="rel_a_c",
                source_entity_id="ent_a",
                target_entity_id="ent_c",
                relation_type="references",
                properties={},
                confidence=0.90,
            ),
        ]
        await store.insert_relations(relations)

        # Execute traversal
        result: Subgraph = await bfs_traverse(
            store=store,
            seed_entity_ids=["ent_a"],
            depth=1,
        )

        # Verify entity count: seed (ent_a) + 2 neighbors (ent_b, ent_c) = 3
        assert len(result.entities) == 3
        entity_ids = {e.entity_id for e in result.entities}
        assert entity_ids == {"ent_a", "ent_b", "ent_c"}

        # Verify relation count: 2 edges
        assert len(result.relations) == 2
        rel_ids = {r.relation_id for r in result.relations}
        assert rel_ids == {"rel_a_b", "rel_a_c"}

        # Verify Subgraph has query_context field
        assert isinstance(result.query_context, str)

    # ------------------------------------------------------------------
    # Test 2: Multi-hop traversal with depth limits
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_multi_hop_with_depth_limit(self, store: KuzuStore):
        """
        Depth=1 returns only direct neighbors; depth=2 reaches two hops away.

        WHAT:
        - Build a chain A->B->C via the helper method.
        - Run bfs_traverse with depth=1: verify only A and B (no C).
        - Run bfs_traverse with depth=2: verify A, B, and C.

        WHY:
        - Depth limiting is the primary mechanism for user-tier control
          (Basic=1, Pro=3, Enterprise=5).
        - This test proves that depth parameter actually constrains
          traversal and does not leak into deeper hops.
        """
        await self._setup_chain_graph(store)

        # --- Depth 1: only direct neighbors ---
        result_d1: Subgraph = await bfs_traverse(
            store=store,
            seed_entity_ids=["ent_a"],
            depth=1,
        )

        entity_ids_d1 = {e.entity_id for e in result_d1.entities}
        # Should contain seed (ent_a) and 1-hop neighbor (ent_b), but NOT ent_c
        assert entity_ids_d1 == {"ent_a", "ent_b"}, (
            f"Depth=1 should return A and B only, got {entity_ids_d1}"
        )
        assert len(result_d1.relations) == 1
        assert result_d1.relations[0].relation_id == "rel_a_b"

        # --- Depth 2: two hops reachable ---
        result_d2: Subgraph = await bfs_traverse(
            store=store,
            seed_entity_ids=["ent_a"],
            depth=2,
        )

        entity_ids_d2 = {e.entity_id for e in result_d2.entities}
        assert entity_ids_d2 == {"ent_a", "ent_b", "ent_c"}, (
            f"Depth=2 should return A, B, and C, got {entity_ids_d2}"
        )
        assert len(result_d2.relations) == 2
        rel_ids_d2 = {r.relation_id for r in result_d2.relations}
        assert rel_ids_d2 == {"rel_a_b", "rel_b_c"}

    # ------------------------------------------------------------------
    # Test 3: Empty seed list returns empty Subgraph
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_empty_seeds(self, store: KuzuStore):
        """
        An empty seed_entity_ids list returns an empty Subgraph.

        WHAT:
        - Insert some entities and relations into the graph.
        - Call bfs_traverse with an empty seed_entity_ids list.
        - Verify the returned Subgraph has zero entities and zero relations.

        WHY:
        - Callers may pass an empty list when a name search yields no
          results. The traversal must handle this gracefully rather
          than raising an error or returning uninitialized data.
        """
        # Insert some data so the graph is non-empty
        entities = [
            Entity(
                entity_id="ent_x",
                name="Entity X",
                entity_type="regulation_clause",
                properties={},
                source_doc_id="doc_001",
            ),
        ]
        await store.insert_entities(entities)

        # Traverse with empty seeds
        result: Subgraph = await bfs_traverse(
            store=store,
            seed_entity_ids=[],
            depth=1,
        )

        # Verify empty result
        assert isinstance(result, Subgraph)
        assert len(result.entities) == 0, (
            f"Empty seeds should return 0 entities, got {len(result.entities)}"
        )
        assert len(result.relations) == 0, (
            f"Empty seeds should return 0 relations, got {len(result.relations)}"
        )
        assert isinstance(result.query_context, str)
