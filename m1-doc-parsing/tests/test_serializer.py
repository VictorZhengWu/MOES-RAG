# -*- coding: utf-8 -*-
"""
Unit tests for serializer.py -- Markdown and JSON output writers.

WHY: The serializer is the final stage of the M1 parsing pipeline before
content reaches storage. It MUST produce correct, well-formed output files
in the canonical directory layout that M2 FileStore and M3 Retrieval expect.

Tests cover:
  - save_markdown: creates {output_dir}/{doc_id}/full.md with UTF-8 content
  - save_json: creates {output_dir}/{doc_id}/full.json with non-ASCII support
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from m1_parser.output.serializer import (
    save_markdown,
    save_json,
    CustomJSONEncoder,
)


# ===========================================================================
# Test 1: save_markdown creates full.md with correct content
# ===========================================================================


def test_save_markdown_creates_file(tmp_path: Path):
    """
    save_markdown() MUST create {output_dir}/{doc_id}/full.md with the
    provided content, encoded as UTF-8, and return the absolute file path.

    WHY: The canonical directory layout ({doc_id}/full.md) is what M2
    FileStore and the download API expect. Deviating from this layout
    breaks downstream consumers.
    """
    output_dir = str(tmp_path)
    doc_id = "test_doc_001"
    content = "# Test Document\n\nThis is a **test**.\n\n![figure](../figures/fig_001.png)\n"

    result_path = save_markdown(content, output_dir, doc_id)

    # Verify return value is the expected file path
    expected = tmp_path / doc_id / "full.md"
    assert result_path == str(expected)

    # Verify file exists and content matches
    assert expected.exists()
    read_back = expected.read_text(encoding="utf-8")
    assert read_back == content

    # Verify non-ASCII content is preserved
    content_cjk = "# 测试文档\n\n包含 **中文** 内容。\n"
    result_cjk = save_markdown(content_cjk, output_dir, doc_id)
    read_cjk = Path(result_cjk).read_text(encoding="utf-8")
    assert read_cjk == content_cjk


# ===========================================================================
# Test 2: save_json creates full.json with correct serialization
# ===========================================================================


def test_save_json_creates_file(tmp_path: Path):
    """
    save_json() MUST create {output_dir}/{doc_id}/full.json with valid
    JSON, using indent=2 and ensure_ascii=False for CJK readability.

    WHY: Docling's export_to_dict() produces complex nested structures
    with datetime, Enum, and bytes values. The JSON encoder must handle
    these gracefully without crashing, while preserving human-readable
    CJK characters (ensure_ascii=False).
    """
    output_dir = str(tmp_path)
    doc_id = "test_doc_002"
    data = {
        "doc_id": doc_id,
        "title": "测试文档",  # CJK test: must not be \uXXXX escaped
        "pages": [
            {"page_num": 1, "text": "第一节 总则"},
            {"page_num": 2, "text": "第二章 船体结构"},
        ],
        "metadata": {
            "author": "CCS",
            "year": 2023,
            "figures": 5,
        },
    }

    result_path = save_json(data, output_dir, doc_id)

    # Verify return value
    expected = tmp_path / doc_id / "full.json"
    assert result_path == str(expected)

    # Verify file exists and is valid JSON
    assert expected.exists()
    raw_text = expected.read_text(encoding="utf-8")
    parsed = json.loads(raw_text)

    # Verify round-trip data integrity
    assert parsed["doc_id"] == doc_id
    assert parsed["title"] == "测试文档"
    assert len(parsed["pages"]) == 2
    assert parsed["metadata"]["author"] == "CCS"

    # Verify ensure_ascii=False: CJK characters preserved as-is
    assert "测试文档" in raw_text
    assert "\\u6d4b" not in raw_text  # ensure_ascii=False means NO unicode escapes

    # Verify indent=2 formatting
    lines = raw_text.splitlines()
    assert any(line.startswith("  ") for line in lines)


# ===========================================================================
# Test 3: CustomJSONEncoder handles special types
# ===========================================================================


def test_custom_json_encoder_special_types(tmp_path: Path):
    """
    CustomJSONEncoder MUST serialize datetime, Path, Enum, and bytes
    to JSON-safe representations without raising TypeError.

    WHY: Docling's export_to_dict() can include datetime objects (document
    timestamps), Path objects (file references), Enum values (format types),
    and bytes (embedded binary data). The default json.JSONEncoder does not
    handle any of these -- a custom encoder is required to prevent crashes.
    """
    import enum
    from datetime import datetime, timezone

    class TestEnum(str, enum.Enum):
        FOO = "foo"
        BAR = "bar"

    output_dir = str(tmp_path)
    doc_id = "enc_test"

    data = {
        "datetime_val": datetime(2026, 5, 21, 14, 30, 0, tzinfo=timezone.utc),
        "path_val": Path("/some/path/to/file.pdf"),
        "enum_val": TestEnum.FOO,
        "bytes_val": b"hello world \xe4\xb8\xad\xe6\x96\x87",
    }

    # This MUST NOT raise TypeError
    result_path = save_json(data, output_dir, doc_id)

    # Verify file was created and is valid JSON
    raw_text = Path(result_path).read_text(encoding="utf-8")
    parsed = json.loads(raw_text)

    # Datetime: ISO 8601 string
    assert isinstance(parsed["datetime_val"], str)
    assert "2026-05-21" in parsed["datetime_val"]

    # Path: string representation
    assert isinstance(parsed["path_val"], str)
    assert "file.pdf" in parsed["path_val"]

    # Enum: string value
    assert parsed["enum_val"] == "foo"

    # Bytes: base64-encoded string
    assert isinstance(parsed["bytes_val"], str)
    import base64
    decoded = base64.b64decode(parsed["bytes_val"])
    assert decoded == b"hello world \xe4\xb8\xad\xe6\x96\x87"


# ===========================================================================
# Test 4: save_markdown validates inputs
# ===========================================================================


def test_save_markdown_rejects_invalid_inputs(tmp_path: Path):
    """
    save_markdown() and save_json() MUST raise ValueError for invalid
    inputs (empty doc_id, None content), failing fast before touching
    the filesystem.

    WHY: Silent failures here would produce files in unexpected locations
    or with corrupted content. Fail-fast validation prevents downstream
    confusion (e.g., a missing full.md that M2 can't store).
    """
    output_dir = str(tmp_path)

    # Empty doc_id
    with pytest.raises(ValueError, match="doc_id"):
        save_markdown("content", output_dir, "")

    # Doc_id with only whitespace
    with pytest.raises(ValueError, match="doc_id"):
        save_markdown("content", output_dir, "   ")

    # None content
    with pytest.raises(ValueError, match="content"):
        save_markdown(None, output_dir, "doc123")  # type: ignore[arg-type]

    # Empty doc_id for save_json
    with pytest.raises(ValueError, match="doc_id"):
        save_json({"key": "val"}, output_dir, "")


# ===========================================================================
# Test 5: save_markdown handles empty content
# ===========================================================================


def test_save_markdown_handles_empty_content(tmp_path: Path):
    """
    save_markdown() MUST accept empty string content (valid edge case for
    documents that produced no extractable text).

    WHY: Some input files (e.g., all-image PDFs, encrypted documents)
    may yield empty markdown after parsing. The serializer should still
    create the file rather than crashing -- the absence of content is
    valid metadata that downstream stages can check.
    """
    output_dir = str(tmp_path)
    doc_id = "empty_doc"

    result_path = save_markdown("", output_dir, doc_id)
    expected = tmp_path / doc_id / "full.md"

    assert expected.exists()
    assert expected.read_text(encoding="utf-8") == ""
