# -*- coding: utf-8 -*-
"""
Marker PDF parser backend — high-quality PDF-to-Markdown via Surya models.

WHY: Marker excels at academic papers, multi-column layouts, and 90+ language
     OCR. Subprocess isolation prevents PyTorch version conflicts with Docling.
     Falls back to Docling if CLI not installed.

Install: pip install marker-pdf
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .docling_backend import ParseResult

logger = logging.getLogger(__name__)


class MarkerBackend:
    """PDF-to-Markdown via Marker CLI (subprocess, graceful fallback)."""

    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu

    def convert(
        self, source: str, output_dir: str | None = None,
        max_pages: int | None = None,
        picture_description: bool = False,
        export_tables: bool = False,
        timeout: int = 120,
    ) -> ParseResult:
        src = Path(source)
        if not src.exists():
            return ParseResult(markdown="", page_count=0)

        # Graceful fallback if Marker CLI not installed
        if not shutil.which("marker"):
            logger.warning("Marker CLI not found, falling back to Docling")
            try:
                from ..backends.docling_backend import DoclingBackend
                return DoclingBackend(use_gpu=self.use_gpu).convert(
                    source, output_dir=output_dir, max_pages=max_pages,
                )
            except Exception as e:
                logger.error("Docling fallback also failed: %s", e)
                return ParseResult(markdown="", page_count=0)

        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="marker_"))
        out_dir.mkdir(parents=True, exist_ok=True)
        self_created_dir = output_dir is None  # Track for cleanup

        try:
            cmd = ["marker", str(src), str(out_dir), "--output_format", "markdown"]
            if max_pages:
                cmd.extend(["--max_pages", str(max_pages)])

            logger.info("Parsing PDF with Marker (timeout=%ds)...", timeout)
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            try:
                stdout, _ = process.communicate(timeout=timeout)
                if process.returncode != 0:
                    lines = stdout.strip().split('\n') if stdout else []
                    last = lines[-1] if lines else 'Unknown error'
                    logger.error("Marker failed (exit %d): %s", process.returncode, last[:500])
                    return ParseResult(markdown="", page_count=0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()  # Reap the zombie
                logger.error("Marker timed out (%ds)", timeout)
                return ParseResult(markdown="", page_count=0)

            # Find generated markdown
            md_files = list(out_dir.rglob("*.md"))
            markdown = md_files[0].read_text(encoding="utf-8", errors="replace") if md_files else ""
            return ParseResult(markdown=markdown, page_count=0)

        except FileNotFoundError:
            raise RuntimeError("Marker CLI not found. Install: pip install marker-pdf")
        finally:
            if self_created_dir:
                shutil.rmtree(out_dir, ignore_errors=True)
