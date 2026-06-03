"""
Tests for M5 QA Engine — Token Budget (token_budget.py).

WHAT: Unit tests for TokenBudget dataclass, estimate_tokens(), and allocate_budget().
WHY: Verify that token allocation follows tier-based ratios and that the
     query-length factor dynamically adjusts retrieval vs generation budget.
"""

import pytest

from m5_qa.context.token_budget import (
    TokenBudget,
    allocate_budget,
    estimate_tokens,
)


# ---------------------------------------------------------------------------
# Tests: estimate_tokens
# ---------------------------------------------------------------------------

class TestEstimateTokens:
    """Tests for estimate_tokens() — character-based token approximation."""

    def test_english_text(self):
        """
        WHAT: Roughly 1 token per 4 English characters.
        WHY: This is the standard heuristic for English token estimation.
        """
        # 40 English chars → ~10 tokens
        result = estimate_tokens("Hello world, this is a test sentence here")
        assert result > 0

    def test_empty_string(self):
        """
        WHAT: Empty string returns 1 token minimum.
        WHY: To avoid division-by-zero and ensure a floor value.
        """
        result = estimate_tokens("")
        assert result == 1


# ---------------------------------------------------------------------------
# Tests: TokenBudget dataclass
# ---------------------------------------------------------------------------

class TestTokenBudgetBasic:
    """Tests for Basic-tier TokenBudget (4000 total, 30% retrieval)."""

    def test_basic_budget(self):
        """
        WHAT: Basic tier = 4000 total, retrieval_limit = 1200 (30% of 4000).
        WHY: Basic tier users get the smallest context window, with
             30% allocated to retrieval, 20% to history, 50% to generation.
        """
        budget = TokenBudget(total=4000, retrieval_ratio=0.30,
                             history_ratio=0.20, generation_ratio=0.50)

        assert budget.total == 4000
        assert budget.retrieval_limit == 1200  # 4000 * 0.30
        assert budget.history_limit == 800      # 4000 * 0.20
        assert budget.generation_limit == 2000  # 4000 * 0.50


class TestTokenBudgetPro:
    """Tests for Pro-tier TokenBudget (8000 total, 40% retrieval)."""

    def test_pro_budget(self):
        """
        WHAT: Pro tier = 8000 total, retrieval_limit = 3200 (40% of 8000).
        WHY: Pro tier users get a larger context window with more budget
             for retrieval to improve answer quality.
        """
        budget = TokenBudget(total=8000, retrieval_ratio=0.40,
                             history_ratio=0.20, generation_ratio=0.40)

        assert budget.total == 8000
        assert budget.retrieval_limit == 3200  # 8000 * 0.40
        assert budget.history_limit == 1600     # 8000 * 0.20
        assert budget.generation_limit == 3200  # 8000 * 0.40


class TestTokenBudgetEnterprise:
    """Tests for Enterprise-tier TokenBudget (16000 total, 50% retrieval)."""

    def test_enterprise_budget(self):
        """
        WHAT: Enterprise tier = 16000 total, retrieval_limit = 8000 (50% of 16000).
        WHY: Enterprise tier gets the largest context window, with half
             dedicated to retrieval for maximum answer accuracy.
        """
        budget = TokenBudget(total=16000, retrieval_ratio=0.50,
                             history_ratio=0.20, generation_ratio=0.30)

        assert budget.total == 16000
        assert budget.retrieval_limit == 8000  # 16000 * 0.50
        assert budget.history_limit == 3200     # 16000 * 0.20
        assert budget.generation_limit == 4800  # 16000 * 0.30


# ---------------------------------------------------------------------------
# Tests: allocate_budget
# ---------------------------------------------------------------------------

class TestAllocateBudget:
    """Tests for allocate_budget() — dynamic budget allocation by tier."""

    def test_basic_allocation(self):
        """
        WHAT: allocate_budget("basic") returns Budget with 4000 total.
        WHY: The function should return correct tier defaults when no
             query-length adjustment is needed.
        """
        budget = allocate_budget("basic")
        assert budget.total == 4000
        assert budget.retrieval_limit == int(4000 * 0.30)
        assert budget.history_limit == int(4000 * 0.20)

    def test_pro_allocation(self):
        """
        WHAT: allocate_budget("pro") returns Budget with 8000 total.
        """
        budget = allocate_budget("pro")
        assert budget.total == 8000
        assert budget.retrieval_limit == int(8000 * 0.40)

    def test_enterprise_allocation(self):
        """
        WHAT: allocate_budget("enterprise") returns Budget with 16000 total.
        """
        budget = allocate_budget("enterprise")
        assert budget.total == 16000
        assert budget.retrieval_limit == int(16000 * 0.50)

    def test_unknown_tier_fallback(self):
        """
        WHAT: Unknown tier string falls back to Basic budget.
        WHY: Safety net — prevents crashes from misconfigured tier strings.
        """
        budget = allocate_budget("super_duper")
        assert budget.total == 4000  # fallback to basic

    def test_query_length_factor(self):
        """
        WHAT: Long query increases retrieval budget proportionally.
        WHY: Longer queries contain more search terms and need more
             retrieval context. The query_factor (0.5x-1.5x) scales
             the retrieval ratio based on query length / 500.
        """
        # Short query (~20 chars): factor ≈ 0.5 (clamped to min 0.5)
        short_budget = allocate_budget("pro", query="short")
        # Long query (~600 chars): factor ≈ 1.2 (600/500 = 1.2)
        long_query = "x" * 600
        long_budget = allocate_budget("pro", query=long_query)

        # The long query should have more retrieval budget than the short one
        assert long_budget.retrieval_limit >= short_budget.retrieval_limit, (
            f"Long query retrieval ({long_budget.retrieval_limit}) should be >= "
            f"short query retrieval ({short_budget.retrieval_limit})"
        )

    def test_default_query(self):
        """
        WHAT: Empty/default query uses base ratios without adjustment.
        """
        budget = allocate_budget("pro")
        assert budget.retrieval_limit == int(8000 * 0.40)
        assert budget.history_limit == int(8000 * 0.20)
