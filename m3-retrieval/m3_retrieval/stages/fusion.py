# -*- coding: utf-8 -*-
"""
RRF (Reciprocal Rank Fusion) stage for the M3 Retrieval Pipeline.

WHAT: Implements RRF_score(d) = sum(1 / (k + rank_i(d))) across multiple
retrieval result sets (dense, sparse, knowledge_graph). Deduplicates by
chunk_id, accumulates RRF scores, and returns the top_k results with
source="fusion".

WHY: RRF is the standard parameter-free fusion method for combining
heterogeneous ranked lists. Unlike linear score combination, RRF does
not require score normalization across different retrieval backends,
each of which has its own scoring scale (cosine similarity, BM25 rank,
graph relevance). RRF only uses rank position, making it robust to
scale differences. It is proven in TREC and academic benchmarks to
produce better results than weighted sum or CombSUM approaches.

Key design decisions:
  - rrf_fusion() is a pure function with no side effects. It takes
    result lists and parameters, returns fused results. No class needed
    because there is no mutable state to manage (unlike retrievers
    which hold storage backend references).
  - Deduplication is by chunk_id, not by text content. chunk_id is the
    canonical identifier assigned by M1 during chunking. Two different
    retrievers returning the same chunk will have the same chunk_id.
  - Uses dict (not set) for dedup because we need to accumulate scores
    for each unique chunk. A set would lose the accumulation semantics.
  - k=60 is the standard RRF constant from the literature. It was
    empirically determined to work well across diverse datasets.
"""

from __future__ import annotations

from contracts.retrieval import ScoredChunk


def rrf_fusion(
    result_sets: list[list[ScoredChunk]],
    k: int = 60,
    top_k: int = 50,
) -> list[ScoredChunk]:
    """
    Fuse multiple ranked retrieval result sets using Reciprocal Rank Fusion.

    WHAT: Implements the RRF formula:
        RRF_score(d) = sum over each result list of 1 / (k + rank_i(d))

    where rank_i(d) is the 1-based position of document d in result list i
    (rank 1 = best, rank 2 = second best, etc.). If document d does not
    appear in result list i, its contribution from that list is 0.

    The function:
      1. Iterates over each result set, assigning rank 1, 2, 3, ...
         based on position in the list.
      2. For each chunk (identified by chunk_id), accumulates the RRF
         contribution: 1 / (k + rank).
      3. Deduplicates by chunk_id -- if the same chunk appears in multiple
         result sets, its scores are accumulated.
      4. Sorts by accumulated RRF score (descending).
      5. Returns the top_k results with source="fusion".

    Args:
        result_sets: A list of ranked result lists. Each inner list
            contains ScoredChunk objects in descending order of the
            original retriever's score (best first). Typically these
            come from dense_retriever.search(), sparse_retriever.search(),
            and potentially a knowledge_graph retriever.
        k: The RRF constant. Higher k gives more weight to consensus
            (chunks appearing in multiple lists) vs. high individual
            ranks. Standard value is 60. Default 60.
        top_k: Maximum number of fused results to return. Default 50.

    Returns:
        A list of ScoredChunk objects sorted by descending RRF score,
        with source="fusion". Empty list if all input lists are empty.

    Example:
        >>> dense_results = [...]  # from DenseRetriever
        >>> sparse_results = [...]  # from SparseRetriever
        >>> fused = rrf_fusion([dense_results, sparse_results], top_k=20)
    """
    # WHAT: Handle empty input -- short-circuit to empty result.
    # WHY: If no retrieval backends returned anything, there is nothing
    # to fuse. Returning [] saves downstream stages from processing
    # a meaningless empty fusion.
    if not result_sets:
        return []

    # WHAT: a dict mapping chunk_id -> (accumulated_rrf_score, ScoredChunk).
    # WHY: use chunk_id as the dedup key because it is the canonical
    # identifier assigned by M1 during chunking. Two retrievers may
    # score the same chunk differently, but the chunk_id uniquely
    # identifies it. We also store the first-encountered ScoredChunk
    # object for each chunk_id, as it carries the chunk metadata
    # (text, citation, etc.) which is identical regardless of which
    # retriever found it.
    fused: dict[str, tuple[float, ScoredChunk]] = {}

    # WHAT: iterate over each result set to compute per-rank RRF
    # contributions and accumulate them by chunk_id.
    for result_list in result_sets:
        # WHAT: rank is 1-based (rank 1 = best match).
        # WHY: RRF formula uses 1-based rank: 1/(k + 1) for the best
        # result. Using 0-based rank would inflate scores for top items.
        for rank_1_based, scored_chunk in enumerate(result_list, start=1):
            chunk_id: str = scored_chunk.chunk.chunk_id

            # WHAT: RRF contribution for this chunk in this result list.
            # WHY: 1/(k + rank) gives higher weight to better-ranked items.
            # The constant k=60 dampens the difference between rank 1 and
            # rank 2 so that very high ranks don't dominate the fusion.
            rrf_contribution: float = 1.0 / (k + rank_1_based)

            if chunk_id in fused:
                # WHAT: chunk already seen in another result list.
                # Accumulate RRF score; keep the first-encountered
                # ScoredChunk (which has the same chunk metadata).
                current_score, existing_sc = fused[chunk_id]
                fused[chunk_id] = (current_score + rrf_contribution, existing_sc)
            else:
                # WHAT: first time seeing this chunk.
                # Store the chunk with its initial RRF score.
                fused[chunk_id] = (rrf_contribution, scored_chunk)

    # WHAT: sort fused chunks by accumulated RRF score in descending order.
    # WHY: higher RRF score = more consensus across retrievers AND/OR
    # higher individual ranks. This produces the final relevance ordering.
    sorted_fused: list[tuple[float, ScoredChunk]] = sorted(
        fused.values(), key=lambda item: item[0], reverse=True
    )

    # WHAT: construct the final output list with source="fusion" and
    # the RRF score replacing the original retriever score.
    # Limit to top_k results.
    # WHY: downstream stages (reranker, context expander) expect
    # ScoredChunk objects with consistent source metadata. The
    # source="fusion" marker identifies these results as fused,
    # distinguishing them from raw retriever outputs.
    result: list[ScoredChunk] = []
    for rrf_score, sc in sorted_fused[:top_k]:
        result.append(ScoredChunk(
            chunk=sc.chunk,
            score=rrf_score,
            source="fusion",
            citation=sc.citation,
        ))

    return result
