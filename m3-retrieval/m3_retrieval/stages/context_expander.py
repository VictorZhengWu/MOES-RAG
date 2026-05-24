# -*- coding: utf-8 -*-
"""
Context Expansion and Deduplication stage for the M3 Retrieval Pipeline.

WHAT: Two post-processing functions applied after fusion and reranking:
  1. expand_context(): (placeholder) fetches neighboring chunks for each
     retrieved chunk to provide richer context to the LLM.
  2. deduplicate_chunks(): removes near-duplicate adjacent chunks using
     Jaccard similarity, keeping the first occurrence of similar content.

WHY: After fusion and reranking, the retrieved chunks may contain:
  - Redundancy: nearly identical chunks from overlapping document sections
    or the same chunk returned by multiple retrievers. Deduplication
    eliminates this waste of the LLM context window.
  - Missing context: a single chunk may not contain the full reasoning
    chain. Context expansion fetches adjacent chunks to provide the
    broader document context. (Currently a placeholder; requires
    StorageManager integration for chunk adjacency queries.)

Key design decisions:
  - _jaccard() is a module-level helper (not a method) for testability.
  - deduplicate_chunks() uses single-pass neighbor comparison (O(n)),
    comparing each chunk only to the last kept chunk. This is fast and
    sufficient for sorted retrieval lists where near-duplicates are
    adjacent.
  - The dedup threshold of 0.85 is a practical heuristic. Values above
    0.9 risk keeping near-duplicates; values below 0.8 risk removing
    genuinely related but distinct content.
  - expand_context() is a passthrough placeholder. Full implementation
    requires the StorageManager to provide a get_adjacent_chunks() API.
"""

from __future__ import annotations

from contracts.retrieval import ScoredChunk


def _jaccard(text_a: str, text_b: str) -> float:
    """
    Compute Jaccard similarity between two text strings at the word level.

    WHAT: Tokenizes both texts into lowercase word sets and computes:
        J(A, B) = |A n B| / |A u B|

    Returns 1.0 for identical word sets, 0.0 for disjoint sets.

    WHY: Jaccard similarity at the word level is a simple, fast, and
    interpretable measure of text overlap. It is O(n) in the number of
    unique words and does not require any model loading or embedding
    computation. For the deduplication use case (detecting near-identical
    chunks), word-level overlap is sufficiently accurate.

    Args:
        text_a: First text string.
        text_b: Second text string.

    Returns:
        Jaccard similarity coefficient in [0.0, 1.0].
        Returns 1.0 if both strings are empty (vacuous truth:
        empty set equals empty set).
        Returns 0.0 if one string is empty and the other is not.
    """
    # WHAT: tokenize into lowercase words, using split() for simplicity.
    # WHY: split() splits on whitespace, which is fast and gives
    # word-level tokens sufficient for Jaccard overlap detection.
    # We don't need NLP-level tokenization for this task -- we just
    # want to know if two texts use very similar vocabulary.
    words_a: set[str] = set(text_a.lower().split())
    words_b: set[str] = set(text_b.lower().split())

    # WHAT: compute intersection and union sizes.
    intersection: int = len(words_a & words_b)
    union: int = len(words_a | words_b)

    # WHAT: handle the edge case of two empty strings.
    # WHY: mathematically, two empty sets have Jaccard = 1.0 (the sets
    # are identical). In practice, this case should never occur with
    # real chunks, but we handle it for robustness.
    if union == 0:
        return 1.0

    return float(intersection / union)


