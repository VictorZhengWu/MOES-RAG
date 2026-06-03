"""
Tests for m5_qa.core.router — ModeRouter.

Tests cover:
  1. Basic user gets simple mode
  2. Pro user gets pipeline mode
  3. Premium quota upgrades to self_rag mode
"""

import pytest

from m5_qa.core.router import ModeRouter
from m5_qa.core.tier import PremiumQuota, UserTier


# In-memory quota manager for testing
class MockQuotaManager:
    """
    Simple in-memory quota manager for testing ModeRouter.

    Stores quotas in a dict keyed by user_id.
    Not persistent — used only in unit tests.
    """

    def __init__(self):
        self._quotas: dict[str, PremiumQuota] = {}

    def add_quota(self, user_id: str, total: int) -> None:
        """Register a PremiumQuota for a test user."""
        self._quotas[user_id] = PremiumQuota(
            user_id=user_id, date="2026-06-03", total=total
        )

    def can_use(self, user_id: str) -> bool:
        """Check if user has remaining Premium quota."""
        quota = self._quotas.get(user_id)
        return quota is not None and quota.can_use()

    def consume(self, user_id: str) -> bool:
        """Consume one Premium credit for the user."""
        quota = self._quotas.get(user_id)
        return quota is not None and quota.consume()


class TestModeRouterBasic:
    """Verify ModeRouter returns correct mode for Basic tier."""

    def test_basic_user_gets_simple_mode(self):
        """
        WHAT: Test that a Basic-tier user (with no Premium quota) gets simple mode.
        WHY: Basic users default to the simplest pipeline: M3 retrieval only.
             Without Premium quota, there should be no upgrade.
        """
        router = ModeRouter()
        mode, tier = router.select_mode(
            user_id="basic_user",
            tier_level="basic",
        )

        assert mode == "simple", (
            f"Basic user without Premium should get 'simple' mode, got '{mode}'"
        )
        assert isinstance(tier, UserTier)
        assert tier.level == "basic"


class TestModeRouterPro:
    """Verify ModeRouter returns correct mode for Pro tier."""

    def test_pro_user_gets_pipeline_mode(self):
        """
        WHAT: Test that a Pro-tier user (with no Premium quota) gets pipeline mode.
        WHY: Pro users default to pipeline mode which combines M3+M4 retrieval.
        """
        router = ModeRouter()
        mode, tier = router.select_mode(
            user_id="pro_user",
            tier_level="pro",
        )

        assert mode == "pipeline", (
            f"Pro user without Premium should get 'pipeline' mode, got '{mode}'"
        )
        assert isinstance(tier, UserTier)
        assert tier.level == "pro"


class TestModeRouterPremium:
    """Verify that Premium quota upgrades the mode to self_rag."""

    def test_premium_quota_upgrades_to_self_rag(self):
        """
        WHAT: Test that a Basic user with available Premium quota gets self_rag mode.
        WHY: Premium is the mechanism for temporary tier upgrades. When a user has
             remaining Premium credits, the router should upgrade their mode to
             self_rag for that query, consuming one credit.
        """
        qm = MockQuotaManager()
        qm.add_quota(user_id="basic_user", total=3)

        router = ModeRouter()
        mode, tier = router.select_mode(
            user_id="basic_user",
            tier_level="basic",
            quota_manager=qm,
        )

        assert mode == "self_rag", (
            f"Basic user with Premium quota should get 'self_rag', got '{mode}'"
        )
        assert tier.level == "basic"

        # Verify one credit was consumed
        assert qm.can_use("basic_user") is True, "Should have 2/3 remaining"
        assert qm._quotas["basic_user"].used == 1

    def test_premium_exhausted_returns_default_mode(self):
        """
        WHAT: Test that a user with exhausted Premium quota gets their default mode.
        WHY: Once Premium credits are used up, the router should fall back to
             the tier's default mode without attempting an upgrade.
        """
        qm = MockQuotaManager()
        # Add quota with 0 remaining (already exhausted)
        qm.add_quota(user_id="pro_user", total=0)

        router = ModeRouter()
        mode, tier = router.select_mode(
            user_id="pro_user",
            tier_level="pro",
            quota_manager=qm,
        )

        assert mode == "pipeline", (
            f"Pro user with exhausted Premium should get 'pipeline', got '{mode}'"
        )
        assert tier.level == "pro"

    def test_unknown_tier_falls_back_to_basic(self):
        """
        WHAT: Test that an unknown tier level falls back to 'basic'.
        WHY: Prevent crashes when a tier level is misspelled or undefined.
             The system should degrade gracefully rather than fail.
        """
        router = ModeRouter()
        mode, tier = router.select_mode(
            user_id="unknown_user",
            tier_level="super_vip",  # Undefined tier
        )

        assert mode == "simple", (
            f"Unknown tier should fall back to 'simple' mode, got '{mode}'"
        )
        assert tier.level == "basic"
