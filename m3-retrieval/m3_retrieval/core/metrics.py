# -*- coding: utf-8 -*-
"""
Quality Metrics for evaluating retrieval pipeline performance.

WHAT: Implements three standard information retrieval evaluation metrics:
  1. recall_at_k(): fraction of relevant documents found in the top k results.
  2. mrr(): Mean Reciprocal Rank -- the reciprocal of the rank of the first
     relevant result (1/rank, or 0 if no relevant result found).
  3. ndcg_at_k(): Normalized Discounted Cumulative Gain -- measures ranking
     quality by comparing DCG against the ideal DCG.

All three functions are pure, side-effect-free, and operate on document
ID sets rather than full Chunk objects. This makes them usable for:
  - Offline evaluation with ground-truth annotation data.
  - Online monitoring (tracking retrieval quality in production).
  - Benchmarking different pipeline configurations.

WHY: Retrieval quality metrics are essential for:
  1. Comparing different retrieval strategies (dense-only vs. hybrid).
  2. Tuning hyperparameters (fusion_k, rerank_top_k, dedup_threshold).
  3. Detecting regressions when pipeline code changes.
  4. Meeting latency/quality SLOs in production.

All functions accept document IDs as strings for maximum flexibility.
The metrics follow standard IR conventions for edge cases (empty sets,
missing relevant documents).
"""

from __future__ import annotations

import math


def recall_at_k(
    relevant_ids: set[str],
    retrieved_ids: list[str],
    k: int = 20,
) -> float:
    """
    Compute Recall@k: fraction of relevant documents found in top k results.

    WHAT: recall = |relevant_ids INTERSECT retrieved_ids[:k]| / |relevant_ids|

    This measures retrieval completeness: of all known relevant documents,
    what fraction did the pipeline find within the top k results?

    Edge cases:
      - If relevant_ids is empty: returns 1.0 (convention: no relevant docs
        means nothing was missed).
      - If retrieved_ids is empty: returns 0.0.
      - k may be larger than len(retrieved_ids): all retrieved IDs are
        considered (the slice clips at list length).

    WHY: Recall is the primary completeness metric. In the marine/offshore
    domain, missing a relevant regulation clause could mean missing a
    safety requirement, so high recall is critical for the expert system.

    Args:
        relevant_ids: Set of document IDs that are known to be relevant
            for the query (ground truth annotations).
        retrieved_ids: List of document IDs returned by the retrieval
            pipeline, ordered by descending relevance score.
        k: Number of top results to consider. Default 20.

    Returns:
        Recall in [0.0, 1.0]. 1.0 means all relevant docs were found;
        0.0 means none were found.
    """
    # WHAT: handle empty relevant set -- return 1.0 by convention.
    # WHY: if there are no ground-truth annotations, there are no
    # relevant documents to miss. Returning 1.0 avoids division by zero
    # and gives a trivially perfect score.
    if len(relevant_ids) == 0:
        return 1.0

    # WHAT: slice to top k retrieved IDs.
    # WHY: recall is only computed over the top k results, since users
    # typically only examine the first page of results. Docs beyond k
    # are practically invisible.
    top_k_retrieved: set[str] = set(retrieved_ids[:k])

    # WHAT: count how many relevant docs appear in the top k.
    # WHY: intersection computes the overlap exactly.
    found: int = len(relevant_ids & top_k_retrieved)

    return found / len(relevant_ids)


def mrr(
    relevant_ids: set[str],
    retrieved_ids: list[str],
) -> float:
    """
    Compute Mean Reciprocal Rank (MRR) for a single query.

    WHAT: mrr = 1 / rank_of_first_relevant_result
    where rank is 1-indexed (first position = rank 1, gives MRR = 1.0).

    If no relevant document appears in the retrieved list, MRR = 0.0.

    Edge cases:
      - Empty retrieved_ids: returns 0.0.
      - Empty relevant_ids: returns 1.0 (convention: if nothing to find,
        the ideal result is trivially at rank 1).

    WHY: MRR measures how quickly the user finds the first useful result.
    In conversational QA, the first result matters most because users
    rarely scroll past the top few results. MRR penalises retrieval
    engines that bury relevant results deep in the list.

    Args:
        relevant_ids: Set of document IDs known to be relevant.
        retrieved_ids: List of document IDs in retrieval order.

    Returns:
        MRR in [0.0, 1.0]. 1.0 means the first result was relevant;
        0.0 means no relevant result was found.
    """
    # WHAT: handle empty relevant set -- return 1.0 by convention.
    # WHY: prevents division by zero and follows the standard IR
    # convention: with no ground truth, every result is trivially correct.
    if len(relevant_ids) == 0:
        return 1.0

    # WHAT: scan retrieved IDs in order to find the first relevant one.
    # rank is 1-based (enumerate with start=1).
    # WHY: we want the RECIPROCAL rank (1/rank), which is highest when
    # the first result is relevant (1/1 = 1.0) and decreases as the
    # relevant result appears later in the list.
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank

    # WHAT: no relevant document found in the entire retrieved list.
    # WHY: return 0.0 rather than raising an error. The retrieval engine
    # completely failed to surface any relevant result for this query.
    return 0.0


