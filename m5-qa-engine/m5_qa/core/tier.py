"""
M5 QA Engine — User Tier System (UserTier + PremiumQuota).

Defines the three-tier service model with differentiated context windows,
default pipeline modes, and daily Premium upgrade quotas.

Three tiers:
  - basic:      4K context, simple mode, 3 daily Premium queries
  - pro:        8K context, pipeline mode, 10 daily Premium queries
  - enterprise: 16K context, self_rag mode, unlimited Premium (-1 sentinel)

NOTE: M5 has its own UserTier definition (duplicates M4's concept).
      This is by design — modules must not import from each other's src/.
"""

from dataclasses import dataclass, field


@dataclass
class UserTier:
    """
    WHAT: Defines the service tier for a single user.
    WHY: Each tier has a different context window size (affects token budget),
         default pipeline mode (affects answer quality and cost), and daily
         Premium upgrade quota. This is the core access-control mechanism for
         differentiated service levels.

    Fields:
      - level: Tier identifier string ("basic", "pro", "enterprise")
      - context_window: LLM context window size in tokens (4000/8000/16000)
      - default_mode: Default pipeline mode ("simple", "pipeline", "self_rag")
      - daily_premium_limit: Max Premium upgrades per day (-1 = unlimited)
    """

    level: str = "basic"
    """Tier identifier: 'basic', 'pro', or 'enterprise'."""

    context_window: int = 4000
    """LLM context window size in tokens. Basic=4000, Pro=8000, Enterprise=16000."""

    default_mode: str = "simple"
    """Default pipeline mode for this tier: 'simple', 'pipeline', or 'self_rag'."""

    daily_premium_limit: int = 3
    """Maximum number of Premium upgrades per day. -1 means unlimited (Enterprise)."""


@dataclass
class PremiumQuota:
    """
    WHAT: Tracks daily Premium upgrade usage for a user.
    WHY: Premium allows temporary mode upgrades (e.g., Basic user → self_rag for one query).
         Each user has a daily allocation defined by their tier.
         Quota resets at midnight (managed by the conversation manager).
         Stored in M5's own SQLite database, NOT through M2.

    Fields:
      - user_id: Unique user identifier
      - date: Date string in "YYYY-MM-DD" format for daily reset tracking
      - total: Total Premium queries allowed on this date
      - used: Number of Premium queries already consumed today
    """

    user_id: str
    """Unique user identifier."""

    date: str
    """Date string in 'YYYY-MM-DD' format for daily tracking."""

    total: int
    """Total Premium queries allowed on this date."""

    used: int = 0
    """Number of Premium queries already consumed today."""

    def can_use(self) -> bool:
        """
        WHAT: Check if the user still has Premium quota remaining.
        WHY: Called before upgrading a query to self_rag mode.
             Returns True only if used < total.
        """
        return self.used < self.total

    def consume(self) -> bool:
        """
        WHAT: Consume one Premium credit if available.
        WHY: Called after a Premium upgrade is approved.
             Returns True on successful consumption, False if quota is already exhausted.
             Only increments used counter on successful consumption.
        """
        if not self.can_use():
            return False
        self.used += 1
        return True


# Pre-defined tier instances for quick lookup by level name.
# WHY: A dictionary provides O(1) lookup and avoids repeated construction.
USER_TIERS: dict[str, UserTier] = {
    "basic": UserTier(
        level="basic",
        context_window=4000,
        default_mode="simple",
        daily_premium_limit=3,
    ),
    "pro": UserTier(
        level="pro",
        context_window=8000,
        default_mode="pipeline",
        daily_premium_limit=10,
    ),
    "enterprise": UserTier(
        level="enterprise",
        context_window=16000,
        default_mode="self_rag",
        daily_premium_limit=-1,  # -1 = unlimited Premium queries
    ),
}
