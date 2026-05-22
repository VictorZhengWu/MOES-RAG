# -*- coding: utf-8 -*-
"""
Image manager -- output directory layout and figure metadata sidecars.

WHAT: Manages the per-document output directory structure and figure
metadata sidecar files for the M1 parsing pipeline.

The canonical output layout:
  {output_dir}/{doc_id}/
    full.md              -- Markdown from serializer.py
    full.json            -- JSON from serializer.py
    pages/               -- rendered page images (PNG, 144 DPI)
    figures/             -- extracted embedded figures (original format)
    tables/              -- rendered table screenshots (PNG)

Each figure in the figures/ directory may have a .meta.json sidecar:
    figures/fig_001.png          -- the figure image
    figures/fig_001.png.meta.json -- its metadata (resolution, DPI, VLM desc)

WHY: A well-defined directory layout is the contract between the parsing
pipeline and downstream consumers (M2 FileStore, Web UI preview, download
API, M3 Retrieval). Every component that writes files writes to the same
structure; every component that reads files knows exactly where to look.

Key design decisions per D017:
  - Images preserved in original format (no lossy re-encoding)
  - PNG images at 144 DPI for rendered pages/tables
  - Relative paths in Markdown (pages/page_001.png)
  - .meta.json sidecar for machine-readable figure information
  - Path traversal validation (same _is_safe_key() pattern as M2 FileStore)
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ===========================================================================
# Subdirectory names -- single source of truth for the layout
# ===========================================================================

# WHY constants: if we ever need to rename these (unlikely but possible),
# changing them in one place is safer than updating magic strings across
# multiple files.
_SUBDIRS = ("pages", "figures", "tables")

# ===========================================================================
# Path safety pattern -- same approach as M2 FileStore._is_safe_key()
# ===========================================================================

# WHY regex: simple, fast, no imports needed. Matches any character that
# could be used for path traversal or cross-platform path manipulation.
_PATH_TRAVERSAL_RE = re.compile(r"[\\/]")

# Only allow alphanumeric, hyphens, underscores, and dots in doc_id
# WHY restrictive whitelist: doc_id becomes a directory name. Being strict
# prevents surprises across Windows/Linux/macOS filesystem differences.
_SAFE_DOC_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def get_output_paths(output_dir: str, doc_id: str) -> dict[str, str]:
    """
    Create and return the canonical per-document output directory structure.

    WHAT: Creates {output_dir}/{doc_id}/ with pages/, figures/, and tables/
    subdirectories. Returns a dict mapping logical names to absolute paths.

    This function is idempotent -- calling it multiple times for the same
    doc_id is safe (existing directories are not errors).

    WHY: Pre-creating all directories up front is a fail-fast pattern.
    It ensures the filesystem is ready before any pipeline stage tries to
    write files, catching permission errors and disk-full conditions
    early rather than mid-pipeline.

    Args:
        output_dir: Root output directory path.
        doc_id: Unique document identifier. Must be alphanumeric with
            optional hyphens, underscores, and dots. Path traversal
            characters (../, /, \\) are rejected.

    Returns:
        Dict with keys:
          - "doc_dir": {output_dir}/{doc_id}/
          - "pages":   {output_dir}/{doc_id}/pages/
          - "figures": {output_dir}/{doc_id}/figures/
          - "tables":  {output_dir}/{doc_id}/tables/

    Raises:
        ValueError: If doc_id is empty or contains path traversal characters.
        OSError: If directories cannot be created.
    """
    _validate_doc_id(doc_id)

    # Build the document root directory path
    # WHY os.path.join: cross-platform path joining that handles Windows
    # backslashes and Unix forward slashes correctly.
    doc_dir = os.path.join(output_dir, doc_id)

    paths: dict[str, str] = {"doc_dir": doc_dir}

    # Create subdirectories
    for subdir in _SUBDIRS:
        sub_path = os.path.join(doc_dir, subdir)
        os.makedirs(sub_path, exist_ok=True)
        paths[subdir] = sub_path

    logger.debug(
        "Output paths created for doc_id=%s: doc_dir=%s",
        doc_id, doc_dir,
    )
    return paths


def save_figure_metadata(figure_path: str, metadata: dict[str, Any]) -> str:
    """
    Write a .meta.json sidecar file next to the specified figure.

    WHAT: Serializes the metadata dict as JSON and writes it to
    <figure_path>.meta.json. Creates the parent directory if needed.

    The metadata typically includes:
      - format: image format (PNG, JPEG, TIFF, etc.)
      - resolution: pixel dimensions ("WxH")
      - dpi: dots per inch (typically 144)
      - original_format: format in the source document
      - description: VLM-generated natural language description
      - page_number: which page the figure appears on
      - extracted_at: ISO 8601 timestamp of extraction
      - source: "embedded_in_document" or "page_render"

    WHY sidecar files: keeps metadata machine-readable without embedding
    it in Markdown. The M3 Retrieval pipeline can index figure descriptions
    by scanning .meta.json files without parsing Markdown. The Markdown
    stays clean and human-readable with just the image link.

    Args:
        figure_path: Absolute or relative path to the figure file.
            The sidecar will be written at {figure_path}.meta.json.
        metadata: Dict of metadata to write. Must be non-empty.

    Returns:
        Absolute path to the written .meta.json sidecar file.

    Raises:
        ValueError: If figure_path is empty or metadata is empty.
        OSError: If the file cannot be written.
    """
    # Validate inputs
    if not figure_path or not figure_path.strip():
        raise ValueError(
            f"figure_path must be a non-empty string, got {figure_path!r}"
        )

    if not metadata:
        raise ValueError(
            "metadata must be a non-empty dict for "
            f"figure_path={figure_path!r}"
        )

    # Build the sidecar path: <figure_path>.meta.json
    # WHY .meta.json extension: clearly identifies this as a JSON metadata
    # file while keeping the naming convention predictable for glob patterns
    # (e.g., figures/*.meta.json finds all metadata files).
    sidecar_path = figure_path + ".meta.json"

    # Ensure parent directory exists
    # WHY exist_ok: the figure directory may not have been created yet if
    # this is called before get_output_paths() (e.g., during streaming
    # extraction where figures arrive incrementally).
    parent_dir = os.path.dirname(sidecar_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # Write the metadata as indented JSON with CJK characters preserved
    # WHY ensure_ascii=False: figure descriptions in Chinese/Japanese/
    # Korean should be human-readable in the JSON, not \\uXXXX escapes.
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.debug(
        "Figure metadata saved: %s (%d keys)",
        sidecar_path, len(metadata),
    )
    return sidecar_path


# ===========================================================================
# Internal helpers
# ===========================================================================


def _validate_doc_id(doc_id: str) -> None:
    """
    Validate doc_id is safe to use as a directory name.

    WHAT: Checks that doc_id is non-empty and contains no path traversal
    characters (../, /, \\). Rejects whitespace-only strings.

    WHY: doc_id becomes a directory name under output_dir. Without this
    check, a malicious or malformed doc_id could cause writes to arbitrary
    filesystem locations.

    The validation pattern mirrors M2 FileStore's _is_safe_key() logic:
    reject any path separator or traversal attempt.

    Args:
        doc_id: The document ID to validate.

    Raises:
        ValueError: If doc_id contains path traversal characters or is
            empty/whitespace-only.
    """
    if not doc_id or not doc_id.strip():
        raise ValueError(
            f"doc_id must be a non-empty string, got {doc_id!r}"
        )

    # Check for path traversal characters
    # WHY: ../ attacks are the most common, but forward/backslash can also
    # construct arbitrary paths on the target platform.
    if ".." in doc_id or _PATH_TRAVERSAL_RE.search(doc_id):
        raise ValueError(
            f"doc_id contains path traversal characters: {doc_id!r}. "
            f"doc_id must be a simple name without directory separators."
        )

    # Additional safety: restrict to alphanumeric + safe punctuation
    # WHY: being strict about what we accept as a directory name prevents
    # surprises from special characters across different filesystems.
    if not _SAFE_DOC_ID_RE.match(doc_id):
        raise ValueError(
            f"doc_id contains unsafe characters: {doc_id!r}. "
            f"Only alphanumeric characters, hyphens, underscores, and "
            f"dots are allowed."
        )
