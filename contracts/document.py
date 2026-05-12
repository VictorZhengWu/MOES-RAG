"""
Document data models shared across modules.

Defines the canonical document representation that flows from
M1 (Doc Parsing) → M2 (Storage) → M3/M4/M5 (Consumers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Domain(str, Enum):
    """Professional domain / engineering discipline."""
    STRUCTURE = "structure"
    MACHINERY = "machinery"
    PIPING = "piping"
    ELECTRICAL = "electrical"
    COMMUNICATION = "communication"
    AUTOMATION = "automation"
    GENERAL = "general"


class VesselType(str, Enum):
    """Ship and offshore structure types."""
    BULK_CARRIER = "bulk_carrier"
    CONTAINER_SHIP = "container_ship"
    OIL_TANKER = "oil_tanker"
    LNG_CARRIER = "lng_carrier"
    DRILLING_PLATFORM = "drilling_platform"
    WIND_PLATFORM = "wind_platform"
    GENERAL = "general"


class ClassificationSociety(str, Enum):
    """Classification societies."""
    CCS = "CCS"
    DNV = "DNV"
    ABS = "ABS"
    LR = "LR"
    BV = "BV"
    NK = "NK"
    RINA = "RINA"
    KR = "KR"
    IACS = "IACS"
    IMO = "IMO"


@dataclass
class DocumentMetadata:
    """Metadata extracted during document parsing.

    Used for filtering and routing during retrieval.
    """
    source_filename: str
    classification_society: ClassificationSociety | None = None
    regulation_name: str | None = None
    version_year: int | None = None
    chapter_section: str | None = None
    domain: Domain = Domain.GENERAL
    vessel_types: list[VesselType] = field(default_factory=list)
    system_type: str | None = None
    manufacturer: str | None = None
    equipment_model: str | None = None
    language: str = "zh"
    page_range: tuple[int, int] | None = None
    custom_tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Chunk:
    """A single semantic chunk of parsed document content."""
    chunk_id: str
    text: str
    metadata: DocumentMetadata
    chunk_type: str  # "clause" | "table" | "figure" | "formula" | "general"
    parent_section: str | None = None
    position_in_document: int = 0
    embedding: list[float] | None = None


@dataclass
class ParsedDocument:
    """Output of M1 Doc Parsing Engine."""
    doc_id: str
    parsed_at: datetime
    source_file_hash: str
    metadata: DocumentMetadata
    chunks: list[Chunk]
    raw_markdown: str | None = None
    tables_json: list[dict[str, Any]] = field(default_factory=list)
    figures_descriptions: list[dict[str, str]] = field(default_factory=list)
