"""
Rule-based entity and relation extractor for the M4 Knowledge Graph engine.

WHAT:
  This module provides deterministic regex- and dictionary-based extraction of
  entities (steel grades, regulation clauses, equipment, parameters, ship types)
  and relations (references, constrains) from marine engineering text.

  - Individual extractor functions (e.g. extract_steel_grades) return list[Entity].
  - apply_negation_filter() removes false positives from exception clauses.
  - extract_entities() orchestrates all extractors with negation filtering.
  - extract_relations() generates edges between extracted entities.

WHY:
  Rule-based extraction covers ~70% of marine engineering entities without
  LLM cost. Negation detection prevents false positives from clauses like
  "except emergency systems". The orchestrator provides a single entry point
  that downstream modules (LLM extractor, merger, engine) depend on.

Entity ID format: md5("name:type")
Relation ID format: md5("source_id:target_id:relation_type")
Confidence: 1.0 for all rule-based results (deterministic extraction).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from contracts.knowledge_graph import Entity, Relation

# ---------------------------------------------------------------------------
# Known ship types for dictionary lookup.
# Keys are lowercase search strings; values are canonical display names.
# WHY: Case-insensitive matching against canonical names ensures consistent
#      entity naming regardless of input text capitalization.
# ---------------------------------------------------------------------------
SHIP_TYPES: dict[str, str] = {
    "bulk carrier": "bulk carrier",
    "ore carrier": "ore carrier",
    "oil tanker": "oil tanker",
    "crude oil tanker": "crude oil tanker",
    "product tanker": "product tanker",
    "chemical tanker": "chemical tanker",
    "container ship": "container ship",
    "lng carrier": "LNG carrier",
    "lpg carrier": "LPG carrier",
    "passenger ship": "passenger ship",
    "cruise ship": "cruise ship",
    "ferry": "ferry",
    "ro-ro": "Ro-Ro",
    "ropax": "RoPax",
    "general cargo ship": "general cargo ship",
    "multi-purpose vessel": "multi-purpose vessel",
    "offshore supply vessel": "offshore supply vessel",
    "osv": "OSV",
    "psv": "PSV",
    "ahts": "AHTS",
    "tug boat": "tug boat",
    "tug": "tug",
    "barge": "barge",
    "fishing vessel": "fishing vessel",
    "trawler": "trawler",
    "drillship": "drillship",
    "semi-submersible": "semi-submersible",
    "jack-up rig": "jack-up rig",
    "fpso": "FPSO",
    "fsru": "FSRU",
    "flng": "FLNG",
    "heavy lift vessel": "heavy lift vessel",
    "cable laying ship": "cable laying ship",
    "pipe laying vessel": "pipe laying vessel",
    "dredger": "dredger",
    "icebreaker": "icebreaker",
    "research vessel": "research vessel",
    "patrol vessel": "patrol vessel",
    "naval vessel": "naval vessel",
    "yacht": "yacht",
}

# ---------------------------------------------------------------------------
# Negation patterns for filtering false positives.
# WHAT: Each pattern captures the "target" group — the text after a negation
#       phrase up to the next period. Entities whose span falls within a
#       negation target are excluded.
# WHY: Regulatory texts frequently use exception clauses ("except X",
#      "not applicable to Y"). Without negation filtering, these exceptions
#      would be extracted as false-positive entities.
# ---------------------------------------------------------------------------
NEGATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"except\s+(?P<target>[^.]+)", re.IGNORECASE),
    re.compile(r"excluding\s+(?P<target>[^.]+)", re.IGNORECASE),
    re.compile(r"not applicable to\s+(?P<target>[^.]+)", re.IGNORECASE),
    re.compile(r"does not apply to\s+(?P<target>[^.]+)", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Compiled regex patterns for entity extraction.
# WHY: Pre-compiled patterns avoid re-compilation on every call, improving
#      throughput when processing thousands of document chunks.
# ---------------------------------------------------------------------------
# Steel grades: 2-4 uppercase letters followed by 2-3 digits.
# Matches DH36, EH36, AH32, NV500, ABS450, etc.
_STEEL_GRADE_RE: re.Pattern[str] = re.compile(r"\b[A-Z]{2,4}\d{2,3}\b")

# Regulation clauses: multiple patterns covering common formats.
# Patterns are applied in order from most specific to least specific
# to avoid fragmenting compound references like "Pt.4 Ch.3".
_CLAUSE_PATTERNS: list[re.Pattern[str]] = [
    # "Part 5 Chapter 2", "Pt.4 Ch.3" — compound clause references
    re.compile(r"\b(?:Part|Pt)\.?\s*\d+\s*(?:Chapter|Ch)\.?\s*\d+\b", re.IGNORECASE),
    # "Pt.3 § 5.2", "Part 4 §2.1"
    re.compile(r"\b(?:Part|Pt)\.?\s*\d+\s*§\s*[\d.]+\b", re.IGNORECASE),
    # "Ch.3 §5.2" — chapter with section
    re.compile(r"\b(?:Chapter|Ch)\.?\s*\d+\s*§\s*[\d.]+\b", re.IGNORECASE),
    # "Part 5", "Pt.4" — standalone part
    re.compile(r"\b(?:Part|Pt)\.?\s*\d+\b", re.IGNORECASE),
    # "Chapter 3", "Ch.2" — standalone chapter
    re.compile(r"\b(?:Chapter|Ch)\.?\s*\d+\b", re.IGNORECASE),
    # "§ 5.2", "§5.2" — section/symbol reference
    re.compile(r"§\s*[\d.]+"),
    # "Section 6.1", "Section 3" — standalone section
    re.compile(r"\bSection\s+[\d.]+\b", re.IGNORECASE),
]

# Equipment: Type- or Model- prefix followed by identifier.
# Matches "Type-A1", "Model-X200", "Type: B500", "Model-200".
_EQUIPMENT_RE: re.Pattern[str] = re.compile(
    r"\b(?:Type|Model)\s*[-:]\s*[A-Za-z0-9]+", re.IGNORECASE
)

# Parameters: temperature (XX-XXXX °C/°F), thickness (X.X mm), pressure (X.X MPa).
# WHY: These three parameter types are the most common quantitative constraints
#      in marine engineering regulations (material properties, design limits).
_TEMPERATURE_RE: re.Pattern[str] = re.compile(r"\b\d{2,4}\s*(?:°\s*)?[CF]\b")
_THICKNESS_RE: re.Pattern[str] = re.compile(r"\b\d+(?:\.\d+)?\s*mm\b")
_PRESSURE_RE: re.Pattern[str] = re.compile(r"\b\d+(?:\.\d+)?\s*MPa\b")


# ===================================================================
# Internal helpers
# ===================================================================


def _make_entity_id(name: str, entity_type: str) -> str:
    """Generate a deterministic entity ID from name and type.

    WHAT: Computes MD5 hash of "name:entity_type" to produce a stable,
          unique identifier for each entity.

    WHY: Deterministic IDs enable deduplication across extraction runs.
         The same entity (same name + type) always gets the same ID,
         which is critical for incremental graph updates.
    """
    raw = f"{name}:{entity_type}"
    return hashlib.md5(raw.encode()).hexdigest()


def _make_relation_id(
    source_entity_id: str, target_entity_id: str, relation_type: str
) -> str:
    """Generate a deterministic relation ID.

    WHAT: Computes MD5 hash of "source_id:target_id:relation_type".

    WHY: Same as entity IDs — deterministic hashing enables deduplication
         and ensures the same relation is not inserted twice.
    """
    raw = f"{source_entity_id}:{target_entity_id}:{relation_type}"
    return hashlib.md5(raw.encode()).hexdigest()


def _find_match_spans(pattern: re.Pattern[str], text: str) -> list[dict[str, Any]]:
    """Find all non-overlapping matches and return span info.

    WHAT: Applies a compiled regex pattern to text and returns a list of
          dicts with 'name' (matched text), 'start', and 'end' positions.

    WHY: Span information is required by apply_negation_filter() to check
         whether a match appears within a negation phrase.
    """
    results: list[dict[str, Any]] = []
    for m in pattern.finditer(text):
        results.append({
            "name": m.group().strip(),
            "start": m.start(),
            "end": m.end(),
        })
    return results


def _deduplicate_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove matches with overlapping spans, keeping the longest match.

    WHAT: When multiple regex patterns match overlapping text (e.g. a compound
          "Pt.4 Ch.3" and standalone "Ch.3" within it), this function keeps
          only the longest match for each overlapping group.

    WHY: Compound clause references (e.g. "Pt.4 Ch.3") are more informative
         than standalone fragments (e.g. "Ch.3"). We prefer the most specific
         match to avoid fragmenting clause identifiers.
    """
    if not matches:
        return []

    # Sort by start position ascending, then by length descending (longest first)
    sorted_matches = sorted(matches, key=lambda m: (m["start"], m["start"] - m["end"]))

    kept: list[dict[str, Any]] = []
    last_end = -1
    for m in sorted_matches:
        if m["start"] >= last_end:
            # No overlap with previous kept match
            kept.append(m)
            last_end = m["end"]
        elif m["end"] > last_end:
            # Overlaps but extends further — keep this one instead
            # This handles the case where we processed a short match first
            kept.append(m)
            last_end = m["end"]
        # else: fully contained within previous match — skip

    return kept


