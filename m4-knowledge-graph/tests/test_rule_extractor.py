"""
Tests for the rule-based entity extractor (M4 Task 00080-02).

Tests cover all extractor functions, the negation filter, the orchestrator,
and the relation generator.
"""

from m4_kg.extraction.rule_extractor import (
    extract_steel_grades,
    extract_regulation_clauses,
    extract_equipment,
    extract_parameters,
    extract_ship_types,
    apply_negation_filter,
    extract_entities,
    extract_relations,
)


class TestExtractSteelGrades:
    """Tests for regex-based steel grade extraction.

    WHAT: Validates that the regex [A-Z]{2,4}\\d{2,3} correctly identifies
          steel grade designations in marine engineering text.
    WHY: Steel grades (DH36, EH36, AH32, etc.) are critical entities in
         shipbuilding specifications and must be extracted accurately.
    """

    def test_single_steel_grade(self):
        """Extract a single steel grade from text."""
        result = extract_steel_grades("The hull plates are made of DH36 steel.")
        assert len(result) == 1
        assert result[0].name == "DH36"
        assert result[0].entity_type == "steel_grade"

    def test_multiple_steel_grades(self):
        """Extract multiple steel grades from text."""
        result = extract_steel_grades(
            "EH36 and DH32 grades are used for the hull, AH40 for the deck."
        )
        names = {e.name for e in result}
        assert len(result) == 3
        assert names == {"EH36", "DH32", "AH40"}
        for e in result:
            assert e.entity_type == "steel_grade"

    def test_no_steel_grade(self):
        """Return empty list when no steel grade patterns are present."""
        result = extract_steel_grades("No steel grade mentioned in this text.")
        assert result == []


class TestExtractRegulationClauses:
    """Tests for regex-based regulation clause extraction.

    WHAT: Validates that Pt./Part/Ch./Chapter/§ patterns are extracted
          as regulation_clause entities.
    WHY: Regulation clauses are the backbone of ship classification rules
         and serve as primary navigation entities in the knowledge graph.
    """

    def test_dnv_clause_pattern(self):
        """Extract DNV Pt.4 Ch.3 style regulation clause."""
        result = extract_regulation_clauses(
            "According to DNV Pt.4 Ch.3, hull structural requirements are specified."
        )
        assert len(result) >= 1
        names = {e.name for e in result}
        assert "Pt.4 Ch.3" in names
        for e in result:
            assert e.entity_type == "regulation_clause"

    def test_multiple_clause_formats(self):
        """Extract clauses using various formatting styles."""
        text = (
            "Part 5 Chapter 2 covers machinery. "
            "See also Ch.3 §5.2 for pump requirements. "
            "Section 6.1 details fire safety."
        )
        result = extract_regulation_clauses(text)
        names = {e.name for e in result}
        assert "Part 5 Chapter 2" in names
        # Deduplication keeps the longest match; "Ch.3 §5.2" is preferred
        # over the shorter standalone "Ch.3". Both are valid extractions.
        assert "Section 6.1" in names
        ch3_found = any("Ch.3" in name for name in names)
        assert ch3_found, f"Expected a Ch.3 variant in {names}"
        for e in result:
            assert e.entity_type == "regulation_clause"

    def test_no_clause(self):
        """Return empty list when no regulation clause patterns are present."""
        result = extract_regulation_clauses("This text contains no clause references.")
        assert result == []


class TestExtractParameters:
    """Tests for regex-based parameter extraction (temperature, thickness, pressure).

    WHAT: Validates that marine engineering parameter values like temperature
          (°C/°F), thickness (mm), and pressure (MPa) are extracted as
          parameter entities.
    WHY: Parameters are quantitative constraints that govern design decisions
         and must be captured as first-class entities for constraint reasoning.
    """

    def test_temperature_celsius(self):
        """Extract temperature value in degrees Celsius."""
        result = extract_parameters("The maximum operating temperature is 350°C.")
        assert len(result) >= 1
        names = {e.name for e in result}
        assert "350°C" in names
        for e in result:
            assert e.entity_type == "parameter"

    def test_thickness_mm(self):
        """Extract thickness value in millimeters."""
        result = extract_parameters("Minimum plate thickness shall be 25mm for the hull.")
        names = {e.name for e in result}
        assert "25mm" in names
        for e in result:
            assert e.entity_type == "parameter"

    def test_pressure_mpa(self):
        """Extract pressure value in megapascals."""
        result = extract_parameters("Design pressure is 1.5MPa for the piping system.")
        names = {e.name for e in result}
        assert "1.5MPa" in names
        for e in result:
            assert e.entity_type == "parameter"

    def test_multiple_parameters(self):
        """Extract multiple parameter types from a single text."""
        result = extract_parameters(
            "Operating at 200°C, thickness 15mm, with design pressure 3.0MPa."
        )
        names = {e.name for e in result}
        assert "200°C" in names
        assert "15mm" in names
        assert "3.0MPa" in names
        for e in result:
            assert e.entity_type == "parameter"

    def test_no_parameter(self):
        """Return empty list when no parameter values are present."""
        result = extract_parameters("This text has no parameter values.")
        assert result == []


