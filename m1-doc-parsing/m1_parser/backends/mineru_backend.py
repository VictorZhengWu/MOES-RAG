# -*- coding: utf-8 -*-
"""
MinerU PDF parser backend — Chinese-optimized PDF-to-Markdown via magic-pdf.

WHY: MinerU (magic-pdf) by Shanghai AI Lab is the best open-source engine for
     Chinese PDFs — handles LaTeX formulas, nested tables, and mixed CJK/EN
     content. Essential for CCS (China Classification Society) documents.

Install: pip install magic-pdf
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from .docling_backend import ParseResult

logger = logging.getLogger(__name__)


class MinerUBackend:
    """PDF-to-Markdown via MinerU CLI (subprocess isolation)."""

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

        import shutil
        if not shutil.which("magic-pdf"):
            raise RuntimeError("MinerU not found. Install: pip install magic-pdf")

        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="mineru_"))
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = ["magic-pdf", "parse", str(src), "-o", str(out_dir)]
        if max_pages:
            cmd.extend(["--max_pages", str(max_pages)])

        try:
            logger.info("Parsing PDF with MinerU (may take 30-120s for large files)...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.error("MinerU failed: %s", result.stderr[:500])
                return ParseResult(markdown="", page_count=0)
        except subprocess.TimeoutExpired:
            logger.error("MinerU timed out (10 min)")
            return ParseResult(markdown="", page_count=0)
        except FileNotFoundError:
            raise RuntimeError("MinerU not found. Install: pip install magic-pdf")

        # Find generated markdown (MinerU outputs to <out_dir>/<filename>/auto.md)
        md_files = list(out_dir.rglob("*.md"))
        markdown = md_files[0].read_text(encoding="utf-8", errors="replace") if md_files else ""
        return ParseResult(markdown=markdown, page_count=0)