# ===================================================================
# Public extractor functions
# ===================================================================


def extract_steel_grades(text: str) -> list[Entity]:
    """Extract steel grade entities using regex.

    WHAT: Finds patterns matching [A-Z]{2,4}\\d{2,3} (e.g. DH36, EH36, AH32)
          and returns them as Entity objects with type "steel_grade".

    WHY: Steel grades are critical material specification entities in
         shipbuilding. They appear frequently in hull construction,
         structural design, and welding procedure documents.

    Args:
        text: The input text to scan for steel grade patterns.

    Returns:
        List of Entity objects with entity_type="steel_grade".
    """
    matches = _find_match_spans(_STEEL_GRADE_RE, text)
    entities: list[Entity] = []
    seen: set[str] = set()
    for m in matches:
        name = m["name"]
        if name in seen:
            continue
        seen.add(name)
        entities.append(Entity(
            entity_id=_make_entity_id(name, "steel_grade"),
            name=name,
            entity_type="steel_grade",
        ))
    return entities


def extract_regulation_clauses(text: str) -> list[Entity]:
    """Extract regulation clause entities using regex.

    WHAT: Finds patterns like Pt.4 Ch.3, Part 5 Chapter 2, Ch.2, Section 6.1,
          § 5.2 and returns them as Entity objects with type "regulation_clause".

    WHY: Regulation clauses are the primary organizational units of ship
         classification rules. They serve as navigation anchors in the
         knowledge graph for cross-referencing between documents.

    Args:
        text: The input text to scan for clause patterns.

    Returns:
        List of Entity objects with entity_type="regulation_clause".
    """
    # Collect all matches from all clause patterns
    all_matches: list[dict[str, Any]] = []
    for pattern in _CLAUSE_PATTERNS:
        all_matches.extend(_find_match_spans(pattern, text))

    # Deduplicate overlapping matches (keep longest/most specific)
    all_matches = _deduplicate_matches(all_matches)

    # Convert to Entity objects, skipping duplicates by name
    entities: list[Entity] = []
    seen: set[str] = set()
    for m in all_matches:
        name = m["name"]
        if name in seen:
            continue
        seen.add(name)
        entities.append(Entity(
            entity_id=_make_entity_id(name, "regulation_clause"),
            name=name,
            entity_type="regulation_clause",
        ))
    return entities


