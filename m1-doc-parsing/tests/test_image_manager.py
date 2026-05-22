# -*- coding: utf-8 -*-
"""
Unit tests for image_manager.py -- output directory creation and figure
metadata sidecar writing.

WHY: The image manager enforces the canonical per-document output layout
(pages/figures/tables/) that all downstream consumers (M2 FileStore, Web UI
preview, download API) rely on. Consistency in directory structure and
metadata format is non-negotiable.

Tests cover:
  - get_output_paths: creates all 3 subdirectories, rejects path traversal
  - save_figure_metadata: writes .meta.json sidecar with correct content
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from m1_parser.output.image_manager import (
    get_output_paths,
    save_figure_metadata,
)


# ===========================================================================
# Test 1: get_output_paths creates directories and returns correct paths
# ===========================================================================


def test_get_output_paths_creates_directories(tmp_path: Path):
    """
    get_output_paths() MUST create the document output directory plus
    pages/, figures/, and tables/ subdirectories, and return a dict
    mapping each logical name to its absolute path.

    WHY: Downstream stages (chunker, M2 bridge) look up these paths by
    name to save page images, figure files, and table screenshots. If a
    directory is missing, these stages will crash with confusing errors.
    Pre-creating all directories up front is a fail-fast pattern.
    """
    output_dir = str(tmp_path)
    doc_id = "test_doc_001"

    paths = get_output_paths(output_dir, doc_id)

    # Verify return value structure
    assert isinstance(paths, dict)
    assert set(paths.keys()) == {"doc_dir", "pages", "figures", "tables"}

    # Verify all directories exist on disk
    for key, path_str in paths.items():
        p = Path(path_str)
        assert p.exists(), f"Directory '{key}' not created: {path_str}"
        assert p.is_dir(), f"Path '{key}' is not a directory: {path_str}"

    # Verify correct hierarchical structure
    doc_dir = Path(paths["doc_dir"])
    assert doc_dir == tmp_path / doc_id

    pages_dir = Path(paths["pages"])
    assert pages_dir == doc_dir / "pages"

    figures_dir = Path(paths["figures"])
    assert figures_dir == doc_dir / "figures"

    tables_dir = Path(paths["tables"])
    assert tables_dir == doc_dir / "tables"


# ===========================================================================
# Test 2: get_output_paths is idempotent (existing dirs don't error)
# ===========================================================================


def test_get_output_paths_idempotent(tmp_path: Path):
    """
    get_output_paths() MUST be safe to call multiple times for the same
    doc_id -- existing directories are not an error.

    WHY: The converter pipeline may call get_output_paths during init
    and again during serialization. Idempotency means no special-case
    "already exists" handling in callers.
    """
    output_dir = str(tmp_path)
    doc_id = "idem_test"

    first = get_output_paths(output_dir, doc_id)
    second = get_output_paths(output_dir, doc_id)

    assert first == second


# ===========================================================================
# Test 3: get_output_paths rejects path traversal in doc_id
# ===========================================================================


def test_get_output_paths_rejects_path_traversal():
    """
    get_output_paths() MUST raise ValueError when doc_id contains path
    traversal characters (../, /, \\), preventing writes outside the
    designated output directory.

    WHY: Without this check, a malicious or malformed doc_id could cause
    file writes to arbitrary filesystem locations (e.g., ../../../etc/cron).
    This follows the same _is_safe_key() pattern used by M2 FileStore.
    """
    output_dir = "/tmp/output"

    # Dot-dot-slash traversal attempt
    with pytest.raises(ValueError, match="path traversal"):
        get_output_paths(output_dir, "../etc/cron")

    # Forward slash in doc_id
    with pytest.raises(ValueError, match="path traversal"):
        get_output_paths(output_dir, "sub/dir/doc")

    # Backslash in doc_id (Windows path separator)
    with pytest.raises(ValueError, match="path traversal"):
        get_output_paths(output_dir, "sub\\dir\\doc")

    # Absolute path as doc_id
    with pytest.raises(ValueError, match="path traversal"):
        get_output_paths(output_dir, "/etc/passwd")


# ===========================================================================
# Test 4: get_output_paths rejects empty doc_id
# ===========================================================================


def test_get_output_paths_rejects_empty_doc_id():
    """
    get_output_paths() MUST raise ValueError for empty or whitespace-only
    doc_id to prevent creating output in the root output_dir directly.
    """
    output_dir = "/tmp/output"

    with pytest.raises(ValueError, match="doc_id"):
        get_output_paths(output_dir, "")

    with pytest.raises(ValueError, match="doc_id"):
        get_output_paths(output_dir, "   ")


# ===========================================================================
# Test 5: save_figure_metadata writes .meta.json sidecar
# ===========================================================================


def test_save_figure_metadata_writes_sidecar(tmp_path: Path):
    """
    save_figure_metadata() MUST write a .meta.json sidecar file next to
    the specified figure, containing the full metadata dict as JSON.

    WHY: Metadata sidecars store resolution, format, DPI, original source,
    and VLM-generated descriptions for each figure. Keeping them as
    sidecar files (rather than embedded in the Markdown) makes them
    machine-readable without parsing the Markdown, and keeps the Markdown
    clean and human-readable.

    The naming convention is: <figure_path>.meta.json
    """
    # Create a figure file in the figures directory
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir(parents=True)
    figure_path = figures_dir / "fig_001.png"
    figure_path.write_text("fake png data")  # placeholder

    metadata = {
        "format": "PNG",
        "resolution": "1200x800",
        "dpi": 144,
        "original_format": "JPEG",
        "description": "船体结构示意图 -- Hull structure diagram",
        "page_number": 5,
        "extracted_at": "2026-05-21T14:30:00Z",
        "source": "embedded_in_document",
    }

    sidecar_path = save_figure_metadata(str(figure_path), metadata)

    # Verify sidecar exists at the expected location
    expected_sidecar = str(figure_path) + ".meta.json"
    assert sidecar_path == expected_sidecar

    # Verify content is valid JSON and round-trips correctly
    parsed = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
    assert parsed["format"] == "PNG"
    assert parsed["dpi"] == 144
    assert parsed["page_number"] == 5
    assert parsed["resolution"] == "1200x800"
    assert parsed["description"] == "船体结构示意图 -- Hull structure diagram"

    # Verify CJK characters preserved (ensure_ascii=False)
    raw_text = Path(sidecar_path).read_text(encoding="utf-8")
    assert "船体结构示意图" in raw_text
    assert "\\u8239" not in raw_text


# ===========================================================================
# Test 6: save_figure_metadata creates parent directories if needed
# ===========================================================================


def test_save_figure_metadata_creates_parent_dirs(tmp_path: Path):
    """
    save_figure_metadata() MUST create parent directories for the figure
    file if they don't yet exist.

    WHY: Figures may arrive at the image manager before get_output_paths
    has been called (e.g., during streaming extraction). The metadata
    writer should not assume the directory tree is pre-populated.
    """
    # Path in a directory that doesn't exist yet
    figure_path = tmp_path / "new_doc" / "figures" / "late_fig_001.jpg"
    metadata = {"format": "JPEG", "dpi": 72}

    sidecar_path = save_figure_metadata(str(figure_path), metadata)

    # Verify both the parent dir and sidecar were created
    assert figure_path.parent.exists()
    assert Path(sidecar_path).exists()


# ===========================================================================
# Test 7: save_figure_metadata rejects empty metadata
# ===========================================================================


def test_save_figure_metadata_validates_inputs(tmp_path: Path):
    """
    save_figure_metadata() MUST raise ValueError for empty metadata
    dict or empty figure_path -- fail-fast for bad inputs.
    """
    figure_path = str(tmp_path / "fig_001.png")

    # Empty metadata dict
    with pytest.raises(ValueError, match="metadata"):
        save_figure_metadata(figure_path, {})

    # Empty figure_path
    with pytest.raises(ValueError, match="figure_path"):
        save_figure_metadata("", {"format": "PNG"})

    # None figure_path
    with pytest.raises(ValueError, match="figure_path"):
        save_figure_metadata(None, {"format": "PNG"})  # type: ignore[arg-type]
