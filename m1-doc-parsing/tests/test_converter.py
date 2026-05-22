# -*- coding: utf-8 -*-
"""
Main converter tests -- 6-stage pipeline orchestration.

WHY: Converter is M1's public API. All consumers call convert().
"""

import tempfile
from pathlib import Path

import pytest

from m1_parser.core.converter import convert, convert_batch, ParseOptions


def _create_minimal_pdf(path: Path) -> None:
    """Create a minimal well-formed PDF file for testing."""
    content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )
    path.write_bytes(content)


class TestParseOptions:
    """ParseOptions defaults and validation."""

    def test_defaults(self):
        """Default options must use docling backend and easyocr OCR."""
        opts = ParseOptions()
        assert opts.backend == "docling"
        assert opts.ocr_engine == "easyocr"
        assert opts.output_dir == "./output"

    def test_custom_options(self):
        """Custom options must be preserved as given."""
        opts = ParseOptions(
            backend="marker",
            ocr_engine="tesseract",
            vlm_preset="granite_docling",
            use_gpu=True,
            output_dir="/tmp/out",
            output_formats=["json"],
        )
        assert opts.backend == "marker"
        assert opts.ocr_engine == "tesseract"
        assert opts.vlm_preset == "granite_docling"
        assert opts.use_gpu is True
        assert opts.output_dir == "/tmp/out"
        assert opts.output_formats == ["json"]

    def test_output_formats_default_mutable(self):
        """Each instance gets its own output_formats list (no shared state)."""
        a = ParseOptions()
        b = ParseOptions()
        a.output_formats.append("html")
        assert "html" not in b.output_formats


class TestConvertBatch:
    """Batch conversion error handling."""

    def test_handles_missing_files(self):
        """Batch with raises_on_error=False must not crash on bad files."""
        options = ParseOptions(backend="docling")
        results = convert_batch(
            ["nonexistent1.pdf", "nonexistent2.pdf"],
            options,
            raises_on_error=False,
        )
        assert len(results) == 2
        assert all(not r.success for r in results)
        for r in results:
            assert r.error is not None

    def test_raises_on_error_flag(self):
        """raises_on_error=True must propagate exceptions."""
        options = ParseOptions(backend="docling")
        with pytest.raises(Exception):
            convert_batch(
                ["nonexistent1.pdf"],
                options,
                raises_on_error=True,
            )


class TestConvertPDF:
    """Integration test with actual PDF conversion (requires docling)."""

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("docling"),
        reason="docling is not installed",
    )
    def test_convert_valid_pdf(self):
        """Converting a valid PDF must return a result with doc_id."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            _create_minimal_pdf(Path(f.name))
            fname = f.name

        options = ParseOptions(backend="docling")
        try:
            result = convert(fname, options)
            assert result is not None
            assert result.doc_id is not None
            assert len(result.doc_id) == 12
            assert result.success is True
        finally:
            Path(fname).unlink(missing_ok=True)