def _dcg_at_k(
    relevant_ids: set[str],
    retrieved_ids: list[str],
    k: int = 20,
) -> float:
    """
    Compute Discounted Cumulative Gain at rank k.

    WHAT: DCG@k = sum over i in [1..k] of gain_i / log2(i + 1)
    where gain_i = 1 if retrieved_ids[i-1] is relevant, 0 otherwise.

    Uses binary relevance (1/0). The division by log2(i + 1) discounts
    the gain of results appearing later in the list, reflecting the
    user behaviour of paying less attention to lower-ranked results.

    WHY separate helper: DCG is used to compute both the actual DCG
    and the ideal DCG (IDCG). Keeping it as a private function avoids
    duplication and makes the relationship between DCG and NDCG clear.

    Args:
        relevant_ids: Set of relevant document IDs.
        retrieved_ids: List of document IDs in ranked order.
        k: Cutoff rank. Only first k results are scored.

    Returns:
        DCG@k as a float. 0.0 if no relevant docs in top k or empty input.
    """
    dcg: float = 0.0

    # WHAT: iterate over at most k results with 1-based rank.
    # enumerate with start=1 gives rank directly (rank 1 = first result).
    for rank, doc_id in enumerate(retrieved_ids[:k], start=1):
        if doc_id in relevant_ids:
            # WHAT: binary gain: 1.0 for relevant, 0.0 for irrelevant.
            # The 0.0 case (irrelevant) contributes nothing, so we skip it.
            # WHY: using binary relevance is the simplest and most common
            # approach. For graded relevance (multi-level), the gain would
            # be the relevance level (e.g. 0/1/2/3).
            gain: float = 1.0

            # WHAT: discount by log2(rank + 1).
            # WHY: log2(rank + 1) is the standard DCG discount function.
            # At rank 1: 1/log2(2) = 1.0 (no discount).
            # At rank 2: 1/log2(3) ≈ 0.631.
            # At rank 10: 1/log2(11) ≈ 0.289.
            # This models diminishing user attention at lower ranks.
            discount: float = math.log2(rank + 1)
            dcg += gain / discount

    return dcg


def ndcg_at_k(
    relevant_ids: set[str],
    retrieved_ids: list[str],
    k: int = 20,
) -> float:
    """
    Compute Normalized Discounted Cumulative Gain at rank k.

    WHAT: NDCG@k = DCG@k / IDCG@k

    where:
      - DCG@k is the Discounted Cumulative Gain of the actual ranking.
      - IDCG@k is the Ideal DCG (best possible ranking: all relevant
        docs listed first, sorted by relevance if graded).

    NDCG@k is always in [0.0, 1.0]. 1.0 means the ranking is identical
    to the ideal ranking. Values closer to 0 mean the ranking is poor
    (relevant documents appear late or not at all).

    Edge cases:
      - Empty retrieved_ids: returns 0.0.
      - Empty relevant_ids: returns 1.0 (if nothing is relevant, any
        ranking is trivially ideal).
      - IDCG = 0 (no relevant docs in the top k of the ideal ranking):
        returns 1.0 (vacuous perfection).

    WHY: NDCG is the gold-standard ranking quality metric. Unlike
    recall (which only cares about presence/absence), NDCG evaluates
    the ORDERING of results. A retrieval engine that places 10
    relevant results at positions 41-50 gets the same recall as one
    that places them at positions 1-10, but the latter gets far higher
    NDCG because users see the most relevant results first.

    Args:
        relevant_ids: Set of document IDs known to be relevant.
        retrieved_ids: List of document IDs in retrieval order
            (position 0 = top result).
        k: Cutoff rank. Default 20.

    Returns:
        NDCG@k in [0.0, 1.0].
    """
    # WHAT: handle empty relevant set -- returns 1.0 by convention.
    # WHY: with no ground truth, the ranking is trivially ideal.
    # This also prevents division by zero when IDCG = 0.
    if len(relevant_ids) == 0:
        return 1.0

    # WHAT: handle empty retrieved list.
    # WHY: DCG is 0 and we can return 0.0 without computing IDCG.
    if len(retrieved_ids) == 0:
        return 0.0

    # WHAT: compute actual DCG of the system's ranking.
    dcg: float = _dcg_at_k(relevant_ids, retrieved_ids, k)

    # WHAT: compute Ideal DCG -- the DCG obtained by the best possible
    # ranking. For binary relevance, the ideal ranking places all
    # relevant docs at the top (positions 1..R where R = |relevant_ids|).
    # We simulate this by creating a list where the first R entries are
    # relevant IDs, followed by the same irrelevant IDs in the same order.
    # WHY: IDCG is the normalization factor. Dividing DCG by IDCG ensures
    # NDCG is always in [0, 1], comparable across queries and result sets
    # of different sizes.
    num_relevant: int = len(relevant_ids)
    # Build ideal ordering: all relevant IDs first (any order is fine
    # for binary relevance), then irrelevant IDs.
    irrelevant_ids: list[str] = [
        did for did in retrieved_ids if did not in relevant_ids
    ]
    # For binary relevance, the ideal ordering places all relevant docs at
    # ranks 1..R. We use the actual relevant IDs (order doesn't matter for
    # binary relevance since all have gain=1).
    ideal_order: list[str] = (
        list(relevant_ids)[:num_relevant] + irrelevant_ids
    )
    idcg: float = _dcg_at_k(relevant_ids, ideal_order, k)

    # WHAT: handle IDCG = 0 edge case.
    # WHY: IDCG is 0 when no relevant docs exist OR when k is 0 or
    # the ideal ordering produces 0 DCG (should not happen if
    # relevant_ids is non-empty). We return 1.0 for vacuous perfection.
    # A practical example: relevant_ids has only IDs not in the retrieved
    # IDs at all -- but in binary relevance, the ideal ordering still
    # places them first, so IDCG > 0 if len(relevant_ids) > 0.
    if idcg == 0.0:
        return 1.0

    return dcg / idcg
