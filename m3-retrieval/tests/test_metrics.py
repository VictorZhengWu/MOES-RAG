# -*- coding: utf-8 -*-
"""
Tests for M3 Quality Metrics (metrics.py).

WHAT: Validates three retrieval evaluation functions:
  1. recall_at_k() — 3 tests (perfect, half, empty)
  2. mrr() — 3 tests (first rank, third rank, not found)
  3. ndcg_at_k() — 2 tests (perfect, empty)

WHY: Retrieval quality metrics are essential for offline evaluation of
the retrieval pipeline. They quantify how well the pipeline finds relevant
documents (recall), how quickly it surfaces the first relevant result (MRR),
and how well it ranks by relevance (NDCG). Correct metric implementations
are prerequisites for any model selection or parameter tuning experiments.
"""

from __future__ import annotations

import math

import pytest


# =============================================================================
# Recall@k tests
# =============================================================================


class TestRecallAtK:
    """Test recall_at_k() -- fraction of relevant docs retrieved in top k."""

    def test_recall_perfect(self) -> None:
        """
        WHAT: When all relevant docs are in the top-k retrieved list,
        recall should be 1.0.

        WHY: This is the ideal case -- the retrieval engine found every
        known relevant document. The metric must return exactly 1.0.
        """
        from m3_retrieval.core.metrics import recall_at_k

        relevant = {"d1", "d2", "d3"}
        retrieved = ["d1", "d2", "d3", "d4", "d5"]

        result = recall_at_k(relevant, retrieved, k=5)
        assert result == pytest.approx(1.0, abs=0.001)

    def test_recall_half(self) -> None:
        """
        WHAT: When only half of the relevant docs are in the top-k list,
        recall should be 0.5.

        WHY: This is a realistic scenario -- the retrieval engine finds
        some but not all relevant documents. The metric must correctly
        compute the fraction found.
        """
        from m3_retrieval.core.metrics import recall_at_k

        relevant = {"d1", "d2", "d3", "d4"}
        retrieved = ["d1", "d2", "d5", "d6", "d7"]

        result = recall_at_k(relevant, retrieved, k=5)
        assert result == pytest.approx(0.5, abs=0.001)

    def test_recall_empty_retrieved(self) -> None:
        """
        WHAT: When the retrieved list is empty, recall should be 0.0.

        WHY: If nothing was retrieved, no relevant documents could be
        found. The metric must handle this edge case without division
        errors and return 0.0.
        """
        from m3_retrieval.core.metrics import recall_at_k

        relevant = {"d1", "d2", "d3"}
        retrieved: list[str] = []

        result = recall_at_k(relevant, retrieved, k=5)
        assert result == 0.0

    def test_recall_empty_relevant(self) -> None:
        """
        WHAT: When there are no relevant documents (empty set), recall
        should be 1.0 by convention (all zero relevant docs found).

        WHY: This edge case (no ground truth annotations) should not
        cause a division by zero. Following information retrieval
        convention, we return 1.0 when the relevant set is empty
        because there are no missing relevant documents.
        """
        from m3_retrieval.core.metrics import recall_at_k

        relevant: set[str] = set()
        retrieved = ["d1", "d2", "d3"]

        result = recall_at_k(relevant, retrieved, k=5)
        assert result == 1.0


# =============================================================================
# MRR tests
# =============================================================================