def extract_equipment(text: str) -> list[Entity]:
    """Extract equipment entities using regex.

    WHAT: Finds patterns like Type-A1, Model-X200 (Type-/Model- prefix
          followed by an alphanumeric identifier) and returns them as
          Entity objects with type "equipment".

    WHY: Equipment identifiers appear throughout marine engineering
         specifications, especially in fire safety, machinery, and
         electrical system sections.

    Args:
        text: The input text to scan for equipment identifiers.

    Returns:
        List of Entity objects with entity_type="equipment".
    """
    matches = _find_match_spans(_EQUIPMENT_RE, text)
    entities: list[Entity] = []
    seen: set[str] = set()
    for m in matches:
        name = m["name"]
        if name in seen:
            continue
        seen.add(name)
        entities.append(Entity(
            entity_id=_make_entity_id(name, "equipment"),
            name=name,
            entity_type="equipment",
        ))
    return entities


def extract_parameters(text: str) -> list[Entity]:
    """Extract parameter entities (temperature, thickness, pressure).

    WHAT: Finds temperature values (XX-XXXX °C/°F), thickness values
          (X.X mm), and pressure values (X.X MPa) and returns them as
          Entity objects with type "parameter".

    WHY: Quantitative parameters are first-class entities in the knowledge
         graph because they constrain and govern design decisions. They
         form the basis for constraint validation and design checking.

    Args:
        text: The input text to scan for parameter values.

    Returns:
        List of Entity objects with entity_type="parameter".
    """
    all_matches: list[dict[str, Any]] = []

    # Temperature: 2-4 digit number followed by optional degree symbol and C/F
    all_matches.extend(_find_match_spans(_TEMPERATURE_RE, text))

    # Thickness: number (optionally decimal) followed by mm
    all_matches.extend(_find_match_spans(_THICKNESS_RE, text))

    # Pressure: number (optionally decimal) followed by MPa
    all_matches.extend(_find_match_spans(_PRESSURE_RE, text))

    # Convert to Entity objects, skipping duplicates by name
    entities: list[Entity] = []
    seen: set[str] = set()
    for m in all_matches:
        name = m["name"]
        if name in seen:
            continue
        seen.add(name)
        entities.append(Entity(
            entity_id=_make_entity_id(name, "parameter"),
            name=name,
            entity_type="parameter",
        ))
    return entities


