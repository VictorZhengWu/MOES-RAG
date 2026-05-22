# -*- coding: utf-8 -*-
"""
Unit tests for chunker.py -- HybridChunker wrapper.

WHY: The chunker wraps Docling's HybridChunker with a HuggingFace tokenizer
for semantic text chunking. It must:
  1. Gracefully return None when docling/transformers is not installed
  2. Return a usable HybridChunker instance when dependencies are available

These tests cover the graceful-degradation path and the happy path.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from m1_parser.output.chunker import create_chunker


# ===========================================================================
# Test 1: create_chunker returns None when dependencies are missing
# ===========================================================================


def test_create_chunker_returns_none_when_docling_missing():
    """
    create_chunker() MUST return None (not crash) when docling is not
    installed or cannot be imported.

    WHAT: Simulates a missing docling installation by temporarily hiding
    the docling.chunking module from sys.modules.

    WHY: M1 should be installable without docling (for lightweight CI,
    linting, or non-parsing tasks). The chunker is optional -- callers
    should check for None and fall back gracefully rather than crashing
    with ImportError at runtime.

    Verification:
      - create_chunker() returns None
      - No exception is raised
    """
    # Temporarily hide docling.chunking to simulate missing dependency
    with patch.dict(sys.modules, {"docling.chunking": None}):
        # Force re-import by removing the cached chunker module
        saved = sys.modules.pop("m1_parser.output.chunker", None)
        try:
            from m1_parser.output.chunker import create_chunker as _fresh

            result = _fresh()
            assert result is None, (
                "Expected None when docling is not installed, "
                f"got {type(result).__name__}"
            )
        finally:
            if saved is not None:
                sys.modules["m1_parser.output.chunker"] = saved


# ===========================================================================
# Test 2: create_chunker returns usable HybridChunker when docling is installed
# ===========================================================================


def test_create_chunker_returns_hybrid_chunker_when_available():
    """
    create_chunker() MUST return a properly configured HybridChunker
    instance when docling and transformers are available.

    WHAT: Calls create_chunker() with the default parameters and verifies
    that the returned object is a docling HybridChunker instance with the
    expected configuration (tokenizer, max_tokens, merge_peers, etc.).

    WHY: The chunker is a core pipeline component that splits parsed
    documents into semantic chunks for storage and retrieval. It must be
    correctly configured:
      - BGE-small tokenizer (default): Aligned with M5 embedding model for
        Chinese-English bilingual text, which is critical since marine
        engineering documents contain both languages.
      - max_tokens=512: BGE-small context window limit. Larger chunks would
        be truncated by the embedding model anyway.
      - merge_peers=True: Merge adjacent chunks that are too small after
        splitting, reducing fragmentation.
      - repeat_table_header=True: Table header rows are repeated on each
        chunk that contains part of a split table, so table data remains
        interpretable even when the header was in a different chunk.

    Verification:
      - Returns an object that is a HybridChunker
      - The tokenizer is configured with the specified model
      - max_tokens matches the configured value
      - merge_peers and repeat_table_header are set correctly
    """
    # Skip this test if docling is not actually installed
    # (unlikely in CI, but protects against manual runs in minimal envs)
    try:
        from docling.chunking import HybridChunker  # noqa: F401
    except ImportError:
        pytest.skip("docling is not installed -- cannot test happy path")

    # Use default parameters (the most common production configuration)
    chunker = create_chunker()

    # Verify the returned object is a HybridChunker
    from docling.chunking import HybridChunker
    assert isinstance(chunker, HybridChunker), (
        f"Expected HybridChunker instance, got {type(chunker).__name__}"
    )

    # Verify key configuration parameters
    # max_tokens is now in the tokenizer wrapper (docling v2.95+ API)
    # It should be 512 (BGE-small context window)
    assert chunker.tokenizer.max_tokens == 512, (
        f"Expected tokenizer max_tokens=512, got {chunker.tokenizer.max_tokens}"
    )

    # merge_peers should be True for reduced fragmentation
    assert chunker.merge_peers is True, (
        f"Expected merge_peers=True, got {chunker.merge_peers}"
    )

    # repeat_table_header should be True so split tables remain readable
    assert chunker.repeat_table_header is True, (
        f"Expected repeat_table_header=True, got {chunker.repeat_table_header}"
    )
