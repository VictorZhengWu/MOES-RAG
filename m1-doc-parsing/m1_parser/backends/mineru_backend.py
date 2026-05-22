# -*- coding: utf-8 -*-
"""
MinerU backend adapter -- PDF parsing engine optimized for Chinese.

WHY: MinerU (magic-pdf), developed by Shanghai AI Lab (OpenDataLab),
is the best open-source solution for parsing Chinese-language PDFs
with complex features:
  - Mathematical formulas (LaTeX rendering)
  - Complex nested tables
  - Multi-column Chinese academic layouts
  - Mixed Chinese/English content

For the Marine & Offshore domain, MinerU is particularly valuable
because Chinese classification society standards (CCS, IACS Chinese
editions) frequently contain dense tables and formulas that general-
purpose engines may struggle with.

This adapter wraps MinerU behind the same ParseResult interface as
DoclingBackend, so the converter.py pipeline can switch backends
without code changes.

Current status: SKELETON. The magic-pdf package requires specific
environment setup (Python 3.10, system libraries). Full implementation
will be completed when magic-pdf is integrated into the deploy pipeline.
"""

from __future__ import annotations

import logging

from .docling_backend import ParseResult

logger = logging.getLogger(__name__)


class MinerUBackend:
    """
    PDF parsing via MinerU (magic-pdf).

    MinerU excels at Chinese-language technical documents:
      - Formula parsing with LaTeX output
      - Table structure recognition with merged-cell handling
      - Reading order recovery for multi-column layouts
      - OCR fallback for scanned pages

    Limitations:
      - Only supports PDF format (no images or Office docs)
      - Requires specific Python version (3.10 recommended)
      - Heavier system dependencies (libreoffice, poppler, etc.)
    """

    def __init__(self, use_gpu: bool = False):
        """
        Initialize the MinerU backend.

        Args:
            use_gpu: Whether to use GPU acceleration for the OCR
                and layout detection models.
        """
        self.use_gpu = use_gpu

    def convert(self, source: str) -> ParseResult:
        """
        Convert a PDF to Markdown using MinerU. (SKELETON)

        WHAT: would call magic-pdf CLI or Python API, parse the output
        directory for markdown files, and wrap the result. Currently
        returns an empty result with a warning.

        WHY skeleton: magic-pdf has specific environment requirements
        that have not yet been integrated into the deployment pipeline.
        The skeleton ensures the backend is importable and the interface
        is consistent with other backends.

        Args:
            source: Absolute or relative path to the PDF file.

        Returns:
            ParseResult with empty markdown (skeleton).
        """
        logger.warning(
            "MinerU backend called but magic-pdf is not installed. "
            "Install it with: pip install magic-pdf"
        )
        return ParseResult(markdown="", page_count=0)