class TestMRR:
    """Test mrr() -- Mean Reciprocal Rank of the first relevant result."""

    def test_mrr_first_rank(self) -> None:
        """
        WHAT: When the first retrieved doc is relevant, MRR should be 1.0.

        WHY: Reciprocal rank = 1/rank. Rank 1 yields 1/1 = 1.0, which
        is the perfect MRR score. This means the user sees the best
        answer immediately at the top of results.
        """
        from m3_retrieval.core.metrics import mrr

        relevant = {"d1", "d2"}
        retrieved = ["d1", "d3", "d4"]

        result = mrr(relevant, retrieved)
        assert result == pytest.approx(1.0, abs=0.001)

    def test_mrr_third_rank(self) -> None:
        """
        WHAT: When the first relevant doc is at rank 3, MRR should be 1/3.

        WHY: Reciprocal rank = 1/3 ≈ 0.333. This penalises the retrieval
        engine for not placing the relevant result higher. The user must
        scroll past two irrelevant results to find the first useful one.
        """
        from m3_retrieval.core.metrics import mrr

        relevant = {"d1"}
        retrieved = ["d3", "d4", "d1", "d5"]

        result = mrr(relevant, retrieved)
        assert result == pytest.approx(1.0 / 3.0, abs=0.001)

    def test_mrr_not_found(self) -> None:
        """
        WHAT: When no relevant doc is in the retrieved list, MRR should
        be 0.0.

        WHY: The reciprocal rank is undefined when the relevant document
        is never found. Convention sets it to 0.0, meaning the engine
        completely failed to surface any relevant result.
        """
        from m3_retrieval.core.metrics import mrr

        relevant = {"d1", "d2"}
        retrieved = ["d3", "d4", "d5"]

        result = mrr(relevant, retrieved)
        assert result == 0.0

    def test_mrr_empty_retrieved(self) -> None:
        """
        WHAT: When the retrieved list is empty, MRR should be 0.0.

        WHY: An empty result list means nothing was found, so MRR is
        naturally 0.0. This must not cause a division-by-zero error.
        """
        from m3_retrieval.core.metrics import mrr

        relevant = {"d1"}
        retrieved: list[str] = []

        result = mrr(relevant, retrieved)
        assert result == 0.0


# =============================================================================
# NDCG@k tests
# =============================================================================


class TestNDCGAtK:
    """Test ndcg_at_k() -- Normalized Discounted Cumulative Gain."""

    def test_ndcg_perfect_ranking(self) -> None:
        """
        WHAT: When retrieved results are perfectly ordered by relevance
        (relevant docs sorted first), NDCG should be 1.0.

        WHY: NDCG = DCG / IDCG. When the ranking is perfect, the
        Discounted Cumulative Gain equals the Ideal DCG (the best
        possible ordering), so NDCG = 1.0.

        We use binary relevance: relevant docs get gain=1, irrelevant
        get gain=0.
        """
        from m3_retrieval.core.metrics import ndcg_at_k

        relevant = {"d1", "d2", "d3"}
        retrieved = ["d1", "d2", "d3", "d4", "d5"]  # All relevant first

        result = ndcg_at_k(relevant, retrieved, k=5)
        assert result == pytest.approx(1.0, abs=0.001)

    def test_ndcg_empty_retrieved(self) -> None:
        """
        WHAT: When the retrieved list is empty, NDCG should be 0.0.

        WHY: If nothing was retrieved, DCG = 0 and the metric must
        gracefully return 0.0 without any division error.
        """
        from m3_retrieval.core.metrics import ndcg_at_k

        relevant = {"d1", "d2"}
        retrieved: list[str] = []

        result = ndcg_at_k(relevant, retrieved, k=5)
        assert result == 0.0

    def test_ndcg_empty_relevant(self) -> None:
        """
        WHAT: When there are no relevant documents (empty set), NDCG
        should be 1.0 by convention.

        WHY: If no documents are relevant, any ranking is trivially
        perfect. Returning 1.0 avoids division-by-zero when IDCG=0.
        """
        from m3_retrieval.core.metrics import ndcg_at_k

        relevant: set[str] = set()
        retrieved = ["d1", "d2", "d3"]

        result = ndcg_at_k(relevant, retrieved, k=5)
        assert result == 1.0

    def test_ndcg_suboptimal_ranking(self) -> None:
        """
        WHAT: When relevant docs are placed after irrelevant ones,
        NDCG should be less than 1.0.

        WHY: A sub-optimal ordering (relevant docs not at the top)
        should produce DCG < IDCG, resulting in NDCG < 1.0. This
        correctly penalises retrieval engines that don't prioritize
        relevant results at the top.
        """
        from m3_retrieval.core.metrics import ndcg_at_k

        relevant = {"d1", "d2"}
        # Relevant docs (d1, d2) appear after irrelevant ones
        retrieved = ["d3", "d4", "d1", "d2", "d5"]

        result = ndcg_at_k(relevant, retrieved, k=5)
        assert 0.0 < result < 1.0
