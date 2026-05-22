# -*- coding: utf-8 -*-
"""
Unit tests for m2_bridge.py -- M1-to-M2 storage bridge.

WHY: The M2 bridge is the integration point between M1's parsed document
output and M2's storage layer. Incorrect record construction or faulty
quality gating would corrupt the document index, let bad content into
the vector database, or drop valid content. These tests verify:
  - Document record construction with all required fields
  - Quality gate: approved chunks pass through to VectorStore
  - Quality gate: review_required chunks are blocked
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from m1_parser.integration.m2_bridge import (
    create_document_record,
    should_store_in_vector_store,
)


# ===========================================================================
# Test 1: Document record construction -- all fields populated
# ===========================================================================


def test_create_document_record_full():
    """
    create_document_record() MUST produce a dict with all required fields
    correctly populated from the input arguments.

    WHAT we verify:
      - Structural fields (doc_id, original_name, file_type, output_dir,
        markdown_path, json_path, page_count, chunk_count) are set correctly.
      - Metadata fields (classification_society, regulation_name,
        version_year, chapter_section, language, domain, vessel_types,
        system_type, manufacturer, equipment_model, page_range, custom_tags)
        are extracted from the metadata dict argument.
      - parsed_at is set to the provided datetime or the current time.
      - The returned dict has consistent snake_case key naming.
      - Default values for optional fields are sensible (empty strings, 0, etc.).

    WHY: every caller in the converter pipeline, standalone mode, and web API
    relies on this function to produce identically-structured records. A
    missing or misnamed field would cause silent data loss in the storage layer.
    """
    parsed_at = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)
    metadata = {
        "classification_society": "DNV",
        "regulation_name": "DNV-ST-N001",
        "version_year": 2023,
        "chapter_section": "Ch.3 Sec.2",
        "language": "en",
        "domain": "structure",
        "vessel_types": ["bulk_carrier", "oil_tanker"],
        "system_type": "Hull Structure",
        "manufacturer": "",
        "equipment_model": "",
        "page_range": (1, 450),
        "custom_tags": {"project": "newbuild-hull-2025"},
    }

    record = create_document_record(
        doc_id="doc-abc123",
        original_name="DNV-ST-N001.pdf",
        file_type="pdf",
        output_dir="/data/output/doc-abc123/",
        markdown_path="/data/output/doc-abc123/full.md",
        json_path="/data/output/doc-abc123/full.json",
        page_count=450,
        chunk_count=187,
        metadata=metadata,
        parsed_at=parsed_at,
    )

    # --- Structural fields ---
    assert record["doc_id"] == "doc-abc123", (
        f"Expected doc_id='doc-abc123', got {record.get('doc_id')}"
    )
    assert record["original_name"] == "DNV-ST-N001.pdf", (
        f"Expected original_name='DNV-ST-N001.pdf', got {record.get('original_name')}"
    )
    assert record["file_type"] == "pdf", (
        f"Expected file_type='pdf', got {record.get('file_type')}"
    )
    assert record["output_dir"] == "/data/output/doc-abc123/", (
        f"Expected output_dir path, got {record.get('output_dir')}"
    )
    assert record["markdown_path"] == "/data/output/doc-abc123/full.md", (
        f"Expected markdown_path, got {record.get('markdown_path')}"
    )
    assert record["json_path"] == "/data/output/doc-abc123/full.json", (
        f"Expected json_path, got {record.get('json_path')}"
    )
    assert record["page_count"] == 450, (
        f"Expected page_count=450, got {record.get('page_count')}"
    )
    assert record["chunk_count"] == 187, (
        f"Expected chunk_count=187, got {record.get('chunk_count')}"
    )

    # --- Metadata fields ---
    assert record["classification_society"] == "DNV", (
        f"Expected classification_society='DNV', got {record.get('classification_society')}"
    )
    assert record["regulation_name"] == "DNV-ST-N001", (
        f"Expected regulation_name='DNV-ST-N001', got {record.get('regulation_name')}"
    )
    assert record["version_year"] == 2023, (
        f"Expected version_year=2023, got {record.get('version_year')}"
    )
    assert record["chapter_section"] == "Ch.3 Sec.2", (
        f"Expected chapter_section='Ch.3 Sec.2', got {record.get('chapter_section')}"
    )
    assert record["language"] == "en", (
        f"Expected language='en', got {record.get('language')}"
    )
    assert record["domain"] == "structure", (
        f"Expected domain='structure', got {record.get('domain')}"
    )
    assert record["vessel_types"] == ["bulk_carrier", "oil_tanker"], (
        f"Expected vessel_types list, got {record.get('vessel_types')}"
    )
    assert record["system_type"] == "Hull Structure", (
        f"Expected system_type='Hull Structure', got {record.get('system_type')}"
    )
    assert record["manufacturer"] == "", (
        f"Expected manufacturer='', got {record.get('manufacturer')}"
    )
    assert record["equipment_model"] == "", (
        f"Expected equipment_model='', got {record.get('equipment_model')}"
    )
    assert record["page_range"] == (1, 450), (
        f"Expected page_range=(1, 450), got {record.get('page_range')}"
    )
    assert record["custom_tags"] == {"project": "newbuild-hull-2025"}, (
        f"Expected custom_tags dict, got {record.get('custom_tags')}"
    )

    # --- Timestamp ---
    assert record["parsed_at"] == parsed_at, (
        f"Expected parsed_at={parsed_at}, got {record.get('parsed_at')}"
    )


def test_create_document_record_minimal():
    """
    create_document_record() with only required args MUST produce a valid
    record with sensible defaults for all optional fields.

    WHY: callers should not be forced to provide every optional field.
    Sensible defaults prevent None values from leaking into storage.
    """
    record = create_document_record(
        doc_id="doc-min-001",
        original_name="report.docx",
    )

    assert record["doc_id"] == "doc-min-001"
    assert record["original_name"] == "report.docx"

    # All optional fields should have sensible defaults
    assert record["file_type"] == "", "file_type should default to ''"
    assert record["output_dir"] == "", "output_dir should default to ''"
    assert record["markdown_path"] == "", "markdown_path should default to ''"
    assert record["json_path"] == "", "json_path should default to ''"
    assert record["page_count"] == 0, "page_count should default to 0"
    assert record["chunk_count"] == 0, "chunk_count should default to 0"

    # Metadata fields should default sensibly
    assert record["classification_society"] is None
    assert record["regulation_name"] is None
    assert record["version_year"] is None
    assert record["chapter_section"] is None
    assert record["language"] == "zh", "language should default to 'zh'"
    assert record["domain"] == "general"
    assert record["system_type"] is None
    assert record["manufacturer"] is None
    assert record["equipment_model"] is None
    assert record["vessel_types"] == []
    assert record["page_range"] is None
    assert record["custom_tags"] == {}

    # parsed_at should be auto-populated with current UTC time
    assert isinstance(record["parsed_at"], datetime), (
        f"parsed_at should be a datetime, got {type(record['parsed_at'])}"
    )
    # Should be within a few seconds of now
    now = datetime.now(timezone.utc)
    delta = abs((now - record["parsed_at"]).total_seconds())
    assert delta < 10, (
        f"parsed_at should be close to now, delta={delta}s"
    )


# ===========================================================================
# Test 2: Quality gate -- approved chunk passes through
# ===========================================================================


def test_should_store_approved_chunk():
    """
    A chunk with review_required=False MUST be allowed into the vector store.

    WHAT: should_store_in_vector_store() returns True when the chunk
    has no quality issues (review_required=False or absent).

    WHY: the quality gating pipeline marks simple, well-parsed chunks
    with review_required=False. These chunks should flow directly to
    the vector database without human intervention. The gate must not
    produce false positives that block valid content.
    """

    # --- Dict-based chunk: review_required explicitly False ---
    chunk_dict_false = {
        "chunk_id": "ch-001",
        "text": "Material yield strength shall be at least 355 MPa.",
        "review_required": False,
        "confidence": 1.0,
    }
    assert should_store_in_vector_store(chunk_dict_false) is True, (
        "Dict chunk with review_required=False should be allowed"
    )

    # --- Dict-based chunk: review_required absent (default: pass) ---
    chunk_dict_no_field = {
        "chunk_id": "ch-002",
        "text": "Welding procedures per AWS D1.1.",
    }
    assert should_store_in_vector_store(chunk_dict_no_field) is True, (
        "Dict chunk without review_required field should be allowed (default pass)"
    )

    # --- Object-based chunk: review_required=False ---
    chunk_obj_ok = MagicMock()
    chunk_obj_ok.review_required = False
    chunk_obj_ok.confidence = 1.0
    assert should_store_in_vector_store(chunk_obj_ok) is True, (
        "Object chunk with review_required=False should be allowed"
    )

    # --- Object-based chunk: no review_required attribute ---
    chunk_obj_no_attr = MagicMock(spec=[])  # No attributes at all
    assert should_store_in_vector_store(chunk_obj_no_attr) is True, (
        "Object chunk without review_required attr should be allowed (default pass)"
    )


# ===========================================================================
# Test 3: Quality gate -- review_required chunk is blocked
# ===========================================================================


def test_should_block_review_required_chunk():
    """
    A chunk with review_required=True MUST be blocked from the vector store.

    WHAT: should_store_in_vector_store() returns False when the chunk
    has been flagged for human review (review_required=True).

    WHY: chunks flagged by the quality gating pipeline (quality.py) have
    structural or semantic issues (cross-page tables, merged cells,
    footnote references) that would produce incorrect embeddings and
    degrade retrieval precision. Blocking them prevents data corruption.
    """

    # --- Dict-based chunk: review_required=True ---
    dict_chunk_1 = {
        "chunk_id": "ch-bad-001",
        "text": "Table 3.2 (continued) ... [see Note 4]",
        "review_required": True,
        "confidence": 0.45,
    }
    assert should_store_in_vector_store(dict_chunk_1) is False, (
        "Dict chunk with review_required=True should be blocked"
    )

    # --- Dict-based chunk: review_required=True with explicit gating info ---
    dict_chunk_2 = {
        "chunk_id": "ch-bad-002",
        "text": "Cross-page table fragment without headers",
        "review_required": True,
        "confidence": 0.3,
        "gating": "blocked",
    }
    assert should_store_in_vector_store(dict_chunk_2) is False, (
        "Dict chunk with review_required=True and gating=blocked should be blocked"
    )

    # --- Dict-based chunk: review_required=True, low_confidence gating ---
    dict_chunk_3 = {
        "chunk_id": "ch-bad-003",
        "text": "Borderless table with merged cells",
        "review_required": True,
        "confidence": 0.7,
        "gating": "low_confidence",
    }
    assert should_store_in_vector_store(dict_chunk_3) is False, (
        "Dict chunk with review_required=True even at low_confidence should be blocked"
    )

    # --- Object-based chunk: review_required=True ---
    chunk_obj_blocked = MagicMock()
    chunk_obj_blocked.review_required = True
    chunk_obj_blocked.confidence = 0.3
    assert should_store_in_vector_store(chunk_obj_blocked) is False, (
        "Object chunk with review_required=True should be blocked"
    )


# ===========================================================================
# Edge case: empty chunk should be treated as pass (no review flag = no issue)
# ===========================================================================


def test_should_store_edge_cases():
    """
    Edge cases for should_store_in_vector_store() MUST default to safe behavior.

    WHAT: None values, empty dicts, and non-standard chunk shapes all
    default to allowing storage (review_required is absent).

    WHY: the safe default is to allow content through. Only explicitly
    flagged content (review_required=True) should be blocked. Blocking
    by default would require every chunk to have the field set, which
    is fragile.
    """
    # Empty dict: no review_required field → allow
    assert should_store_in_vector_store({}) is True

    # None value: treat as no review flag → allow
    # (though in practice this should never be passed)
    chunk_with_none_review = {"review_required": None}
    assert should_store_in_vector_store(chunk_with_none_review) is True, (
        "Chunk with review_required=None should be treated as pass"
    )

    # String "true" / "false" values: only bool True should block
    # (defensive against serialization artifacts)
    chunk_with_string_true = {"review_required": "true"}
    assert should_store_in_vector_store(chunk_with_string_true) is True, (
        "Chunk with review_required='true' (string) should NOT be blocked "
        "(strict bool check only)"
    )