def deduplicate_chunks(
    chunks: list[ScoredChunk],
    threshold: float = 0.85,
) -> list[ScoredChunk]:
    """
    Remove near-duplicate adjacent chunks using Jaccard word overlap.

    WHAT: Performs a single-pass scan of the chunk list. For each chunk
    at position i (starting from i=1), compares it to the last kept
    chunk. If the Jaccard similarity >= threshold, the chunk is discarded
    as a near-duplicate. Otherwise, it is kept.

    This is O(n) in the number of chunks. It only compares adjacent
    pairs because in a sorted retrieval list (by relevance), near-
    duplicates from overlapping document sections will be adjacent.

    WHY: Retrieval pipelines often produce near-duplicate results:
      - Overlapping chunks from chunking (M1's chunker may overlap
        adjacent chunks by 10-20% to preserve context).
      - Same passage retrieved by multiple backends (dense + sparse)
        with slightly different boundaries.
      - Paragraphs that repeat similar boilerplate across a document
        (e.g. repeated safety warnings).

    Deduplication removes this redundancy so the LLM context window
    is used efficiently. We use Jaccard similarity (word overlap)
    instead of embedding similarity because it is fast (no model
    needed) and sufficient for detecting near-identical text.

    Args:
        chunks: List of ScoredChunk objects, typically from reranker
            or fusion output. Should be sorted by descending score.
        threshold: Jaccard similarity threshold for deduplication.
            Chunks with similarity >= threshold are considered
            duplicates. Default 0.85.

    Returns:
        Deduplicated list of ScoredChunk objects. The first occurrence
        of each near-duplicate group is kept. If input is empty or
        single-element, returned as-is (or empty list).
    """
    # WHAT: short-circuit for 0 or 1 elements.
    # WHY: with <= 1 elements, there is nothing to deduplicate against.
    # The single-pass comparison starts at index 1, so these cases
    # would cause an index error or meaningless iteration.
    if len(chunks) <= 1:
        return list(chunks)

    # WHAT: initialize the deduplicated list with the first chunk.
    # WHY: the first chunk is always kept (there is nothing to compare
    # it against). Subsequent chunks are compared to this keeper.
    deduped: list[ScoredChunk] = [chunks[0]]

    # WHAT: scan remaining chunks, comparing each to the last kept chunk.
    # WHY: single-pass O(n) algorithm. Since retrieval results are sorted
    # by relevance, chunks from the same document section (which are most
    # likely to be near-duplicates) will be adjacent. Comparing only to
    # the immediately last kept chunk is sufficient for this use case.
    for i in range(1, len(chunks)):
        current_chunk = chunks[i]
        last_kept = deduped[-1]

        # WHAT: compute Jaccard similarity between current chunk and
        # the last chunk that was NOT removed.
        similarity: float = _jaccard(
            last_kept.chunk.text,
            current_chunk.chunk.text,
        )

        # WHAT: keep the chunk if it is sufficiently different from
        # the last kept chunk.
        # WHY: if similarity >= threshold, this chunk is a near-duplicate
        # and should be skipped. If below threshold, it is distinct
        # enough to keep.
        if similarity < threshold:
            deduped.append(current_chunk)

    return deduped


def expand_context(
    chunks: list[ScoredChunk],
    storage_manager=None,
    window: int = 3,
) -> list[ScoredChunk]:
    """
    Expand each retrieved chunk with its neighboring chunks (placeholder).

    WHAT: Currently returns the input chunks unchanged. This is a
    placeholder for future implementation that will fetch the `window`
    chunks before and after each retrieved chunk from the document,
    providing richer context to the LLM.

    For example, if chunk #42 is retrieved, the expander would also
    include chunks #39, #40, #41, #43, #44, #45 (with window=3).

    WHY placeholder: full implementation requires the StorageManager
    to expose a get_adjacent_chunks(chunk_id, window) API that queries
    the vector store for chunks with the same source_filename and
    adjacent position_in_document values. This API is planned but not
    yet implemented in M2's StorageManager.

    The placeholder ensures the pipeline composes correctly without
    context expansion. Once the StorageManager API is available, this
    function will be implemented without changing any other pipeline
    code.

    Args:
        chunks: List of ScoredChunk objects to expand.
        storage_manager: StorageManager instance for querying adjacent
            chunks. Not used in placeholder implementation.
        window: Number of chunks to fetch on each side (before and
            after). Default 3, meaning up to 6 additional chunks per
            retrieved chunk. Not used in placeholder implementation.

    Returns:
        The input list unchanged (placeholder behavior).
    """
    # WHAT: passthrough -- return the input list as-is.
    # WHY: context expansion requires StorageManager.get_adjacent_chunks()
    # which is not yet implemented. This placeholder is a no-op that
    # preserves the pipeline's contract without blocking development.
    return list(chunks)
