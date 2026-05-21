# -*- coding: utf-8 -*-
"""
Unit tests for router.py -- file format detection and backend routing.

WHY: The router decides which backend processes each file. Routing a PDF
to the DOCX pipeline would produce garbage output. Magic bytes sniffing
catches files with wrong extensions -- a .pdf file that is actually a JPEG
would be silently mishandled by extension-only detection.

Test coverage:
  - PDF detection via %PDF- magic bytes
  - DOCX detection via ZIP magic + .docx extension
  - IMAGE detection via PNG magic bytes
  - Unsupported format raises ValueError
  - PDF routing to all 3 valid backends + invalid backend rejection
  - DOCX forced routing to docling regardless of user preference
"""

import tempfile
from pathlib import Path

import pytest

from m1_parser.core.router import (
    detect_format,
    route_backend,
    FileFormat,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _write_temp_file(ext: str, magic_bytes: bytes = b"") -> Path:
    """
    Create a temporary file with the given extension and magic bytes.

    WHY: Each test needs an actual on-disk file for detect_format() to
    open and read. tempfile ensures each test gets a clean, isolated file
    that is automatically cleaned up on interpreter exit.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    if magic_bytes:
        tmp.write(magic_bytes)
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Test 1: PDF detection via magic bytes
# ---------------------------------------------------------------------------


def test_detect_pdf():
    """Files starting with %PDF- MUST be identified as PDF."""
    f = _write_temp_file(".pdf", b"%PDF-1.4\n%some content")
    fmt = detect_format(str(f))
    assert fmt == FileFormat.PDF


# ---------------------------------------------------------------------------
# Test 2: DOCX detection via ZIP magic + extension
# ---------------------------------------------------------------------------


def test_detect_docx():
    """Files with ZIP magic bytes and .docx suffix = DOCX."""
    f = _write_temp_file(".docx", b"PK\x03\x04")
    fmt = detect_format(str(f))
    assert fmt == FileFormat.DOCX


# ---------------------------------------------------------------------------
# Test 3: IMAGE detection via PNG magic bytes
# ---------------------------------------------------------------------------


def test_detect_image_png():
    """Files with PNG magic bytes MUST be identified as IMAGE."""
    f = _write_temp_file(".png", b"\x89PNG\r\n\x1a\n")
    fmt = detect_format(str(f))
    assert fmt == FileFormat.IMAGE


# ---------------------------------------------------------------------------
# Test 4: Unsupported format rejection
# ---------------------------------------------------------------------------


def test_unsupported_format():
    """Unknown magic bytes MUST raise ValueError."""
    f = _write_temp_file(".xyz", b"random binary garbage")
    with pytest.raises(ValueError, match="Unsupported"):
        detect_format(str(f))


# ---------------------------------------------------------------------------
# Test 5: PDF routing -- user-chosen backend
# ---------------------------------------------------------------------------


def test_route_pdf():
    """PDF files MUST route to the user-selected backend."""
    assert route_backend(FileFormat.PDF, "docling") == "docling"
    assert route_backend(FileFormat.PDF, "marker") == "marker"
    assert route_backend(FileFormat.PDF, "mineru") == "mineru"
    with pytest.raises(ValueError, match="Unsupported backend"):
        route_backend(FileFormat.PDF, "unknown_engine")


# ---------------------------------------------------------------------------
# Test 6: DOCX forced routing
# ---------------------------------------------------------------------------


def test_route_docx():
    """DOCX MUST always route to Docling regardless of user preference."""
    assert route_backend(FileFormat.DOCX, "docling") == "docling"
    assert route_backend(FileFormat.DOCX, "marker") == "docling"