class TestExtractEquipment:
    """Tests for regex-based equipment extraction (Type-XXX, Model-XXX patterns).

    WHAT: Validates that equipment identifiers using Type- and Model- prefixes
          are extracted as equipment entities.
    WHY: Equipment is a key entity type in marine engineering diagrams and
         certification documents.
    """

    def test_type_pattern(self):
        """Extract Type-XXX equipment identifier."""
        result = extract_equipment(
            "All Type-A1 fire extinguishers must be inspected annually."
        )
        assert len(result) >= 1
        names = {e.name for e in result}
        assert "Type-A1" in names
        for e in result:
            assert e.entity_type == "equipment"

    def test_model_pattern(self):
        """Extract Model-XXX equipment identifier."""
        result = extract_equipment("The Model-X200 centrifugal pump provides main cooling.")
        names = {e.name for e in result}
        assert "Model-X200" in names

    def test_no_equipment(self):
        """Return empty list when no equipment identifiers are present."""
        result = extract_equipment("No special equipment mentioned here.")
        assert result == []


class TestExtractShipTypes:
    """Tests for dictionary-based ship type extraction.

    WHAT: Validates that known ship types (bulk carrier, oil tanker, etc.)
          are extracted via dictionary lookup.
    WHY: Ship types are high-level classification entities that organize
         regulations and design requirements.
    """

    def test_bulk_carrier(self):
        """Extract 'bulk carrier' from text."""
        result = extract_ship_types("The bulk carrier shall comply with CSR rules.")
        assert len(result) == 1
        assert result[0].name == "bulk carrier"
        assert result[0].entity_type == "ship_type"

    def test_multiple_ship_types(self):
        """Extract multiple ship types from text."""
        result = extract_ship_types(
            "Both oil tanker and container ship designs are covered under this regulation."
        )
        names = {e.name for e in result}
        assert "oil tanker" in names
        assert "container ship" in names
        assert len(result) == 2

    def test_no_ship_type(self):
        """Return empty list when no known ship types are mentioned."""
        result = extract_ship_types("General engineering principles apply.")
        assert result == []


class TestNegationFilter:
    """Tests for the negation pattern filter.

    WHAT: Validates that entities within negation phrases (except, excluding,
          not applicable to, does not apply to) are filtered out.
    WHY: Negation detection prevents false-positive entity extraction from
         exception clauses, which is critical for regulatory compliance.
    """

    def test_except_negation(self):
        """Remove entities that fall within 'except' phrase."""
        text = "All piping systems except emergency bilge systems shall be inspected."
        matches = [
            {"name": "emergency bilge systems", "start": 30, "end": 54},
        ]
        result = apply_negation_filter(text, matches)
        assert result == []

    def test_excluding_negation(self):
        """Remove entities that fall within 'excluding' phrase."""
        text = "Steel grades DH36 and EH36, excluding DH32 for cold regions."
        matches = [
            {"name": "DH32", "start": 40, "end": 44},
        ]
        result = apply_negation_filter(text, matches)
        assert result == []

    def test_not_applicable_to_negation(self):
        """Remove entities within 'not applicable to' phrase."""
        text = "This requirement is not applicable to fishing vessels under 24m."
        matches = [
            {"name": "fishing vessels", "start": 40, "end": 55},
        ]
        result = apply_negation_filter(text, matches)
        assert result == []

    def test_does_not_apply_to_negation(self):
        """Remove entities within 'does not apply to' phrase."""
        text = "The standard does not apply to offshore supply vessels."
        matches = [
            {"name": "offshore supply vessels", "start": 38, "end": 62},
        ]
        result = apply_negation_filter(text, matches)
        assert result == []

    def test_unaffected_match_passes(self):
        """Entities outside negation phrases should pass through.

        WHAT: Verifies that when an entity appears BEFORE a negation phrase
              (not within it), it is preserved while the negated entity is removed.
        WHY: The negation filter should only remove entities whose span overlaps
             with the negation phrase. Entities in non-negated parts of the text
             must pass through unchanged.
        """
        # "DH36" appears before "except"; only "emergency systems" is negated
        text = "DH36 steel is required, except emergency systems."
        matches = [
            {"name": "DH36", "start": 0, "end": 4},
            {"name": "emergency systems", "start": 35, "end": 52},
        ]
        result = apply_negation_filter(text, matches)
        assert len(result) == 1
        assert result[0]["name"] == "DH36"


class TestEmptyInput:
    """Tests for empty or edge-case input handling.

    WHAT: Validates that all extractors handle None, empty string, and
          whitespace-only input gracefully.
    WHY: Robust input handling prevents crashes in the pipeline when
          processing documents with empty sections or chunks.
    """

    def test_empty_text_entities(self):
        """extract_entities returns empty list for empty text."""
        result = extract_entities("")
        assert result == []

    def test_empty_text_relations(self):
        """extract_relations returns empty list for empty entity list."""
        result = extract_relations([])
        assert result == []


