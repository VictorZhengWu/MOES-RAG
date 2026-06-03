"""
Tests for the entity/relation merger with disambiguation (Task 00080-04).

WHAT:
  Tests for merge_entities(), merge_relations(), disambiguate_entity(),
  and disambiguate_name() functions in m4_kg.extraction.merger.

WHY:
  The merger is the bridge between rule-based and LLM extraction results.
  It must correctly deduplicate, prioritize LLM results, and disambiguate
  document-scoped entities to prevent naming collisions across classification
  societies.
"""

from contracts.knowledge_graph import Entity, Relation


# ---------------------------------------------------------------------------
# Helper factories
# WHY: Reducing boilerplate in tests makes the test intent clearer and
#      reduces copy-paste errors when creating test entities/relations.
# ---------------------------------------------------------------------------

def _make_entity(
    name: str,
    entity_type: str,
    entity_id: str | None = None,
    **kwargs: object,
) -> Entity:
    """Create an Entity with a deterministic ID derived from name+type.

    Additional kwargs (e.g. properties, source_doc_id) are forwarded to the
    Entity constructor.
    """
    return Entity(
        entity_id=entity_id or f"{name}:{entity_type}",
        name=name,
        entity_type=entity_type,
        **kwargs,  # type: ignore[arg-type]
    )


def _make_relation(
    source_id: str,
    target_id: str,
    relation_type: str = "references",
    confidence: float = 1.0,
    relation_id: str | None = None,
) -> Relation:
    """Create a Relation with a deterministic ID."""
    return Relation(
        relation_id=relation_id or f"{source_id}:{target_id}:{relation_type}",
        source_entity_id=source_id,
        target_entity_id=target_id,
        relation_type=relation_type,
        confidence=confidence,
    )


# ===================================================================
# Test 1: merge_entities — same entity deduplication, LLM preferred
# ===================================================================


def test_merge_same_entity():
    """
    When rule and LLM extractors both produce the same entity (same name + type),
    deduplicate to exactly one entity and prefer the LLM version.

    WHY: Rule extraction is a best-effort baseline. LLM extraction has higher
         confidence because it understands context (e.g. distinguishing between
         a steel grade and a coating name). The LLM result should overwrite
         the rule result for the same entity key.
    """
    from m4_kg.extraction.merger import merge_entities

    rule_entities = [
        _make_entity("EH36", "steel_grade", entity_id="rule:EH36"),
    ]
    llm_entities = [
        _make_entity("EH36", "steel_grade", entity_id="llm:EH36",
                     properties={"confidence": "high"}),
    ]

    result = merge_entities(rule_entities, llm_entities)

    assert len(result) == 1, f"Expected 1 entity after dedup, got {len(result)}"
    merged = result[0]
    assert merged.name == "EH36"
    assert merged.entity_type == "steel_grade"
    # LLM version should win (its entity_id should be present)
    assert merged.entity_id == "llm:EH36", "LLM entity_id should overwrite rule entity_id"


# ===================================================================
# Test 2: merge_entities — different types, same name kept separate
# ===================================================================


def test_merge_different_types_same_name():
    """
    When two entities have the same name but different types, both are kept.

    Example: "EH36" can be a steel_grade AND a piece of equipment (e.g. a
    coating or a plate specification). The dedup key is (name, type), so
    different types never collide.

    WHY: In marine engineering, the same alphanumeric identifier can refer
         to fundamentally different things depending on context. Merging
         them would lose critical semantic distinction.
    """
    from m4_kg.extraction.merger import merge_entities

    rule_entities = [
        _make_entity("EH36", "steel_grade"),
        _make_entity("EH36", "equipment"),
    ]
    llm_entities: list[Entity] = []

    result = merge_entities(rule_entities, llm_entities)

    assert len(result) == 2, f"Expected 2 entities (different types), got {len(result)}"
    types = sorted(e.entity_type for e in result)
    assert types == ["equipment", "steel_grade"]


# ===================================================================
# Test 3: merge_relations — same (source, target, rel_type) dedup, LLM wins
# ===================================================================


def test_merge_relation_dedup():
    """
    When rule and LLM both produce the same relation (same source, target,
    relation_type), deduplicate and prefer the LLM version.

    WHY: LLM-extracted relations have richer properties (e.g. extracted
         confidence scores, supporting text spans) that should not be
         overwritten by simpler rule-based relations.
    """
    from m4_kg.extraction.merger import merge_relations

    rule_relations = [
        _make_relation("e1", "e2", "references", confidence=1.0,
                       relation_id="rule:ref"),
    ]
    llm_relations = [
        _make_relation("e1", "e2", "references", confidence=0.95,
                       relation_id="llm:ref"),
    ]

    result = merge_relations(rule_relations, llm_relations)

    assert len(result) == 1, f"Expected 1 relation after dedup, got {len(result)}"
    merged = result[0]
    assert merged.relation_id == "llm:ref", "LLM relation_id should overwrite rule"
    assert merged.confidence == 0.95, "LLM confidence should overwrite rule confidence"


