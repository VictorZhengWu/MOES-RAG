# -*- coding: utf-8 -*-
"""
MinerU PDF parser backend — Chinese-optimized PDF-to-Markdown via magic-pdf.

WHY: MinerU (magic-pdf) by Shanghai AI Lab is the best open-source engine for
     Chinese PDFs — handles LaTeX formulas, nested tables, and mixed CJK/EN
     content. Essential for CCS (China Classification Society) documents.
     Falls back to Docling if CLI not installed.

Install: pip install magic-pdf
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .docling_backend import ParseResult

logger = logging.getLogger(__name__)


class MinerUBackend:
    """PDF-to-Markdown via MinerU CLI (subprocess, graceful fallback)."""

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

        # Graceful fallback if MinerU CLI not installed
        if not shutil.which("magic-pdf"):
            logger.warning("MinerU CLI not found, falling back to Docling")
            from ..backends.docling_backend import DoclingBackend
            return DoclingBackend(use_gpu=self.use_gpu).convert(
                source, output_dir=output_dir, max_pages=max_pages,
            )

        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="mineru_"))
        out_dir.mkdir(parents=True, exist_ok=True)
        self_created_dir = output_dir is None

        try:
            cmd = ["magic-pdf", "parse", str(src), "-o", str(out_dir)]
            if max_pages:
                cmd.extend(["--max_pages", str(max_pages)])

            logger.info("Parsing PDF with MinerU (timeout=%ds)...", timeout)
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            try:
                stdout, _ = process.communicate(timeout=timeout)
                if process.returncode != 0:
                    lines = stdout.strip().split('\n') if stdout else []
                    last = lines[-1] if lines else 'Unknown error'
                    logger.error("MinerU failed (exit %d): %s", process.returncode, last[:500])
                    return ParseResult(markdown="", page_count=0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()  # Reap zombie
                logger.error("MinerU timed out (%ds)", timeout)
                return ParseResult(markdown="", page_count=0)

            # Find generated markdown
            md_files = list(out_dir.rglob("*.md"))
            markdown = md_files[0].read_text(encoding="utf-8", errors="replace") if md_files else ""
            return ParseResult(markdown=markdown, page_count=0)

        except FileNotFoundError:
            raise RuntimeError("MinerU not found. Install: pip install magic-pdf")
        finally:
            if self_created_dir:
                shutil.rmtree(out_dir, ignore_errors=True)
