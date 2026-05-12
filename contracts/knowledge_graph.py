"""
Knowledge Graph engine protocols (M4).

Defines the graph engine interface consumed by M5 (QA Engine).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Entity:
    """A node in the knowledge graph."""
    entity_id: str
    name: str
    entity_type: str  # "regulation_clause" | "vessel_type" | "system" | "equipment" | "manufacturer"
    properties: dict[str, Any] = field(default_factory=dict)
    source_doc_id: str | None = None


@dataclass
class Relation:
    """An edge between two entities in the knowledge graph."""
    relation_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str  # "references" | "applies_to" | "equivalent_to" | "replaces" | "requires" | "prohibits"
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class Subgraph:
    """A subgraph result from a graph query."""
    entities: list[Entity]
    relations: list[Relation]
    query_context: str


@dataclass
class CrossReferenceResult:
    """Result of cross-classification-society mapping."""
    source_society: str
    source_clause: str
    target_society: str
    target_clause: str
    relation_type: str  # "equivalent" | "similar" | "related"
    confidence: float
    notes: str = ""


@runtime_checkable
class KGEngineProtocol(Protocol):
    """Interface for the knowledge graph engine."""

    async def extract_entities(
        self, document_id: str, chunks: list
    ) -> list[Entity]:
        """Extract entities from parsed document chunks."""
        ...

    async def extract_relations(self, entities: list[Entity]) -> list[Relation]:
        """Extract relations among entities."""
        ...

    async def query_entities(
        self, query_text: str, entity_types: list[str] | None = None, limit: int = 20
    ) -> list[Entity]:
        """Search for entities matching the query."""
        ...

    async def query_relations(
        self, entity_ids: list[str], relation_types: list[str] | None = None
    ) -> list[Relation]:
        """Find relations involving the given entities."""
        ...

    async def graph_search(
        self, topic: str, depth: int = 2
    ) -> Subgraph:
        """Traverse the graph from matching seed entities."""
        ...

    async def cross_reference(
        self, source_clause: str, source_society: str, target_society: str
    ) -> CrossReferenceResult | None:
        """Map a clause from one classification society to its equivalent in another."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Verify graph database connectivity."""
        ...
