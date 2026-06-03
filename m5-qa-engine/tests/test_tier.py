"""
Tests for m5_qa.core.tier — UserTier and PremiumQuota.

Tests cover:
  1. Basic tier properties (context window, default mode, premium limit)
  2. Pro tier properties
  3. PremiumQuota consume/exhaust lifecycle
"""

import pytest

from m5_qa.core.tier import UserTier, PremiumQuota, USER_TIERS


class TestUserTierBasic:
    """Verify Basic-tier UserTier properties."""

    def test_basic_tier_properties(self):
        """
        WHAT: Test that the Basic tier has 4K context, simple mode, and 3 daily premium queries.
        WHY: Basic is the default tier for unauthenticated or free users.
             Its constraints define the minimum service level guarantee.
        """
        tier = USER_TIERS["basic"]

        assert tier.level == "basic"
        assert tier.context_window == 4000, "Basic tier should have 4K context window"
        assert tier.default_mode == "simple", "Basic tier should default to simple mode"
        assert tier.daily_premium_limit == 3, "Basic tier should have 3 daily premium queries"


class TestUserTierPro:
    """Verify Pro-tier UserTier properties."""

    def test_pro_tier_properties(self):
        """
        WHAT: Test that the Pro tier has 8K context, pipeline mode, and 10 daily premium queries.
        WHY: Pro is the mid-tier for paid users. pipeline mode provides
             better answer quality by combining M3 semantic + M4 graph retrieval.
        """
        tier = USER_TIERS["pro"]

        assert tier.level == "pro"
        assert tier.context_window == 8000, "Pro tier should have 8K context window"
        assert tier.default_mode == "pipeline", "Pro tier should default to pipeline mode"
        assert tier.daily_premium_limit == 10, "Pro tier should have 10 daily premium queries"


class TestPremiumQuota:
    """Verify PremiumQuota consume/exhaust lifecycle."""

    def test_premium_quota_consume_and_exhaust(self):
        """
        WHAT: Test the full lifecycle of PremiumQuota: can_use → consume → exhaust.
        WHY: Premium quota is the mechanism for temporary tier upgrades.
             Correct consume/exhaust logic is critical for fairness and billing.
        """
        # Create a quota with 3 daily Premium uses, none used yet
        quota = PremiumQuota(user_id="test_user", date="2026-06-03", total=3)

        # Initially, user can use Premium (used=0 < total=3)
        assert quota.can_use() is True
        assert quota.used == 0

        # Consume Premium credits one by one
        assert quota.consume() is True, "First consume should succeed"
        assert quota.used == 1
        assert quota.can_use() is True, "Should still have quota after 1/3 uses"

        assert quota.consume() is True, "Second consume should succeed"
        assert quota.used == 2

        assert quota.consume() is True, "Third consume should succeed"
        assert quota.used == 3

        # Now exhausted: used=3, total=3
        assert quota.can_use() is False, "Should be exhausted after 3/3 uses"
        assert quota.consume() is False, "Consume should fail when exhausted"
        assert quota.used == 3, "Used count should not increase after failed consume"

    def test_enterprise_tier_unlimited_premium(self):
        """
        WHAT: Test that Enterprise tier has unlimited Premium (-1 daily_premium_limit).
        WHY: Enterprise users get self_rag as their default mode, so Premium
             upgrade is meaningless for them. -1 is the sentinel for unlimited.
        """
        tier = USER_TIERS["enterprise"]

        assert tier.level == "enterprise"
        assert tier.context_window == 16000, "Enterprise tier should have 16K context window"
        assert tier.default_mode == "self_rag", "Enterprise tier should default to self_rag mode"
        assert tier.daily_premium_limit == -1, \
            "Enterprise tier should have -1 (unlimited) daily premium limit"
