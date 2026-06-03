"""
Tests for Kuzu graph store (kuzu_store.py + schema.py).

WHAT: 5 test cases covering entity insertion/query, relation insertion/query,
      type filtering, society filtering, and cascade delete by document ID.
WHY: KuzuStore is the persistence foundation for M4's knowledge graph engine.
     All graph operations (extraction, traversal, search, cross-reference)
     depend on correct and reliable store behavior. Each test uses a fresh
     temporary database to ensure complete isolation and repeatability.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from contracts.knowledge_graph import Entity, Relation
from m4_kg.graph.kuzu_store import KuzuStore


# ---------------------------------------------------------------------------
# Fixture: create a fresh KuzuStore backed by a temporary directory
# ---------------------------------------------------------------------------

@pytest.fixture
def store():
    """
    Create a KuzuStore with a fresh temporary database for test isolation.

    WHAT:
    - Creates a temp directory unique to each test
    - Instantiates KuzuStore pointing at a test.db inside that directory
    - Yields the store for the test to use
    - Cleans up the temp directory after the test completes

    WHY:
    - Each test must start with an empty graph to be independent
    - Temp directory isolation prevents cross-test data leakage
    - Automatic cleanup avoids leaving orphaned database files on disk
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="kuzu_test_"))
    db = KuzuStore(db_path=str(tmpdir / "test.db"))
    yield db
    # Release Kuzu resources before removing the temp directory.
    # Kuzu Connection does not always expose an explicit close(); setting
    # references to None lets the garbage collector release file handles.
    db._conn = None
    db._db = None
    shutil.rmtree(str(tmpdir), ignore_errors=True)


# ---------------------------------------------------------------------------
# Helper: create standard test entities
# ---------------------------------------------------------------------------