# ===================================================================
# Test 4: disambiguate_entity — regulation_clause gets society prefix
# ===================================================================


def test_disambiguate_regulation_clause():
    """
    A regulation_clause entity from a known classification society document
    should be prefixed with the society name to prevent cross-society collisions.

    Example: "§5.2" in a DNV document becomes "DNV-§5.2".
    The original name is preserved in properties["original_name"].

    WHY: The same clause number (e.g. "§5.2") appears in DNV, ABS, LR, etc.
         with entirely different meanings. Without disambiguation, querying
         "§5.2" would return conflicting results from multiple societies.
    """
    from m4_kg.extraction.merger import disambiguate_entity

    entity = _make_entity("§5.2", "regulation_clause", entity_id="clause:5.2")
    result = disambiguate_entity(entity, "DNV")

    assert result.name == "DNV-§5.2", f"Expected 'DNV-§5.2', got '{result.name}'"
    assert result.entity_id == "clause:5.2", "entity_id should be unchanged"
    assert result.entity_type == "regulation_clause"
    assert result.properties.get("original_name") == "§5.2", (
        "original_name should be preserved in properties"
    )


# ===================================================================
# Test 5: disambiguate_entity — steel_grade stays unchanged (global)
# ===================================================================


def test_disambiguate_steel_grade_unchanged():
    """
    Steel grades, ship_types, parameters, and system_types are global entities
    that should NOT receive a classification society prefix.

    Example: "EH36" is the same steel grade regardless of which society's
    document mentions it. Adding "DNV-EH36" would fragment the knowledge graph.

    WHY: Global entity types represent universal concepts. A steel grade like
         EH36 has the same chemical and mechanical properties regardless of
         which classification society specifies it. Global entities enable
         cross-society knowledge integration.
    """
    from m4_kg.extraction.merger import disambiguate_entity

    entity = _make_entity("EH36", "steel_grade", entity_id="steel:EH36")
    result = disambiguate_entity(entity, "DNV")

    assert result.name == "EH36", f"Steel grade should not be prefixed, got '{result.name}'"
    assert result.entity_type == "steel_grade"


# ===================================================================
# Test 6: merge_entities — LLM overwrites rule for same key
# ===================================================================


def test_merge_llm_overwrites_rules():
    """
    When both rule and LLM extractors produce entities with the same
    (name, type) key, the LLM version completely replaces the rule version.

    This test explicitly verifies the priority override behavior: rules are
    loaded first, then LLM results overwrite any matching key entries.

    WHY: LLM extraction is more precise and context-aware. It can distinguish
         between genuine entities and coincidental pattern matches. The LLM
         result carries higher confidence and richer properties.
    """
    from m4_kg.extraction.merger import merge_entities

    rule_entities = [
        _make_entity("EH36", "steel_grade", entity_id="rule:1", properties={"source": "rule"}),
        _make_entity("DH36", "steel_grade", entity_id="rule:2", properties={"source": "rule"}),
    ]
    llm_entities = [
        _make_entity("EH36", "steel_grade", entity_id="llm:1",
                     properties={"source": "llm", "confidence": 0.98}),
    ]

    result = merge_entities(rule_entities, llm_entities)

    assert len(result) == 2, f"Expected 2 entities (EH36 merged + DH36 rule-only), got {len(result)}"

    # EH36 should be the LLM version
    eh36 = [e for e in result if e.name == "EH36"][0]
    assert eh36.entity_id == "llm:1", "EH36 should be LLM version"
    assert eh36.properties.get("source") == "llm", "EH36 properties should be from LLM"
    assert eh36.properties.get("confidence") == 0.98

    # DH36 should be the rule version (not in LLM results)
    dh36 = [e for e in result if e.name == "DH36"][0]
    assert dh36.entity_id == "rule:2", "DH36 should remain as rule version"
    assert dh36.properties.get("source") == "rule"


# ===================================================================
# Test 7: empty inputs return empty lists
# ===================================================================


def test_empty_inputs():
    """
    Mergers should handle empty input lists gracefully, returning empty lists
    without errors.

    WHY: In production, extraction may produce no results for certain document
         sections or content types. The merger must not crash on empty inputs
         — it should be a safe no-op that downstream code can always call
         regardless of extraction output.
    """
    from m4_kg.extraction.merger import merge_entities, merge_relations

    # Empty entities
    result_e = merge_entities([], [])
    assert result_e == [], f"Expected empty list, got {result_e}"
    assert isinstance(result_e, list)

    # Empty relations
    result_r = merge_relations([], [])
    assert result_r == [], f"Expected empty list, got {result_r}"
    assert isinstance(result_r, list)

    # Empty LLM (only rules)
    rule_entities = [_make_entity("EH36", "steel_grade")]
    result_rule_only = merge_entities(rule_entities, [])
    assert len(result_rule_only) == 1

    # Empty rules (only LLM)
    llm_entities = [_make_entity("EH36", "steel_grade")]
    result_llm_only = merge_entities([], llm_entities)
    assert len(result_llm_only) == 1
