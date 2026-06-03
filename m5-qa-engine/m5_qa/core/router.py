"""
M5 QA Engine — Mode Router.

Determines the pipeline mode for each query based on:
  1. User tier level (basic/pro/enterprise) → default mode
  2. Premium quota availability → temporary upgrade to self_rag

The router is stateless — quota state is managed externally by the
quota_manager (conversation manager), which is injected at call time.
"""

from m5_qa.core.tier import UserTier, USER_TIERS


class ModeRouter:
    """
    WHAT: Routes a user query to the appropriate pipeline mode.
    WHY: The system supports three pipeline modes (simple, pipeline, self_rag)
         that differ in cost, latency, and answer quality. The router decides
         which mode to use based on the user's tier and Premium quota status.

    Mode selection logic:
      1. Look up the user's tier → get default_mode
      2. Check Premium quota → if available, upgrade to "self_rag" and consume one credit
      3. Unknown tier levels fall back to "basic"

    The router itself is stateless — it does not store quota data.
    The quota_manager is injected at call time (adhering to dependency inversion).
    """

    def select_mode(
        self,
        user_id: str | None,
        tier_level: str,
        quota_manager=None,
    ) -> tuple[str, UserTier]:
        """
        WHAT: Determine the pipeline mode for a single query.
        WHY: This is the single decision point for mode routing.
             All callers (engine.py, API handlers) go through this method.

        Args:
          user_id: User identifier, used for quota lookup. May be None for anonymous.
          tier_level: Tier level string ("basic", "pro", "enterprise").
          quota_manager: Object with can_use(user_id) → bool and consume(user_id) → bool.
                         If None, Premium upgrades are disabled.

        Returns:
          Tuple of (mode_string, effective_tier):
            - Normally: tier's default_mode (e.g., "simple", "pipeline", "self_rag")
            - Premium available: "self_rag" (temporary upgrade for one query)
            - Unknown tier: falls back to "basic" tier with "simple" mode
        """
        # Resolve tier level to a UserTier instance, falling back to "basic"
        # for unknown tier strings (graceful degradation)
        tier = USER_TIERS.get(tier_level, USER_TIERS["basic"])

        # Check if the user has Premium quota available
        # Premium upgrades the mode to "self_rag" regardless of the user's
        # default tier, consuming one credit
        if user_id and quota_manager and quota_manager.can_use(user_id):
            quota_manager.consume(user_id)
            return ("self_rag", tier)

        # No Premium available — use the tier's default mode
        return (tier.default_mode, tier)
