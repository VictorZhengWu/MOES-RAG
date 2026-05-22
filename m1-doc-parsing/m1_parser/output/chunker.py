# -*- coding: utf-8 -*-
"""
HybridChunker wrapper -- Docling HybridChunker with HuggingFace Tokenizer.

WHAT: Provides create_chunker(), a factory function that creates a
configured Docling HybridChunker instance with a HuggingFace tokenizer
aligned to the embedding model used by M5 (QA Engine).

WHY: Semantic chunking is the bridge between M1 (Document Parsing) and
M3 (Retrieval). The chunker splits parsed Markdown into token-aware
segments that fit within the embedding model's context window. Key
design decisions:

1. HybridChunker (not raw text splitting):
   - Docling's HybridChunker uses both structural (heading hierarchy)
     and token-based boundaries, producing chunks that respect document
     structure while staying within token limits.
   - Raw text splitters (e.g., RecursiveCharacterTextSplitter) lose
     the heading/table/figure structure that Docling preserves.

2. BGE-small tokenizer (default):
   - The BGE family (bge-small-en-v1.5, BGE-M3) is the default embedding
     model for this system. Using the same tokenizer ensures chunks are
     split at the exact boundaries the embedding model will use.
   - For Chinese-English bilingual text (common in marine engineering
     documents), BGE tokenizers handle CJK characters correctly.

3. max_tokens=512 (default):
   - BGE-small context window is 512 tokens. Larger chunks would be
     truncated by the embedding model.
   - 512 tokens is ~300-400 words, which is a good balance between
     semantic richness and retrieval precision for technical documents.

4. merge_peers=True:
   - After splitting, small residual chunks (orphaned sentences,
     single-cell table fragments) are merged into their neighbors.
     This prevents fragmentation and ensures each chunk carries enough
     context to be independently retrievable.

5. repeat_table_header=True:
   - When a table spans multiple chunks, the header row is repeated in
     each chunk. Without this, a chunk showing cell data without context
     (e.g., "15.2 | 3.4 | Pass") is meaningless.
   - This is especially critical for classification society rule tables
     where column headers define the meaning of every cell.

Graceful degradation:
  - If docling is not installed (e.g., CI environments, linting),
    create_chunker() returns None instead of raising ImportError.
    Callers should check for None and skip chunking operations.
  - This follows the M1 design principle of optional backends:
    the core parsing pipeline should work without optional components.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docling.chunking import HybridChunker

logger = logging.getLogger(__name__)


def create_chunker(
    tokenizer_model_id: str = "BAAI/bge-small-en-v1.5",
    max_tokens: int = 512,
    merge_peers: bool = True,
    repeat_table_header: bool = True,
) -> "HybridChunker | None":
    """
    Create a configured Docling HybridChunker instance.

    WHAT: Factory function that instantiates a HybridChunker with a
    HuggingFace tokenizer aligned to the configured embedding model.
    Returns None if the required dependencies are not available.

    WHY: Centralizing chunker creation here (rather than letting callers
    construct HybridChunker directly) ensures:
      1. Consistent tokenizer-embedding alignment across the codebase
      2. Graceful degradation when docling is not installed
      3. A single place to update default parameters when switching
         embedding models (e.g., from BGE-small to BGE-M3)

    Args:
        tokenizer_model_id: HuggingFace model ID for the tokenizer.
            Default is "BAAI/bge-small-en-v1.5" -- the BGE-small model
            that balances performance and resource usage. For production
            with Chinese-heavy content, use "BAAI/bge-m3".
        max_tokens: Maximum tokens per chunk. Default 512 matches the
            BGE-small context window.
        merge_peers: Whether to merge adjacent small chunks after splitting.
            Default True -- reduces fragmentation.
        repeat_table_header: Whether to repeat table header rows on each
            chunk of a split table. Default True -- preserves table
            readability.

    Returns:
        A configured HybridChunker instance, or None if docling is not
        installed or the import fails.
    """
    # --- Step 1: Verify docling is available ---
    # WHY: M1 should be importable even without docling. The chunker is
    # an optional component -- callers handle None gracefully.
    try:
        from docling.chunking import HybridChunker  # noqa: F811
    except ImportError:
        logger.warning(
            "docling is not installed. create_chunker() returns None. "
            "Install with: pip install docling"
        )
        return None

    # --- Step 2: Verify HuggingFace transformers is available ---
    # WHY: We need AutoTokenizer to load the tokenizer model, and
    # HuggingFaceTokenizer from docling_core to wrap it. Both
    # transformers and docling-core[chunking] are required.
    # NOTE: We catch Exception (not just ImportError) because
    # transformers' module-level code can raise ValueError when
    # torch.__spec__ is unset (a known Python 3.12+ edge case where
    # importlib.util.find_spec fails for torch after certain
    # sys.modules manipulations in test environments).
    try:
        from transformers import AutoTokenizer  # noqa: F401
    except Exception:
        logger.warning(
            "transformers failed to import. "
            "create_chunker() returns None. "
            "Install with: pip install transformers"
        )
        return None

    # --- Step 3: Create the HuggingFace tokenizer wrapper ---
    # WHY: Docling v2.95+ requires tokenizers to be passed as wrapper
    # objects (HuggingFaceTokenizer or OpenAITokenizer), not as raw
    # model ID strings. The wrapper encapsulates both the tokenizer
    # instance and the max_tokens limit, which the chunker uses to
    # determine chunk boundaries.
    # We use AutoTokenizer.from_pretrained() which handles model
    # downloading, caching, and configuration automatically.
    try:
        from docling_core.transforms.chunker.tokenizer.huggingface import (
            HuggingFaceTokenizer,
        )
        from transformers import AutoTokenizer  # noqa: F811

        hf_tokenizer = AutoTokenizer.from_pretrained(tokenizer_model_id)
        tokenizer_wrapper = HuggingFaceTokenizer(
            tokenizer=hf_tokenizer,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        logger.warning(
            "Failed to load tokenizer model '%s': %s. "
            "create_chunker() returns None.",
            tokenizer_model_id,
            exc,
        )
        return None

    # --- Step 4: Build and return the chunker ---
    # WHY: HybridChunker uses the HuggingFaceTokenizer wrapper for all
    # token-aware operations (counting tokens, finding split points).
    # merge_peers reduces fragmentation; repeat_table_header ensures
    # split tables stay interpretable.
    logger.info(
        "Creating HybridChunker: tokenizer=%s, max_tokens=%d, "
        "merge_peers=%s, repeat_table_header=%s",
        tokenizer_model_id,
        max_tokens,
        merge_peers,
        repeat_table_header,
    )

    chunker = HybridChunker(
        tokenizer=tokenizer_wrapper,
        merge_peers=merge_peers,
        repeat_table_header=repeat_table_header,
    )

    logger.debug(
        "HybridChunker created successfully: %s",
        chunker,
    )
    return chunker
