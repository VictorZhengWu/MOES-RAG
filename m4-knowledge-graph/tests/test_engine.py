"""
Tests for KGEngine (engine.py) — the main M4 knowledge graph engine.

WHAT: 4 test cases covering:
  1. test_engine_init — engine initializes with default tier (basic)
  2. test_engine_tier_limits_cross_ref — basic tier prevents cross_reference
  3. test_engine_pro_tier_allows_cross_ref — pro tier allows cross_reference lookup
  4. test_health_check — returns {"status": "ok"} when Kuzu DB has data

WHY: The KGEngine is the entry point for all M4 functionality. It must
     correctly enforce tier-based access control, proxy queries to KuzuStore,
     and report database health. These tests verify the core engine wiring
     without requiring real LLM backends or M1/M2 integration.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from contracts.knowledge_graph import (
    CrossReferenceResult,
    Entity,
    Relation,
)
from m4_kg.graph.kuzu_store import KuzuStore


# ---------------------------------------------------------------------------
# Fixture: temporary Kuzu database path (engine uses this for each test)
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_db_path():
    """
    Create a unique temporary directory for test-isolated Kuzu databases.

    WHAT:
    - Generates a unique temp directory path for each test.
    - Yields the db_path string (directory + database name).
    - Cleans up the directory after the test completes.

    WHY:
    - Each test must start with an empty, isolated graph database to prevent
      cross-test data leakage. Kuzu creates files on first connection, so we
      need clean directories each time.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="kuzu_engine_test_"))
    db_path = str(tmpdir / "test.db")
    yield db_path
    # Close any lingering Kuzu connections by letting them go out of scope.
    # Kuzu uses file-level locking on Windows — the rmtree may fail if
    # connections are not fully released, so we use ignore_errors=True.
    shutil.rmtree(str(tmpdir), ignore_errors=True)


# ===========================================================================
# Test 1: Engine initialization with default tier
# ===========================================================================


@pytest.mark.asyncio
async def test_engine_init(fresh_db_path):
    """
    Verify KGEngine initializes with default tier "basic" and valid config.

    WHAT:
    - Creates a KGEngine with only a db_path (no explicit tier).
    - Checks that _tier is the "basic" UserTier.
    - Checks that _config is an ExtractionConfig with default values.
    - Checks that the KuzuStore is lazily initialized (not connected yet).

    WHY:
    - The default tier must be "basic" for safety — new deployments should
      start with the most restrictive tier. The KuzuStore must be lazily
      initialized to avoid file creation at construction time.
    """
    from m4_kg.core.engine import KGEngine

    engine = KGEngine(db_path=fresh_db_path)

    # Verify default tier is "basic" (most restrictive tier for safety)
    assert engine._tier.level == "basic"
    assert engine._tier.traversal_depth == 1
    assert engine._tier.max_entities == 20
    assert engine._tier.enable_cross_ref is False

    # Verify config exists with default values
    assert engine._config is not None
    assert engine._config.llm is None  # default: no LLM configured
    assert engine._config.fallback_to_rules is True

    # Verify KuzuStore is not yet connected (lazy init)
    assert engine._store._conn is None

    # Clean up — close the engine's store to release file handles
    await engine._store.close()


# ===========================================================================
# Test 2: Basic tier prevents cross_reference (returns None immediately)
# ===========================================================================


@pytest.mark.asyncio
async def test_engine_tier_limits_cross_ref(fresh_db_path):
    """
    Verify that basic tier blocks cross_reference by returning None.

    WHAT:
    - Creates an engine with tier="basic" (enable_cross_ref=False).
    - Calls cross_reference() — it should return None immediately without
      accessing the database, because the tier check short-circuits.

    WHY:
    - Basic tier users must not be able to perform cross-reference queries,
      which require additional LLM costs. The tier check is a zero-cost
      gate that prevents both graph and LLM lookups for basic users.
    """
    from m4_kg.core.engine import KGEngine

    engine = KGEngine(db_path=fresh_db_path, tier="basic")

    # Basic tier disables cross-reference entirely
    result = await engine.cross_reference(
        source_clause="Pt.4 Ch.3",
        source_society="DNV",
        target_society="ABS",
    )

    assert result is None, (
        f"Expected None for basic tier cross_reference, got {result}"
    )

    await engine._store.close()


