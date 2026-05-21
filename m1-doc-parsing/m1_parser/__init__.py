# -*- coding: utf-8 -*-
"""
M1 -- Document Parsing Engine.

Converts raw files (PDF, Office, images) into structured Markdown
with offshore-engineering domain metadata, complex table annotations,
and quality confidence scores.

Two operating modes:
  - Standalone: CLI tool + web interface
  - Module: called by M7 admin portal, writes to M2 storage
"""

__version__ = "0.1.0"

# NOTE: converter imports are deferred -- converter.py is not yet implemented.
# Once implemented, uncomment the line below and remove the deferred import block.
from .core.config import detect_hardware, HardwareProfile, M1Config, load_m1_config

__all__ = [
    "detect_hardware", "HardwareProfile",
    "M1Config", "load_m1_config",
    "__version__",
]


def __getattr__(name):
    """Deferred import for symbols not yet implemented (e.g., convert)."""
    if name in ("convert", "convert_batch"):
        from .core.converter import convert, convert_batch  # pragma: no cover
        return locals()[name]
    raise AttributeError(
        f"module 'm1_parser' has no attribute {name!r}"
    )
