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
            logger.warning("MinerU CLI not found, falling back to Docling")
            from ..backends.docling_backend import DoclingBackend
            return DoclingBackend(use_gpu=self.use_gpu).convert(source, output_dir=output_dir, max_pages=max_pages)

        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="mineru_"))
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = ["magic-pdf", "parse", str(src), "-o", str(out_dir)]
        if max_pages:
            cmd.extend(["--max_pages", str(max_pages)])

        try:
            logger.info("Parsing PDF with MinerU (may take 30-120s for large files)...")
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            try:
                stdout, _ = process.communicate(timeout=timeout)
                if process.returncode != 0:
                    lines = stdout.strip().split('\n') if stdout else []
                    logger.error("MinerU failed (exit %d): %s", process.returncode, lines[-1][:500] if lines else 'Unknown')
                    return ParseResult(markdown="", page_count=0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                logger.error("MinerU timed out (%ds)", timeout)
                return ParseResult(markdown="", page_count=0)
        except FileNotFoundError:
            raise RuntimeError("MinerU not found. Install: pip install magic-pdf")

        # Find generated markdown (MinerU outputs to <out_dir>/<filename>/auto.md)
        md_files = list(out_dir.rglob("*.md"))
        markdown = md_files[0].read_text(encoding="utf-8", errors="replace") if md_files else ""
        return ParseResult(markdown=markdown, page_count=0)