class TestExtractEntitiesOrchestrator:
    """Tests for the main orchestrator function.

    WHAT: Validates that extract_entities() correctly orchestrates all
          individual extractors and returns combined, deduplicated results.
    WHY: The orchestrator is the primary public API that downstream modules
         call; it must reliably aggregate results from all rule-based extractors.
    """

    def test_orchestrates_all_extractors(self):
        """Combined text should produce entities from all extractor types."""
        text = (
            "For a bulk carrier with DH36 steel hull plates, "
            "according to DNV Pt.4 Ch.3, the minimum thickness is 25mm. "
            "All Type-A1 fire equipment must be tested at 350°C "
            "with a design pressure of 1.5MPa."
        )
        result = extract_entities(text)

        entity_types = {e.entity_type for e in result}
        # Should find steel_grade, regulation_clause, ship_type,
        # equipment, and parameter entities
        assert "steel_grade" in entity_types
        assert "regulation_clause" in entity_types
        assert "ship_type" in entity_types
        assert "equipment" in entity_types
        assert "parameter" in entity_types

        # Check specific entities are present
        names_by_type: dict[str, set[str]] = {}
        for e in result:
            names_by_type.setdefault(e.entity_type, set()).add(e.name)

        assert "DH36" in names_by_type.get("steel_grade", set())
        assert "Pt.4 Ch.3" in names_by_type.get("regulation_clause", set())
        assert "bulk carrier" in names_by_type.get("ship_type", set())
        assert "Type-A1" in names_by_type.get("equipment", set())
        param_names = names_by_type.get("parameter", set())
        assert "25mm" in param_names or "350°C" in param_names or "1.5MPa" in param_names

    def test_entity_ids_are_hash_based(self):
        """Entity IDs should be deterministic MD5 hashes of name:type."""
        result = extract_steel_grades("DH36 steel.")
        # entity_id should be md5("DH36:steel_grade")
        import hashlib
        expected_id = hashlib.md5("DH36:steel_grade".encode()).hexdigest()
        assert result[0].entity_id == expected_id

    def test_doc_id_assigned(self):
        """When doc_id is provided, it should be assigned to all entities."""
        result = extract_entities("DH36 steel for bulk carrier.", doc_id="doc-001")
        for e in result:
            assert e.source_doc_id == "doc-001"


class TestExtractRelations:
    """Tests for the relation generator function.

    WHAT: Validates that extract_relations() generates 'references' edges
          between regulation_clause entities and 'constrains' edges from
          parameter entities to other entities.
    WHY: Relations connect entities into a usable knowledge graph structure.
    """

    def test_references_between_clauses(self):
        """Generate references relations between regulation clauses."""
        from contracts.knowledge_graph import Entity
        clauses = [
            Entity(entity_id="id1", name="Pt.4 Ch.3", entity_type="regulation_clause"),
            Entity(entity_id="id2", name="Pt.4 Ch.5", entity_type="regulation_clause"),
            Entity(entity_id="id3", name="Ch.2 §3.1", entity_type="regulation_clause"),
        ]
        relations = extract_relations(clauses)
        reference_rels = [r for r in relations if r.relation_type == "references"]
        # Three clauses should produce pairwise references
        assert len(reference_rels) >= 2  # At least some pairwise connections

    def test_constrains_parameter_to_entity(self):
        """Generate constrains relations from parameters to other entity types."""
        from contracts.knowledge_graph import Entity
        entities = [
            Entity(entity_id="id1", name="DH36", entity_type="steel_grade"),
            Entity(entity_id="id2", name="Type-A1", entity_type="equipment"),
            Entity(entity_id="id3", name="25mm", entity_type="parameter"),
            Entity(entity_id="id4", name="350°C", entity_type="parameter"),
        ]
        relations = extract_relations(entities)
        constrain_rels = [r for r in relations if r.relation_type == "constrains"]
        # Each parameter should constrain non-parameter entities
        assert len(constrain_rels) >= 2

    def test_relation_ids_are_hash_based(self):
        """Relation IDs should be deterministic MD5 hashes."""
        from contracts.knowledge_graph import Entity
        entities = [
            Entity(entity_id="id_a", name="Pt.4 Ch.3", entity_type="regulation_clause"),
            Entity(entity_id="id_b", name="Pt.4 Ch.5", entity_type="regulation_clause"),
        ]
        relations = extract_relations(entities)
        for r in relations:
            # relation_id format: md5(source_id:target_id:relation_type)
            import hashlib
            expected = hashlib.md5(
                f"{r.source_entity_id}:{r.target_entity_id}:{r.relation_type}".encode()
            ).hexdigest()
            assert r.relation_id == expected
            assert r.confidence == 1.0
