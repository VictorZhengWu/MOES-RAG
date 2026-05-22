# -*- coding: utf-8 -*-
"""
Marker backend adapter -- alternative PDF/image parsing engine.

WHY: Marker (marker-pdf) uses Surya deep learning models for layout
detection and OCR. Some users prefer its output quality for certain
document types (academic papers, scanned books). It serves as a
drop-in alternative to Docling for PDF and image formats.

This adapter wraps Marker behind the same ParseResult interface as
DoclingBackend, so the converter.py pipeline can switch backends
without code changes.

Current status: SKELETON. The marker-pdf package has complex
dependencies (PyTorch, Surya models ~2 GB). Full implementation
will be completed when marker-pdf is integrated into the deploy
pipeline.
"""

from __future__ import annotations

import logging

from .docling_backend import ParseResult

logger = logging.getLogger(__name__)


class MarkerBackend:
    """
    PDF/image parsing via Marker (Surya-based).

    Marker uses the Surya OCR and layout detection models under the hood.
    It is particularly strong at:
      - Academic paper layout (two-column, references, footnotes)
      - Scanned book pages with complex formatting
      - Multi-language text (supports 90+ languages)

    Limitations (compared to Docling):
      - Only supports PDF and image formats (no Office docs)
      - Heavier install footprint (~2 GB model download)
      - Slower on CPU-only machines
    """

    def __init__(self, use_gpu: bool = False):
        """
        Initialize the Marker backend.

        Args:
            use_gpu: Whether to prefer GPU acceleration for Surya models.
        """
        self.use_gpu = use_gpu

    def convert(self, source: str) -> ParseResult:
        """
        Convert a PDF/image to Markdown using Marker. (SKELETON)

        WHAT: would call marker.convert_single_pdf() or marker CLI,
        then wrap the result in a ParseResult. Currently returns an
        empty result with a warning.

        WHY skeleton: marker-pdf has not been integrated into the
        deployment pipeline yet. The skeleton ensures the backend is
        importable and the interface is defined, while the warning
        message guides the user on how to install it.

        Args:
            source: Absolute or relative path to the PDF/image file.

        Returns:
            ParseResult with empty markdown (skeleton).
        """
        logger.warning(
            "Marker backend called but marker-pdf is not installed. "
            "Install it with: pip install marker-pdf"
        )
        return ParseResult(markdown="", page_count=0)
