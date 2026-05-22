# -*- coding: utf-8 -*-
"""
Output serialization for M1 Document Parsing Engine.

Exports the serializer and image manager for converting parsed documents
into persistent file-based representations (Markdown, JSON) with proper
directory layouts and metadata sidecars.

All functions are designed as stateless utilities that operate on a
per-document output directory:
  {output_dir}/{doc_id}/
    full.md               -- complete document in Markdown
    full.json             -- complete document as structured JSON
    pages/                -- rendered page images (PNG, 144 DPI)
    figures/              -- extracted figures (original format)
    tables/               -- rendered table screenshots (PNG)
"""

from .serializer import (
    save_markdown,
    save_json,
    CustomJSONEncoder,
)
from .image_manager import (
    get_output_paths,
    save_figure_metadata,
)

__all__ = [
    "save_markdown",
    "save_json",
    "CustomJSONEncoder",
    "get_output_paths",
    "save_figure_metadata",
]
