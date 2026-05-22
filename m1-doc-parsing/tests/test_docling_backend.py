# -*- coding: utf-8 -*-
"""
Unit tests for DoclingBackend.

WHY: Docling is the default engine handling all 10+ supported formats.
These tests verify the adapter correctly wraps Docling's
DocumentConverter and passes through configuration options correctly.

When docling is not installed, all tests are skipped via
pytest.importorskip -- this allows CI to run on environments
without the heavy docling dependency.
"""

import tempfile
from pathlib import Path

import pytest

docling = pytest.importorskip("docling", reason="docling is not installed")

from m1_parser.backends.docling_backend import DoclingBackend, ParseResult


# ===========================================================================
# Helpers
# ===========================================================================


def _create_test_markdown(path: Path) -> None:
    """
    Create a simple Markdown file with text content for testing.

    WHAT: writes a short Markdown document containing a heading,
    paragraph, and list. This ensures Docling has actual text content
    to extract during conversion.

    WHY Markdown instead of PDF: creating a real PDF with text requires
    a library like reportlab. Docling natively supports Markdown input,
    so a .md file exercises the full pipeline (format detection ->
    parsing -> Markdown export) with predictable text output.
    """
    content = (
        "# Test Document\n\n"
        "This is a test paragraph for Docling conversion.\n\n"
        "- Item one\n"
        "- Item two\n"
        "- Item three\n"
    )
    path.write_text(content, encoding="utf-8")


# ===========================================================================
# Test 1: Markdown to Markdown conversion (end-to-end pipeline test)
# ===========================================================================


def test_document_to_markdown():
    """
    Converting a document MUST return a ParseResult with non-empty markdown.

    Verifies the full Docling pipeline runs end-to-end:
    format detection -> parsing -> markdown export.

    Uses a Markdown file as input because it guarantees text content
    without needing external PDF-generation libraries.
    """
    with tempfile.NamedTemporaryFile(
        suffix=".md", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write("# Test Doc\n\nHello World.\n")
        md_path = f.name

    try:
        backend = DoclingBackend()
        result = backend.convert(md_path)

        # Verify the result structure
        assert isinstance(result, ParseResult), (
            "convert() must return a ParseResult instance"
        )
        assert result.markdown is not None, (
            "markdown field must not be None"
        )
        assert isinstance(result.markdown, str), (
            "markdown must be a string"
        )
        assert len(result.markdown) > 0, (
            "parsed document markdown must not be empty"
        )
        # Verify JSON export is also populated
        assert result.json_dict is not None, (
            "json_dict must not be None for a successful conversion"
        )
    finally:
        Path(md_path).unlink(missing_ok=True)


# ===========================================================================
# Test 2: OCR engine parameter is stored correctly
# ===========================================================================


def test_ocr_engine_config():
    """
    Passing an ocr_engine parameter MUST be stored on the backend instance.

    This is a pure unit test -- no conversion is performed, so it works
    even if the OCR engine packages are not installed.
    """
    backend = DoclingBackend(ocr_engine="easyocr")
    assert backend.ocr_engine == "easyocr", (
        "ocr_engine must be stored as passed"
    )

    # Verify a different OCR engine is also accepted
    backend2 = DoclingBackend(ocr_engine="rapidocr")
    assert backend2.ocr_engine == "rapidocr"


# ===========================================================================
# Test 3: VLM preset parameter is stored correctly
# ===========================================================================


def test_vlm_preset_config():
    """
    Passing a vlm_preset parameter MUST be stored correctly.

    Verifies that recognized VLM presets are accepted without error.
    This is a pure unit test validating configuration, not execution.
    """
    backend = DoclingBackend(vlm_preset="granite_docling")
    assert backend.vlm_preset == "granite_docling", (
        "vlm_preset must be stored as passed"
    )

    # Verify another known preset is accepted
    backend2 = DoclingBackend(vlm_preset="smoldocling")
    assert backend2.vlm_preset == "smoldocling"


# ===========================================================================
# Test 4: Default parameters
# ===========================================================================


def test_default_config():
    """
    A DoclingBackend with no arguments MUST have sensible defaults.

    Default: easyocr, no VLM, no GPU. These are the safest cross-platform
    defaults that work on any machine (Linux, Windows, macOS).
    """
    backend = DoclingBackend()
    assert backend.ocr_engine == "easyocr"
    assert backend.vlm_preset is None
    assert backend.use_gpu is False


# ===========================================================================
# Test 5: GPU flag is stored correctly
# ===========================================================================


def test_gpu_config():
    """
    The use_gpu flag MUST be stored and retrievable.

    GPU acceleration is optional; verifying the flag is stored means
    the converter pipeline can later inspect it for hardware-aware
    optimization decisions.
    """
    backend = DoclingBackend(use_gpu=True)
    assert backend.use_gpu is True

    backend2 = DoclingBackend(use_gpu=False)
    assert backend2.use_gpu is False
