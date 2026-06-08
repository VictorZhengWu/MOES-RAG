# -*- coding: utf-8 -*-
"""
Marker PDF parser backend — high-quality PDF-to-Markdown via Surya models.

WHY: Marker excels at academic papers, multi-column layouts, and 90+ language
     OCR. Subprocess isolation prevents PyTorch version conflicts with Docling.

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
    """PDF-to-Markdown via Marker CLI (subprocess isolation)."""

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

        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="marker_"))
        out_dir.mkdir(parents=True, exist_ok=True)

        if not shutil.which("marker"):
            raise RuntimeError("Marker CLI not found. Install: pip install marker-pdf")

        cmd = ["marker", str(src), str(out_dir), "--output_format", "markdown"]
        if max_pages:
            cmd.extend(["--max_pages", str(max_pages)])

        logger.info("Parsing PDF with Marker (may take 30-120s for large files)...")
        try:
            # Use Popen for real-time progress detection
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            try:
                stdout, _ = process.communicate(timeout=timeout)
                if process.returncode != 0:
                    # Extract last meaningful line for error reporting
                    lines = stdout.strip().split('\n') if stdout else []
                    last_line = lines[-1] if lines else 'Unknown error'
                    logger.error("Marker failed (exit %d): %s", process.returncode, last_line[:500])
                    return ParseResult(markdown="", page_count=0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                logger.error("Marker timed out (%ds)", timeout)
                return ParseResult(markdown="", page_count=0)
        except FileNotFoundError:
            raise RuntimeError("Marker CLI not found. Install: pip install marker-pdf")

        # Find generated markdown
        md_files = list(out_dir.rglob("*.md"))
        markdown = md_files[0].read_text(encoding="utf-8", errors="replace") if md_files else ""
        return ParseResult(markdown=markdown, page_count=0)
