# -*- coding: utf-8 -*-
"""
Document serializer -- ParsedDocument to Markdown / JSON / HTML output.

WHAT: Provides stateless functions that write parsed document content to
the canonical per-document output directory structure:
  {output_dir}/{doc_id}/
    full.md    -- complete document in Markdown format
    full.json  -- complete structured data as JSON

WHY: The serializer is the final stage of the M1 parsing pipeline. It
converts in-memory parsed content into persistent files that M2 FileStore
stores and M3 Retrieval indexes. The per-document directory layout (with
doc_id as the directory name) ensures:
  1. Self-contained documents -- copying the directory copies everything
  2. Relative-path image references work naturally
  3. M2 FileStore can store the entire tree atomically
  4. The download API can zip the directory for user downloads

Key design decisions:
  - Both save functions create their parent directory automatically
    (os.makedirs exist_ok=True) so callers don't need orchestration.
  - save_json uses a custom JSONEncoder to handle Docling's non-standard
    types (datetime, Path, Enum, bytes) that default json.dumps rejects.
  - ensure_ascii=False in save_json: CJK characters in Chinese/Japanese/
    Korean documents are stored as-is, not as \\uXXXX escapes. This makes
    the JSON human-readable and saves ~4x space for CJK text.
"""

from __future__ import annotations

import base64
import enum
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ===========================================================================
# Custom JSON encoder
# ===========================================================================


class CustomJSONEncoder(json.JSONEncoder):
    """
    JSON encoder that handles non-JSON-native types from Docling's output.

    WHAT: Extends json.JSONEncoder to serialize datetime, Path, Enum, and
    bytes objects that appear in Docling's export_to_dict() output.

    WHY: Docling's internal document model uses Python-specific types:
      - datetime: document creation/modification timestamps
      - Path: file references and image paths
      - Enum: format types (InputFormat, FileFormat, etc.)
      - bytes: embedded binary data (images, fonts)

    The default json.JSONEncoder raises TypeError for any of these.
    Without this encoder, save_json() would crash on valid Docling output.

    Serialization strategy:
      - datetime -> ISO 8601 string (lossless, human-readable, sortable)
      - Path -> string (POSIX forward slashes for cross-platform compat)
      - Enum -> .value (str enums become strings, int enums become ints)
      - bytes -> base64 string (standard JSON-safe binary encoding)
    """

    def default(self, obj: Any) -> Any:
        # WHY datetime check first: most common non-JSON type in Docling output
        if isinstance(obj, datetime):
            return obj.isoformat()

        # Path objects appear in image references and file metadata
        if isinstance(obj, Path):
            return obj.as_posix()

        # Enum values (e.g., InputFormat.PDF -> "pdf")
        if isinstance(obj, enum.Enum):
            return obj.value

        # bytes: embedded images or binary data from Docling
        # WHY base64: standard, widely-supported binary-to-JSON encoding
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode("ascii")

        # Let the base class raise TypeError for truly unknown types
        return super().default(obj)


# ===========================================================================
# Public API
# ===========================================================================


def save_markdown(content: str, output_dir: str, doc_id: str) -> str:
    """
    Save parsed Markdown content to {output_dir}/{doc_id}/full.md.

    WHAT: Creates the per-document output directory and writes the full
    Markdown content to full.md using UTF-8 encoding. Returns the absolute
    path to the written file.

    WHY: full.md is the canonical human-readable representation of a
    parsed document. It contains all text, tables (as Markdown tables),
    figure references (as Markdown image links with relative paths),
    and heading hierarchy. This is what the Web UI preview renders.

    Args:
        content: The Markdown string to write. May be empty (valid for
            documents with no extractable text, e.g., all-image PDFs).
        output_dir: Root output directory path.
        doc_id: Unique document identifier. Used as the subdirectory name.
            Must be non-empty and contain only safe characters.

    Returns:
        Absolute path to the written full.md file.

    Raises:
        ValueError: If doc_id is empty/whitespace or content is None.
        OSError: If the directory cannot be created (permission denied,
            read-only filesystem, etc.).
    """
    _validate_inputs(doc_id, content)

    doc_dir = os.path.join(output_dir, doc_id)
    os.makedirs(doc_dir, exist_ok=True)

    file_path = os.path.join(doc_dir, "full.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.debug("Markdown saved: %s (%d chars)", file_path, len(content))
    return file_path


def save_json(data: dict[str, Any], output_dir: str, doc_id: str) -> str:
    """
    Save structured document data to {output_dir}/{doc_id}/full.json.

    WHAT: Serializes the data dict (typically Docling's export_to_dict()
    output) as formatted JSON with indent=2 and ensure_ascii=False, then
    writes it to the canonical location.

    WHY: full.json is the machine-readable representation of a parsed
    document. It preserves the complete DoclingDocument structure (pages,
    layout, reading order, tables, figures, text items with bounding boxes)
    that Markdown cannot fully represent. This is critical for:
      - Metadata extraction that needs spatial layout info
      - Table extraction that needs cell-level bounding boxes
      - VLM re-processing of specific page regions
      - Debugging and auditing the parsing pipeline

    Args:
        data: The dict to serialize. Should be JSON-serializable with
            the CustomJSONEncoder handling non-standard types.
        output_dir: Root output directory path.
        doc_id: Unique document identifier. Used as the subdirectory name.

    Returns:
        Absolute path to the written full.json file.

    Raises:
        ValueError: If doc_id is empty/whitespace or data is None/empty.
        TypeError: If data contains a type that even CustomJSONEncoder
            cannot handle (e.g., a custom class without __json__).
        OSError: If the directory cannot be created.
    """
    _validate_inputs(doc_id, data, name="data")

    doc_dir = os.path.join(output_dir, doc_id)
    os.makedirs(doc_dir, exist_ok=True)

    file_path = os.path.join(doc_dir, "full.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
            cls=CustomJSONEncoder,
        )

    logger.debug("JSON saved: %s (%d keys)", file_path, len(data))
    return file_path


# ===========================================================================
# Internal helpers
# ===========================================================================


def _validate_inputs(
    doc_id: str,
    payload: Any,
    *,
    name: str = "content",
) -> None:
    """
    Validate common inputs for both save functions.

    WHAT: Checks that doc_id is a non-empty, non-whitespace string and
    the payload (content or data) is not None.

    WHY: Fail-fast validation prevents writing files to unexpected
    locations (empty doc_id would write directly to output_dir) and
    catches None values from buggy upstream code before they become
    confusing filesystem errors.

    Args:
        doc_id: The document ID to validate.
        payload: The content/data to validate.
        name: Label for the payload in error messages ("content" or "data").

    Raises:
        ValueError: If doc_id is empty/whitespace or payload is None/empty.
    """
    if not doc_id or not doc_id.strip():
        raise ValueError(
            f"doc_id must be a non-empty string, got {doc_id!r}"
        )

    if payload is None:
        raise ValueError(
            f"{name} must not be None for doc_id={doc_id!r}"
        )

    # For dict payloads (save_json), also reject empty dicts
    # WHY: an empty dict is almost certainly a bug in the parsing pipeline
    if isinstance(payload, dict) and len(payload) == 0:
        raise ValueError(
            f"{name} must not be an empty dict for doc_id={doc_id!r}"
        )
