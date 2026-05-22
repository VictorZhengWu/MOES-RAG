# -*- coding: utf-8 -*-
"""
M1-to-M2 storage bridge.

WHAT: Provides the translation layer between M1 (Document Parsing Engine)
and M2 (Storage Abstraction Layer). Converts M1 domain objects into
M2-compatible record dicts and enforces quality gating before content
enters the vector database.

Two core functions:
  1. create_document_record()  -- build an m1_documents table row dict
  2. should_store_in_vector_store()  -- quality gate for chunk admission

WHY: M1 and M2 communicate only through contracts/ (Protocols + Pydantic
schemas). This bridge encapsulates all translation logic in one module
so that:
  - M1's pipeline code never touches M2's concrete table schemas
  - M2's backend changes (e.g., adding a column) only require updates here
  - The quality gating decision is centralized, auditable, and testable

Design decisions:
  - Record dicts use snake_case keys matching M2's SQLAlchemy column names
  - Metadata fields are flattened into the record dict (not nested),
    matching the relational DB schema design
  - The quality gate uses duck typing (dict.get / hasattr) so it works
    with both raw dicts and Chunk dataclass objects
  - The gate defaults to "allow" when review_required is absent -- this
    is the safe default because only explicitly flagged content should
    be blocked
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# ===========================================================================
# Metadata field name constants
# ===========================================================================

# WHAT: the canonical set of metadata fields extracted from the metadata
# dict and flattened into the document record.
# WHY: centralized list prevents key-name drift between the bridge and
# the test suite. If a new metadata field is added to DocumentMetadata,
# it must be added here to appear in the record dict.
_METADATA_FIELDS = [
    "classification_society",
    "regulation_name",
    "version_year",
    "chapter_section",
    "language",
    "domain",
    "vessel_types",
    "system_type",
    "manufacturer",
    "equipment_model",
    "page_range",
    "custom_tags",
]

# WHAT: default values for each metadata field when the metadata dict
# does not contain the key.
# WHY: prevents None from silently propagating into storage. Each default
# was chosen to match the DocumentMetadata dataclass defaults in
# contracts/document.py.
_METADATA_DEFAULTS: dict[str, Any] = {
    "classification_society": None,
    "regulation_name": None,
    "version_year": None,
    "chapter_section": None,
    "language": "zh",
    "domain": "general",
    "vessel_types": [],
    "system_type": None,
    "manufacturer": None,
    "equipment_model": None,
    "page_range": None,
    "custom_tags": {},
}


# ===========================================================================
# Public API
# ===========================================================================


def create_document_record(
    doc_id: str,
    original_name: str,
    file_type: str = "",
    output_dir: str = "",
    markdown_path: str = "",
    json_path: str = "",
    page_count: int = 0,
    chunk_count: int = 0,
    metadata: dict[str, Any] | None = None,
    parsed_at: datetime | None = None,
) -> dict[str, Any]:
    """
    Build an m1_documents table record dict with all required fields.

    WHAT: constructs a complete dictionary representing a single row in
    the m1_documents relational database table. The dict includes:

      Structural fields (from pipeline output):
        - doc_id, original_name, file_type, output_dir
        - markdown_path, json_path, page_count, chunk_count

      Metadata fields (flattened from DocumentMetadata):
        - classification_society, regulation_name, version_year
        - chapter_section, language, domain, vessel_types
        - system_type, manufacturer, equipment_model
        - page_range, custom_tags

      Timestamp:
        - parsed_at (ISO 8601 UTC datetime)

    Args:
        doc_id: Unique document identifier (UUID or hash-based).
        original_name: Original filename as uploaded by the user.
        file_type: File extension / MIME category (pdf, docx, xlsx, etc.).
        output_dir: Root output directory for this document's artifacts.
        markdown_path: Full path to the parsed Markdown file.
        json_path: Full path to the parsed JSON output file.
        page_count: Total number of pages in the source document.
        chunk_count: Total number of semantic chunks produced.
        metadata: Dictionary of extracted metadata. Keys are the field
            names from DocumentMetadata / marine_metadata.py.
        parsed_at: UTC datetime when parsing completed. If None, the
            current UTC time is used.

    Returns:
        A dict with all m1_documents column values. Every key in the
        returned dict corresponds to a database column.

    WHY: provides a single, consistent constructor for document records.
    Every caller (converter.py pipeline, standalone CLI, web API endpoint)
    uses this function to produce identically-structured records. This
    eliminates field-ordering bugs, missing-column errors, and key-name
    drift across the codebase.

    Examples:
        >>> record = create_document_record("doc-001", "spec.pdf")
        >>> record["doc_id"]
        'doc-001'
        >>> record["language"]
        'zh'
        >>> isinstance(record["parsed_at"], datetime)
        True
    """
    # Resolve metadata defaults: overlay provided values on top of defaults
    metadata_source = metadata if metadata is not None else {}
    resolved_meta: dict[str, Any] = {}
    for field_name in _METADATA_FIELDS:
        resolved_meta[field_name] = metadata_source.get(
            field_name, _METADATA_DEFAULTS[field_name]
        )

    # Auto-populate parsed_at if not provided
    # WHY: callers should not need to manage timestamps manually.
    # Using timezone-aware UTC ensures consistent sorting across
    # deployments in different geographic regions.
    effective_parsed_at = parsed_at if parsed_at is not None else datetime.now(timezone.utc)

    # Build the complete record dict
    # WHY: the explicit key-value layout makes it obvious which fields
    # are present and what their types are. This is more maintainable
    # than a dynamic **kwargs spread or a loop-based constructor.
    record: dict[str, Any] = {
        # --- Structural fields ---
        "doc_id": doc_id,
        "original_name": original_name,
        "file_type": file_type,
        "output_dir": output_dir,
        "markdown_path": markdown_path,
        "json_path": json_path,
        "page_count": page_count,
        "chunk_count": chunk_count,
        # --- Metadata fields (flattened from DocumentMetadata) ---
        "classification_society": resolved_meta["classification_society"],
        "regulation_name": resolved_meta["regulation_name"],
        "version_year": resolved_meta["version_year"],
        "chapter_section": resolved_meta["chapter_section"],
        "language": resolved_meta["language"],
        "domain": resolved_meta["domain"],
        "vessel_types": resolved_meta["vessel_types"],
        "system_type": resolved_meta["system_type"],
        "manufacturer": resolved_meta["manufacturer"],
        "equipment_model": resolved_meta["equipment_model"],
        "page_range": resolved_meta["page_range"],
        "custom_tags": resolved_meta["custom_tags"],
        # --- Timestamp ---
        "parsed_at": effective_parsed_at,
    }

    return record


def should_store_in_vector_store(chunk: Any) -> bool:
    """
    Quality gate: determine whether a chunk should enter the vector database.

    WHAT: inspects the chunk's ``review_required`` flag and returns False
    if it is explicitly set to True (boolean). Chunks flagged for review
    have quality issues -- cross-page tables, merged cells, footnote
    references -- that would produce incorrect embeddings and degrade
    downstream retrieval precision.

    The function uses duck typing to support multiple chunk representations:

      - dict: checks ``chunk.get("review_required", False)``
      - object: checks ``getattr(chunk, "review_required", False)``
      - None / missing field: treated as False (safe default = allow)

    Args:
        chunk: A chunk in any of the supported representations (dict,
            dataclass, MagicMock, etc.). The chunk is expected to have
            a ``review_required`` field/attribute but this is not
            strictly required.

    Returns:
        True if the chunk is safe to store in the vector database
        (no review required). False if the chunk must be held back
        for human review in the M7 admin portal.

    WHY: the quality gating pipeline (core/quality.py) analyzes parsed
    tables and assigns a gating level based on 7 structural factors.
    Chunks with score 1+ get ``review_required = True``. This gate is
    the mechanism that enforces the gating decision -- it prevents
    gated content from reaching the vector store and contaminating
    the retrieval index.

    The gate is intentionally strict: only an explicit boolean True
    value triggers a block. String values like "true" or "1" are NOT
    treated as True, preventing serialization artifacts from causing
    false positives.

    Usage in pipeline:
        for chunk in parsed_document.chunks:
            if should_store_in_vector_store(chunk):
                await vector_store.insert([chunk], [embedding])
            else:
                logger.info(f"Chunk {chunk.chunk_id} held for review")

    Examples:
        >>> should_store_in_vector_store({"review_required": False})
        True
        >>> should_store_in_vector_store({"review_required": True})
        False
        >>> should_store_in_vector_store({"text": "hello"})
        True
    """
    # Extract review_required from dict or object
    # WHY: use duck typing so the function works with raw dicts from
    # serialized data, Chunk dataclass instances, and mock objects in
    # tests without requiring isinstance checks.
    review_flag: Any = None

    if isinstance(chunk, dict):
        # Dict-based chunk (e.g., from JSON deserialization or test data)
        review_flag = chunk.get("review_required", False)
    elif hasattr(chunk, "review_required"):
        # Object-based chunk (e.g., Chunk dataclass or QualityAssessment)
        review_flag = chunk.review_required
    else:
        # No review_required field at all -- safe default is to allow
        # WHY: only explicitly flagged content should be blocked.
        # Blocking by default would require every chunk producer to
        # set the field, creating a fragile coupling.
        return True

    # Gate logic: only an explicit boolean True blocks storage
    # WHY: strict bool check prevents string "true", int 1, or other
    # truthy values from causing false-positive blocks. The quality
    # gating pipeline always sets review_required as a real bool, so
    # non-bool values indicate a data integrity issue elsewhere.
    if review_flag is True:
        return False

    # All other cases: allow the chunk through
    return True
