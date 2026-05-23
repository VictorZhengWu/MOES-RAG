# -*- coding: utf-8 -*-
"""
Main document converter -- 6-stage parsing pipeline.

WHY: M1's core value is orchestrating the pipeline that turns raw files into
ParsedDocuments with metadata, table annotations, and quality scores.
Converter is the single entry point for all consumers (CLI, Web UI,
M7 admin portal, batch processing).

Pipeline stages:
  1. Format routing (router.py)
  2. Structure parsing (backend adapters)
  3. Metadata extraction (marine_metadata.py)
  4. Table enhancement (table_annotator + table_merger)
  5. Quality gating (quality.py)
  6. Output serialization (serializer + chunker + image_manager)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ===========================================================================
# Input / output types
# ===========================================================================


@dataclass
class ParseOptions:
    """
    User-configurable parse options.

    WHY separate options class rather than function arguments: as more
    config knobs are added (OCR, VLM, quality thresholds, output formats),
    function signatures become unmaintainable. A dataclass with defaults
    keeps the API stable.
    """

    backend: str = "docling"
    ocr_engine: str = "easyocr"
    vlm_preset: str | None = None
    use_gpu: bool = False
    output_dir: str | None = None
    output_formats: list[str] = field(default_factory=lambda: ["md", "json"])


@dataclass
class ParseResult:
    """
    Result of a single document conversion.

    WHY dataclass: simple data carrier with no behavior. Callers can
    inspect the doc_id, check success/error, and consume markdown/json
    without coupling to any specific backend or pipeline stage.
    """

    doc_id: str
    source_path: str
    markdown: str = ""
    html: str = ""
    json_dict: dict | None = None
    page_count: int = 0
    figure_count: int = 0
    table_count: int = 0
    success: bool = False
    error: str | None = None
    output_dir: str | None = None
    metadata: dict | None = None
    parse_time_sec: float = 0.0


# ===========================================================================
# Public API
# ===========================================================================


def convert(source: str, options: ParseOptions | None = None) -> ParseResult:
    """
    Convert a single document through the full 6-stage pipeline.

    This is M1's primary public API. All consumers (CLI, batch, Web UI)
    funnel through this function.

    Currently implements stages 1-2 (route + backend). Stages 3-6
    (metadata, tables, quality, serialization) will be wired in as
    they are built in subsequent tasks.

    Args:
        source: File path or URL to the document.
        options: Parse configuration. Uses defaults if omitted.

    Returns:
        ParseResult with doc_id, markdown, metadata, and status.

    Raises:
        ValueError: If the backend is not supported.
        RuntimeError: If the requested backend's dependencies are missing.
        Various backend-specific exceptions for corrupted files.
    """
    if options is None:
        options = ParseOptions()

    doc_id = uuid.uuid4().hex[:12]
    logger.info(
        "Parsing %s (doc_id=%s, backend=%s)",
        source, doc_id, options.backend,
    )

    # --- Stage 1: Format routing ---
    # WHY: detect_format sniffs magic bytes (not extension), route_backend
    # enforces the rule that Office formats MUST use docling regardless
    # of user preference.
    from .router import detect_format, route_backend

    fmt = detect_format(source)
    backend_name = route_backend(fmt, options.backend)

    # --- Stage 2: Structure parsing ---
    # WHY: each backend produces a consistent ParseResult shape, so the
    # rest of the pipeline is backend-agnostic. Currently only Docling
    # is fully implemented; Marker and MinerU are placeholders.
    from ..backends.docling_backend import (
        DoclingBackend,
        ParseResult as BackendResult,
    )

    if backend_name == "docling":
        backend = DoclingBackend(
            ocr_engine=options.ocr_engine,
            vlm_preset=options.vlm_preset,
            use_gpu=options.use_gpu,
        )
        # Treat empty string as "not set" (web form sends "")
        out_dir = options.output_dir or None
        raw: BackendResult = backend.convert(source, output_dir=out_dir)
    else:
        return ParseResult(
            doc_id=doc_id,
            source_path=source,
            success=False,
            error=f"Backend '{backend_name}' is not yet implemented",
        )

    # Stage 3: metadata extraction (marine_metadata.py)
    import time; t0 = time.time()
    meta: dict[str, object] = {}
    try:
        from m1_parser.enrichments.marine_metadata import extract_marine_metadata as _ext_meta
        mm = _ext_meta(text=raw.markdown, filename=source)
        meta = {
            "classification_society": mm.classification_society,
            "regulation_name": mm.regulation_name,
            "version_year": mm.version_year,
            "chapter_section": mm.chapter_section,
            "language": mm.language,
        }
    except Exception as e:
        logger.warning("Metadata extraction failed: %s", e)

    # Stage 4: table enhancement (not yet wired)
    # Stage 5: quality gating (not yet wired)
    # Stage 6: output serialization
    saved_dir = None
    if out_dir:
        from ..output.serializer import save_markdown, save_json
        save_markdown(raw.markdown, out_dir, doc_id)
        if raw.json_dict:
            save_json(raw.json_dict, out_dir, doc_id)
        saved_dir = str(Path(out_dir) / doc_id)

    return ParseResult(
        doc_id=doc_id,
        source_path=source,
        markdown=raw.markdown,
        html=raw.html,
        json_dict=raw.json_dict,
        page_count=raw.page_count,
        figure_count=raw.figure_count,
        table_count=raw.table_count,
        success=True,
        output_dir=saved_dir,
        metadata=meta,
        parse_time_sec=round(time.time() - t0, 1),
    )


def convert_batch(
    sources: list[str],
    options: ParseOptions | None = None,
    raises_on_error: bool = False,
) -> list[ParseResult]:
    """
    Convert multiple documents, collecting errors rather than crashing.

    WHAT: iterates over a list of file paths, calling convert() for each
    one. Failures are captured as ParseResult objects with success=False
    and error set, so the caller can inspect what worked and what didn't.

    WHY raises_on_error=False by default: a single corrupted file in a
    500-file batch should not kill the entire run. The caller collects
    all results and can report failures at the end.

    Args:
        sources: List of file paths to convert.
        options: Parse configuration shared across all files.
        raises_on_error: If True, re-raises the first exception encountered.

    Returns:
        List of ParseResult objects, one per input source. Failed entries
        have success=False and their error field set.
    """
    results: list[ParseResult] = []

    for source in sources:
        try:
            result = convert(source, options)
        except Exception as exc:
            if raises_on_error:
                raise
            result = ParseResult(
                doc_id="error",
                source_path=source,
                success=False,
                error=str(exc),
            )
        results.append(result)

    return results