def extract_ship_types(text: str) -> list[Entity]:
    """Extract ship type entities using dictionary lookup.

    WHAT: Searches the text for known ship types (bulk carrier, oil tanker,
          container ship, LNG carrier, etc.) using case-insensitive matching
          against a curated dictionary of marine vessel types.

    WHY: Ship types are high-level classification entities that determine
         which regulatory frameworks apply. Dictionary lookup is used
         instead of regex because ship type naming is not pattern-based
         (unlike steel grades or clause numbers).

    Args:
        text: The input text to scan for known ship type names.

    Returns:
        List of Entity objects with entity_type="ship_type".
    """
    entities: list[Entity] = []
    seen: set[str] = set()
    text_lower = text.lower()

    for search_key, canonical_name in SHIP_TYPES.items():
        if search_key in text_lower:
            if canonical_name in seen:
                continue
            seen.add(canonical_name)
            entities.append(Entity(
                entity_id=_make_entity_id(canonical_name, "ship_type"),
                name=canonical_name,
                entity_type="ship_type",
            ))
    return entities


# ===================================================================
# Negation filter
# ===================================================================


def apply_negation_filter(text: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter out matches that fall within negation phrases.

    WHAT: For each match, checks whether its character span overlaps with
          any negation phrase (except, excluding, not applicable to,
          does not apply to). Matches inside negation phrases are removed.

    WHY: Regulatory texts frequently use exception clauses (e.g. "all systems
         except emergency systems"). Without negation filtering, entities
         mentioned in exceptions would be incorrectly extracted as applicable
         entities, leading to false positives in the knowledge graph.

    Args:
        text: The original text being analyzed.
        matches: List of match dicts, each with 'name', 'start', 'end' keys
                 representing the matched entity's span in the text.

    Returns:
        Filtered list of match dicts, with negated matches removed.
    """
    # Find all negation spans in the text
    negated_ranges: list[tuple[int, int]] = []
    for pattern in NEGATION_PATTERNS:
        for m in pattern.finditer(text):
            target_span = m.span("target")
            # Expand the negation span slightly to include the keyword itself
            negated_ranges.append((m.start(), m.end()))

    if not negated_ranges:
        return matches

    # Filter out matches whose span overlaps with any negation range
    def _is_negated(match_start: int, match_end: int) -> bool:
        """Check if a match span overlaps with any negation range."""
        for neg_start, neg_end in negated_ranges:
            # Overlap check: two ranges overlap if one does not end before
            # the other starts
            if match_start < neg_end and match_end > neg_start:
                return True
        return False

    return [m for m in matches if not _is_negated(m["start"], m["end"])]


# ===================================================================
# Private extraction helpers (return match dicts with span info)
# ===================================================================


def _extract_all_raw_matches(text: str) -> dict[str, list[dict[str, Any]]]:
    """Run all extractors and collect raw matches with span info.

    WHAT: Runs each entity type's regex/dict matching logic and returns
          a dict mapping entity_type -> list of match dicts with spans.

    WHY: The orchestrator needs span information to apply negation filtering
          before converting matches to Entity objects. This helper separates
          match-finding from Entity construction.

    Args:
        text: The input text to scan.

    Returns:
        Dict mapping entity_type to list of match dicts (name, start, end).
    """
    raw: dict[str, list[dict[str, Any]]] = {}

    # Steel grades
    raw["steel_grade"] = _find_match_spans(_STEEL_GRADE_RE, text)

    # Regulation clauses (with deduplication)
    clause_matches: list[dict[str, Any]] = []
    for pattern in _CLAUSE_PATTERNS:
        clause_matches.extend(_find_match_spans(pattern, text))
    raw["regulation_clause"] = _deduplicate_matches(clause_matches)

    # Equipment
    raw["equipment"] = _find_match_spans(_EQUIPMENT_RE, text)

    # Parameters (temperature + thickness + pressure)
    param_matches: list[dict[str, Any]] = []
    param_matches.extend(_find_match_spans(_TEMPERATURE_RE, text))
    param_matches.extend(_find_match_spans(_THICKNESS_RE, text))
    param_matches.extend(_find_match_spans(_PRESSURE_RE, text))
    raw["parameter"] = param_matches

    # Ship types: find matches with span info
    ship_matches: list[dict[str, Any]] = []
    text_lower = text.lower()
    seen_names: set[str] = set()
    for search_key, canonical_name in SHIP_TYPES.items():
        if canonical_name in seen_names:
            continue
        idx = text_lower.find(search_key)
        if idx != -1:
            seen_names.add(canonical_name)
            ship_matches.append({
                "name": canonical_name,
                "start": idx,
                "end": idx + len(search_key),
            })
    raw["ship_type"] = ship_matches

    return raw


# ===================================================================
# Main orchestrator
# ===================================================================


def extract_entities(text: str, doc_id: str = "") -> list[Entity]:
    """Run all rule-based extractors and return combined, deduplicated entities.

    WHAT: Orchestrates all five entity extractors (steel grades, regulation
          clauses, equipment, parameters, ship types), applies negation
          filtering, and returns a unified list of Entity objects.

    WHY: This is the primary public API for rule-based extraction. Downstream
         modules (LLM extractor, merger, engine) call this to get baseline
         entities before LLM enhancement.

    The pipeline:
      1. Run all extractors to collect raw matches with span info.
      2. Apply negation filtering to remove matches in exception clauses.
      3. Convert filtered matches to Entity objects with deterministic IDs.
      4. Deduplicate by entity_id.

    Args:
        text: The input text to extract entities from.
        doc_id: Optional source document ID to stamp on all entities.

    Returns:
        Combined list of Entity objects covering all entity types found.
    """
    if not text or not text.strip():
        return []

    # Step 1: Collect raw matches with span info
    raw_by_type = _extract_all_raw_matches(text)

    # Step 2: Apply negation filtering to each type's matches
    filtered_by_type: dict[str, list[dict[str, Any]]] = {}
    for entity_type, matches in raw_by_type.items():
        if matches:
            filtered_by_type[entity_type] = apply_negation_filter(text, matches)
        else:
            filtered_by_type[entity_type] = []

    # Step 3: Convert matches to Entity objects
    entities: list[Entity] = []
    seen_ids: set[str] = set()

    for entity_type, matches in filtered_by_type.items():
        seen_names: set[str] = set()
        for m in matches:
            name = m["name"]
            # Skip duplicate names within the same type
            if name in seen_names:
                continue
            seen_names.add(name)

            entity_id = _make_entity_id(name, entity_type)
            # Skip duplicate IDs across all types (shouldn't happen since
            # ID includes type, but defensive check)
            if entity_id in seen_ids:
                continue
            seen_ids.add(entity_id)

            entities.append(Entity(
                entity_id=entity_id,
                name=name,
                entity_type=entity_type,
                source_doc_id=doc_id if doc_id else None,
            ))

    return entities


def extract_relations(entities: list[Entity]) -> list[Relation]:
    """Generate relations between extracted entities.

    WHAT: Creates two types of relations:
      1. 'references': Between regulation_clause entities. Clauses that
         appear in the same document text are linked as referencing each
         other. This captures the hierarchical and cross-reference structure
         of classification rules.
      2. 'constrains': From parameter entities to non-parameter, non-clause
         entities (equipment, steel_grade, ship_type). Each parameter is
         linked to every applicable entity because the parameter value
         constrains the design or operation of that entity.

    WHY: Relations connect entities into a usable knowledge graph. References
         enable clause-level navigation; constrains enable parametric design
         checking and rule validation.

    Args:
        entities: List of Entity objects extracted from text.

    Returns:
        List of Relation objects with deterministic IDs and confidence=1.0.
    """
    relations: list[Relation] = []
    seen_relation_ids: set[str] = set()

    # Group entities by type
    by_type: dict[str, list[Entity]] = {}
    for e in entities:
        by_type.setdefault(e.entity_type, []).append(e)

    # Collect non-clause, non-parameter entities for constrains relations
    constrainable = (
        by_type.get("steel_grade", [])
        + by_type.get("equipment", [])
        + by_type.get("ship_type", [])
    )

    # === references: between regulation_clause entities ===
    # Sort clauses by name for deterministic ordering
    clauses = sorted(by_type.get("regulation_clause", []), key=lambda e: e.name)
    # Create pairwise references: each clause references the next clause
    # WHY: Clauses that appear together in the same text are semantically
    #      related, typically forming a hierarchical structure.
    for i in range(len(clauses)):
        for j in range(i + 1, len(clauses)):
            source = clauses[i]
            target = clauses[j]
            rel_id = _make_relation_id(
                source.entity_id, target.entity_id, "references"
            )
            if rel_id not in seen_relation_ids:
                seen_relation_ids.add(rel_id)
                relations.append(Relation(
                    relation_id=rel_id,
                    source_entity_id=source.entity_id,
                    target_entity_id=target.entity_id,
                    relation_type="references",
                    confidence=1.0,
                ))

    # === constrains: parameter → constrainable entity ===
    # WHY: A parameter value (e.g. 25mm thickness) constrains the design
    #      or operation of equipment, steel grades, or vessel types that
    #      appear in the same specification text.
    parameters = by_type.get("parameter", [])
    for param in parameters:
        for target in constrainable:
            rel_id = _make_relation_id(
                param.entity_id, target.entity_id, "constrains"
            )
            if rel_id not in seen_relation_ids:
                seen_relation_ids.add(rel_id)
                relations.append(Relation(
                    relation_id=rel_id,
                    source_entity_id=param.entity_id,
                    target_entity_id=target.entity_id,
                    relation_type="constrains",
                    confidence=1.0,
                ))

    return relations
