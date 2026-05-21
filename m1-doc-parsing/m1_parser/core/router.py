# -*- coding: utf-8 -*-
"""
File format detection and backend routing.

WHY: Different file formats need different parsers. Magic bytes sniffing
is more reliable than extension-only checks -- a file named .pdf could
actually be a JPEG. The router also knows which backends can handle
which formats (e.g., Marker only supports PDF/image).

Detection priority: magic bytes (first 8 bytes) -> extension fallback.

Routing rules:
  - PDF / IMAGE -> user-selected backend (docling / marker / mineru)
  - DOCX / XLSX / PPTX / HTML / CSV / Markdown -> forced docling
    (Marker and MinerU only support PDF/image; Docling handles Office
    formats natively)
  - Anything unsupported -> clear ValueError with supported list

Key decisions:
  - Enum-based FileFormat instead of raw strings: IDE autocomplete and
    mypy type narrowing
  - ZIP magic (PK\x03\x04) uses extension lookup because DOCX, XLSX,
    and PPTX all share the same ZIP container format
  - route_backend() returns strings not enums: easier integration with
    existing config.py (SUPPORTED_BACKENDS is a list[str])
"""

from __future__ import annotations

import enum
from pathlib import Path


class FileFormat(str, enum.Enum):
    """
    Supported input file formats.

    WHY str mixin: can be used directly in f-strings and JSON
    serialization without calling .value. Also simplifies comparison
    with raw strings from user input.
    """
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    HTML = "html"
    IMAGE = "image"
    CSV = "csv"
    MARKDOWN = "markdown"


# ---------------------------------------------------------------------------
# Magic bytes signatures -- ordered by specificity
# WHY list of tuples: easy to iterate in priority order. None format
# means "defer to extension" (used for ZIP-based Office formats).
# ---------------------------------------------------------------------------

_MAGIC_SIGNATURES: list[tuple[bytes, FileFormat | None]] = [
    (b"%PDF-", FileFormat.PDF),
    (b"\x89PNG", FileFormat.IMAGE),
    (b"\xff\xd8\xff", FileFormat.IMAGE),          # JPEG
    (b"II*\x00", FileFormat.IMAGE),               # TIFF (little-endian)
    (b"MM\x00*", FileFormat.IMAGE),               # TIFF (big-endian)
    (b"BM", FileFormat.IMAGE),                    # BMP
    (b"PK\x03\x04", None),                        # ZIP-based: DOCX/XLSX/PPTX
    (b"<!DOCTYP", FileFormat.HTML),
    (b"<html", FileFormat.HTML),
]

# Backends available for PDF/image formats
_PDF_IMAGE_BACKENDS = {"docling", "marker", "mineru"}

# Formats that MUST use Docling (Marker/MinerU don't support them)
_DOCLING_ONLY_FORMATS: set[FileFormat] = {
    FileFormat.DOCX,
    FileFormat.XLSX,
    FileFormat.PPTX,
    FileFormat.HTML,
    FileFormat.CSV,
    FileFormat.MARKDOWN,
}


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


def detect_format(file_path: str) -> FileFormat:
    """
    Detect file format via magic bytes, falling back to extension.

    Reads the first 8 bytes of the file and compares against known
    magic signatures. If the signature maps to a ZIP-based container
    (e.g., DOCX/XLSX/PPTX), the file extension is used for the final
    determination.

    Args:
        file_path: Absolute or relative path to the file to inspect.

    Returns:
        FileFormat enum value.

    Raises:
        ValueError: If neither magic bytes nor extension match a known
            format. The error message includes the list of supported
            extensions.
    """
    path = Path(file_path)

    with open(file_path, "rb") as f:
        header = f.read(8)

    for signature, fmt in _MAGIC_SIGNATURES:
        if header.startswith(signature):
            if fmt is None:
                # ZIP container -- use extension to disambiguate
                # DOCX/XLSX/PPTX (all share PK\x03\x04 magic)
                return _format_from_extension(path.suffix.lower())
            return fmt

    # No magic match -- try extension as last resort
    return _format_from_extension(path.suffix.lower())


# ---------------------------------------------------------------------------
# Backend routing
# ---------------------------------------------------------------------------


def route_backend(fmt: FileFormat, user_choice: str) -> str:
    """
    Select the correct backend for a given file format.

    Routing rules:
      - PDF / IMAGE: respects user's choice among docling/marker/mineru
      - All other formats: forced to docling (Marker and MinerU only
        handle PDF/image input)

    Args:
        fmt: The detected FileFormat.
        user_choice: The user's preferred backend name.

    Returns:
        Backend name string (one of "docling", "marker", "mineru").

    Raises:
        ValueError: If the backend is invalid for this format (e.g.,
            choosing "marker" for DOCX, or an unknown backend for PDF).
    """
    # Docling-only formats ignore user preference entirely
    if fmt in _DOCLING_ONLY_FORMATS:
        return "docling"

    # PDF / IMAGE: validate user's choice against the supported set
    if fmt in (FileFormat.PDF, FileFormat.IMAGE):
        if user_choice in _PDF_IMAGE_BACKENDS:
            return user_choice
        raise ValueError(
            f"Unsupported backend '{user_choice}' for {fmt.value}. "
            f"Supported: {', '.join(sorted(_PDF_IMAGE_BACKENDS))}"
        )

    # Unknown/unsupported format (shouldn't reach here if detect_format
    # validates first, but defensive programming)
    raise ValueError(f"Unsupported file format: {fmt.value}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_from_extension(suffix: str) -> FileFormat:
    """
    Map a file extension to its FileFormat.

    WHY separate function: reused in two code paths -- the ZIP-container
    disambiguation branch and the final magic-miss fallback. Having it
    in one place ensures the extension-to-format mapping stays consistent.

    Args:
        suffix: Lowercase file extension including the dot (e.g., ".pdf").

    Returns:
        FileFormat enum value.

    Raises:
        ValueError: If the suffix is not in the supported list.
    """
    # WHY dict: O(1) lookup, easy to extend with new formats.
    ext_map: dict[str, FileFormat] = {
        ".pdf": FileFormat.PDF,
        ".docx": FileFormat.DOCX,
        ".xlsx": FileFormat.XLSX,
        ".pptx": FileFormat.PPTX,
        ".html": FileFormat.HTML,
        ".htm": FileFormat.HTML,
        ".png": FileFormat.IMAGE,
        ".jpg": FileFormat.IMAGE,
        ".jpeg": FileFormat.IMAGE,
        ".tiff": FileFormat.IMAGE,
        ".tif": FileFormat.IMAGE,
        ".bmp": FileFormat.IMAGE,
        ".csv": FileFormat.CSV,
        ".md": FileFormat.MARKDOWN,
    }
    fmt = ext_map.get(suffix)
    if fmt is None:
        raise ValueError(
            f"Unsupported file extension: {suffix}. "
            f"Supported: {', '.join(sorted(ext_map.keys()))}"
        )
    return fmt