def _make_entities() -> list[Entity]:
    """
    Build a standard set of 3 test entities for reuse across tests.

    Returns:
        list[Entity] with steel_grade and regulation_clause types.
    """
    return [
        Entity(
            entity_id="eh36",
            name="EH36 Steel Plate",
            entity_type="steel_grade",
            properties={"yield_strength": "355MPa", "standard": "DNV-OS-B101"},
            source_doc_id="doc_dnv_001",
        ),
        Entity(
            entity_id="abs_a",
            name="ABS Grade A Steel",
            entity_type="steel_grade",
            properties={"yield_strength": "235MPa", "standard": "ABS-Rules"},
            source_doc_id="doc_abs_001",
        ),
        Entity(
            entity_id="dnv_preheat",
            name="DNV Welding Preheat Requirement",
            entity_type="regulation_clause",
            properties={
                "temperature": "150C",
                "section": "Pt.2 Ch.3 Sec.2",
            },
            source_doc_id="doc_dnv_001",
        ),
    ]


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestKuzuStore:
    """Test suite for KuzuStore CRUD operations on Entity and Relation tables."""

    # ------------------------------------------------------------------
    # Test 1: Entity insert and query by name (CONTAINS search)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_insert_and_query_entities(self, store: KuzuStore):
        """
        Insert 3 entities and verify name-based CONTAINS search.

        WHAT:
        - Insert 3 entities of different types with different names
        - Query by name substring "EH36" → should return exactly 1 match
        - Query by name substring "Steel" → should return 2 matches
        - Query by non-existent name → should return empty list

        WHY:
        - Name search is the primary entry point for graph_search()
        - CONTAINS semantics allow partial matches for flexible user queries
        """
        entities = _make_entities()
        await store.insert_entities(entities)

        # Query 1: exact substring match
        results = await store.query_entities_by_name("EH36")
        assert len(results) == 1
        assert results[0].entity_id == "eh36"
        assert results[0].name == "EH36 Steel Plate"
        assert results[0].entity_type == "steel_grade"
        assert results[0].properties["yield_strength"] == "355MPa"
        assert results[0].source_doc_id == "doc_dnv_001"

        # Query 2: multiple matches
        results = await store.query_entities_by_name("Steel")
        assert len(results) == 2
        result_ids = {r.entity_id for r in results}
        assert result_ids == {"eh36", "abs_a"}

        # Query 3: no match
        results = await store.query_entities_by_name("NonexistentEntity")
        assert len(results) == 0

    # ------------------------------------------------------------------
    # Test 2: Relation insert and query
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_insert_and_query_relations(self, store: KuzuStore):
        """
        Insert 2 entities and 1 relation, then query the relation.

        WHAT:
        - Insert 2 entities (source and target)
        - Insert 1 relation connecting them (type "requires")
        - Query relations by source entity ID → should return the relation
        - Verify relation properties and confidence are preserved

        WHY:
        - Relations are the edges that make the knowledge graph traversable
        - Round-trip integrity (insert → query) ensures data is not corrupted
        """
        entities = [
            Entity(
                entity_id="e_src",
                name="EH36 Steel Plate",
                entity_type="steel_grade",
                properties={},
                source_doc_id="doc_001",
            ),
            Entity(
                entity_id="e_tgt",
                name="Preheat 150C",
                entity_type="regulation_clause",
                properties={},
                source_doc_id="doc_001",
            ),
        ]
        await store.insert_entities(entities)

        # Insert relation from source to target
        relation = Relation(
            relation_id="rel_001",
            source_entity_id="e_src",
            target_entity_id="e_tgt",
            relation_type="requires",
            properties={"condition": "t <= 50mm"},
            confidence=0.95,
        )
        await store.insert_relations([relation])

        # Query relations involving the source entity
        results = await store.query_relations(["e_src"])
        assert len(results) == 1
        assert results[0].relation_id == "rel_001"
        assert results[0].source_entity_id == "e_src"
        assert results[0].target_entity_id == "e_tgt"
        assert results[0].relation_type == "requires"
        assert results[0].confidence == 0.95
        assert results[0].properties["condition"] == "t <= 50mm"

    # ------------------------------------------------------------------
    # Test 3: Query by entity_type (exact match filtering)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_query_by_type(self, store: KuzuStore):
        """
        Insert mixed-type entities and verify type-based filtering.

        WHAT:
        - Insert entities with types: steel_grade (2), regulation_clause (1)
        - Query by entity_type "steel_grade" → should return exactly 2
        - Query by entity_type "regulation_clause" → should return exactly 1
        - Query by non-existent type → should return empty list

        WHY:
        - Type filtering is essential for narrowing graph_search results
        - The index on entity_type makes these queries fast even at scale
        """
        entities = _make_entities()
        await store.insert_entities(entities)

        # Filter by steel_grade type
        results = await store.query_entities_by_type("steel_grade")
        assert len(results) == 2
        for r in results:
            assert r.entity_type == "steel_grade"

        # Filter by regulation_clause type
        results = await store.query_entities_by_type("regulation_clause")
        assert len(results) == 1
        assert results[0].entity_id == "dnv_preheat"

        # Filter by non-existent type
        results = await store.query_entities_by_type("equipment")
        assert len(results) == 0

    # ------------------------------------------------------------------
    # Test 4: Query by doc_society (classification society filtering)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_query_by_society(self, store: KuzuStore):
        """
        Insert entities with different societies and verify society filtering.

        WHAT:
        - Insert 2 DNV entities and 1 ABS entity (via doc_society parameter)
        - Query by society "DNV" → should return exactly 2 DNV entities
        - Query by society "ABS" → should return exactly 1 ABS entity
        - Query by non-existent society → should return empty list

        WHY:
        - Society filtering enables cross_reference() to isolate entities
          from a specific classification society
        - The index on doc_society makes this O(log N) instead of full scan
        """
        # DNV entities
        dnv_entities = [
            Entity(
                entity_id="dnv_e1",
                name="DNV EH36 Requirement",
                entity_type="steel_grade",
                properties={},
                source_doc_id="doc_dnv_001",
            ),
            Entity(
                entity_id="dnv_e2",
                name="DNV Welding Standard",
                entity_type="regulation_clause",
                properties={},
                source_doc_id="doc_dnv_002",
            ),
        ]
        await store.insert_entities(dnv_entities, doc_society="DNV")

        # ABS entity
        abs_entities = [
            Entity(
                entity_id="abs_e1",
                name="ABS Hull Construction",
                entity_type="regulation_clause",
                properties={},
                source_doc_id="doc_abs_001",
            ),
        ]
        await store.insert_entities(abs_entities, doc_society="ABS")

        # Query DNV entities
        results = await store.query_entities_by_society("DNV")
        assert len(results) == 2
        result_ids = {r.entity_id for r in results}
        assert result_ids == {"dnv_e1", "dnv_e2"}

        # Query ABS entities
        results = await store.query_entities_by_society("ABS")
        assert len(results) == 1
        assert results[0].entity_id == "abs_e1"

        # Query non-existent society
        results = await store.query_entities_by_society("CCS")
        assert len(results) == 0

    # ------------------------------------------------------------------
    # Test 5: Cascade delete by document ID
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_by_doc_id(self, store: KuzuStore):
        """
        Insert entities across two documents, delete one document's data.

        WHAT:
        - Insert 3 entities belonging to doc_dnv_001, 2 to doc_abs_001
        - Insert 1 relation with source_doc_id matching doc_dnv_001
        - Call delete_by_doc_id("doc_dnv_001")
        - Verify all 3 entities from doc_dnv_001 are gone
        - Verify doc_abs_001 entities remain untouched
        - Verify the relation from doc_dnv_001 is also deleted

        WHY:
        - Document-level deletion is the core mechanism for incremental graph
          updates when a document is removed or re-parsed
        - Cascade behavior (entity + relation) prevents orphaned edges
        """
        # Insert entities for two different documents
        dnv_entities = [
            Entity(
                entity_id="del_e1",
                name="DNV Rule A",
                entity_type="regulation_clause",
                properties={},
                source_doc_id="doc_dnv_001",
            ),
            Entity(
                entity_id="del_e2",
                name="DNV Rule B",
                entity_type="regulation_clause",
                properties={},
                source_doc_id="doc_dnv_001",
            ),
            Entity(
                entity_id="del_e3",
                name="DNV Requirement C",
                entity_type="steel_grade",
                properties={},
                source_doc_id="doc_dnv_001",
            ),
        ]
        await store.insert_entities(dnv_entities, doc_society="DNV")

        abs_entities = [
            Entity(
                entity_id="keep_e1",
                name="ABS Hull Rule",
                entity_type="regulation_clause",
                properties={},
                source_doc_id="doc_abs_001",
            ),
            Entity(
                entity_id="keep_e2",
                name="ABS Material Standard",
                entity_type="steel_grade",
                properties={},
                source_doc_id="doc_abs_001",
            ),
        ]
        await store.insert_entities(abs_entities, doc_society="ABS")

        # Insert a relation between two DNV entities
        relation = Relation(
            relation_id="rel_del",
            source_entity_id="del_e1",
            target_entity_id="del_e2",
            relation_type="references",
            properties={},
            confidence=1.0,
        )
        await store.insert_relations([relation])

        # Verify all entities exist before deletion
        all_before = await store.query_entities_by_name("Rule")
        assert len(all_before) == 3  # del_e1, del_e2, keep_e1

        # Delete everything from doc_dnv_001 (expect 3 entities cleared)
        deleted_count = await store.delete_by_doc_id("doc_dnv_001")
        assert deleted_count == 3  # 3 DNV entities should be removed

        # Verify DNV entities are gone
        dnv_results = await store.query_entities_by_name("DNV")
        assert len(dnv_results) == 0

        # Verify ABS entities remain
        abs_results = await store.query_entities_by_name("ABS")
        assert len(abs_results) == 2
        abs_ids = {r.entity_id for r in abs_results}
        assert abs_ids == {"keep_e1", "keep_e2"}

        # Verify relation is also deleted
        rel_results = await store.query_relations(["del_e1"])
        assert len(rel_results) == 0