# ===========================================================================
# Test 3: Pro tier allows cross_reference (performs actual lookup)
# ===========================================================================


@pytest.mark.asyncio
async def test_engine_pro_tier_allows_cross_ref(fresh_db_path):
    """
    Verify that pro tier allows cross_reference to perform a real lookup.

    WHAT:
    - Creates an engine with tier="pro" (enable_cross_ref=True).
    - Inserts entities from two classification societies (DNV and ABS) into
      the KuzuStore.
    - Inserts a similar_to relation between a DNV clause and an ABS clause.
    - Calls cross_reference() and verifies it finds the cached graph match.

    WHY:
    - Pro tier enables cross-reference lookups. The engine must not
      short-circuit with None when enable_cross_ref is True. It must
      delegate to the search.cross_reference function and return real
      results when matches exist in the graph.
    """
    from m4_kg.core.engine import KGEngine

    engine = KGEngine(db_path=fresh_db_path, tier="pro")

    # Insert test entities: a DNV clause and an ABS clause
    source_entity = Entity(
        entity_id="dnv_clause_1",
        name="DNV-Pt.4 Ch.3 preheat",
        entity_type="regulation_clause",
    )
    target_entity = Entity(
        entity_id="abs_clause_1",
        name="ABS-Pt.5B hull fire",
        entity_type="regulation_clause",
    )

    # Insert entities with their classification society tags
    await engine._store.insert_entities([source_entity], doc_society="DNV")
    await engine._store.insert_entities([target_entity], doc_society="ABS")

    # Insert a similar_to relation between them (simulating a cached
    # cross-reference from a previous LLM lookup)
    similar_to_rel = Relation(
        relation_id="rel_similar_1",
        source_entity_id="dnv_clause_1",
        target_entity_id="abs_clause_1",
        relation_type="similar_to",
        confidence=0.95,
    )
    await engine._store.insert_relations([similar_to_rel])

    # Pro tier enables cross_reference — should find the graph match
    result = await engine.cross_reference(
        source_clause="preheat",
        source_society="DNV",
        target_society="ABS",
    )

    assert result is not None, (
        "Expected CrossReferenceResult from pro tier lookup, got None"
    )
    assert isinstance(result, CrossReferenceResult)
    assert result.source_society == "DNV"
    assert result.target_society == "ABS"
    assert result.confidence > 0.8
    assert "preheat" in result.source_clause.lower()

    await engine._store.close()


# ===========================================================================
# Test 4: Health check returns ok when Kuzu DB is connected and has data
# ===========================================================================


@pytest.mark.asyncio
async def test_health_check(fresh_db_path):
    """
    Verify health_check returns {"status": "ok"} when the database is healthy.

    WHAT:
    - Creates an engine and inserts a steel_grade entity (needed because
      health_check queries for entity_type="steel_grade").
    - Calls health_check() and verifies it returns status "ok".

    WHY:
    - Health check is the primary monitoring endpoint for M4. It must
      verify actual database connectivity (not just return a hardcoded
      status). Inserting a steel_grade entity ensures the query returns
      results, confirming the database is functional.
    """
    from m4_kg.core.engine import KGEngine

    engine = KGEngine(db_path=fresh_db_path, tier="basic")

    # Insert a steel_grade entity — health_check queries by this type
    steel_entity = Entity(
        entity_id="steel_eh36",
        name="EH36",
        entity_type="steel_grade",
    )
    await engine._store.insert_entities([steel_entity])

    # Verify health check returns ok status
    result = await engine.health_check()

    assert result["status"] == "ok", (
        f"Expected status 'ok', got {result.get('status')}"
    )
    assert "graph_entities" in result
    assert result["graph_entities"] == "connected"

    await engine._store.close()
