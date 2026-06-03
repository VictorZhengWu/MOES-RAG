"""
Tests for M4 Knowledge Graph Engine — User Tier module.

Tests cover:
  1. Basic tier
  2. Pro tier
  3. Enterprise tier
"""

import pytest

# WHAT: Import UserTier and USER_TIERS from the tier module.
# WHY: Tests validate that all three user tiers have correct attribute values
#      matching the specification.
from m4_kg.core.tier import UserTier, USER_TIERS


class TestBasicTier:
    """Test the Basic user tier configuration."""

    def test_basic_tier_values(self):
        """Verify Basic tier has the correct restricted settings.

        WHAT: Check all fields of the 'basic' tier entry.
        WHY: Basic tier is the most constrained — depth=1, max_entities=20,
             no cross-reference, limited context tokens (2048).
        """
        tier = USER_TIERS["basic"]
        assert tier.level == "basic"
        assert tier.traversal_depth == 1
        assert tier.max_entities == 20
        assert tier.enable_cross_ref is False
        assert tier.context_token_limit == 2048

    def test_basic_tier_immutable_reference_returned(self):
        """Verify the basic tier object is returned, not a copy.

        WHAT: Ensure USER_TIERS["basic"] returns the same object on each access.
        WHY: The tier objects should be singletons — creating copies would be
             wasteful since UserTier is an immutable value object.
        """
        t1 = USER_TIERS["basic"]
        t2 = USER_TIERS["basic"]
        assert t1 is t2


class TestProTier:
    """Test the Pro user tier configuration."""

    def test_pro_tier_values(self):
        """Verify Pro tier has the correct intermediate settings.

        WHAT: Check all fields of the 'pro' tier entry.
        WHY: Pro tier allows deeper traversal (depth=3), more entities (50),
             cross-reference enabled, and larger context (8192).
        """
        tier = USER_TIERS["pro"]
        assert tier.level == "pro"
        assert tier.traversal_depth == 3
        assert tier.max_entities == 50
        assert tier.enable_cross_ref is True
        assert tier.context_token_limit == 8192


class TestEnterpriseTier:
    """Test the Enterprise user tier configuration."""

    def test_enterprise_tier_values(self):
        """Verify Enterprise tier has the correct maximum settings.

        WHAT: Check all fields of the 'enterprise' tier entry.
        WHY: Enterprise tier has the deepest traversal (depth=5), most
             entities (200), cross-reference enabled, and largest context
             (32768) for the most complex queries.
        """
        tier = USER_TIERS["enterprise"]
        assert tier.level == "enterprise"
        assert tier.traversal_depth == 5
        assert tier.max_entities == 200
        assert tier.enable_cross_ref is True
        assert tier.context_token_limit == 32768

    def test_enterprise_tier_user_creation(self):
        """Verify UserTier can be instantiated directly for custom tiers.

        WHAT: Create a custom UserTier instance via the constructor.
        WHY: While USER_TIERS provides predefined tiers, the UserTier dataclass
             should also support custom tier creation for admin-defined tiers.
        """
        custom = UserTier(
            level="custom-extreme",
            traversal_depth=10,
            max_entities=500,
            enable_cross_ref=True,
            context_token_limit=65536,
        )
        assert custom.level == "custom-extreme"
        assert custom.traversal_depth == 10
        assert custom.max_entities == 500
        assert custom.enable_cross_ref is True
        assert custom.context_token_limit == 65536
