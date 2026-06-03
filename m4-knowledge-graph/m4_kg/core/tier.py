"""
M4 Knowledge Graph Engine — User Tier module.

Defines user tier levels that control query depth, entity limits, and
cross-reference capabilities.

WHAT:
  - UserTier: Dataclass defining the capabilities and limits for a user tier.
  - USER_TIERS: Dict of predefined tiers (basic, pro, enterprise).

WHY:
  - Different user plans need different resource limits to control cost
    and performance. Basic users get limited traversal and no cross-reference;
    Enterprise users get deep traversal and full cross-reference support.
  - Tiered access allows the system to serve both casual users and
    power users from the same infrastructure.
  - The dict-based lookup (USER_TIERS["basic"]) provides O(1) tier resolution
    from configuration or API requests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UserTier:
    """Defines the capabilities and limits for a user subscription tier.

    WHAT: Stores traversal depth, entity count limits, cross-reference
          enablement, and context token budget for a user tier.
    WHY: Tiered access is a core design principle of M4 — graph traversal
         is free (in-memory), but unlimited traversal could cause latency
         spikes. Tiers cap this in a predictable way.

    Attributes:
        level: Tier identifier string (e.g. "basic", "pro", "enterprise").
        traversal_depth: Maximum BFS hops from seed entities (1-5).
        max_entities: Maximum entity count to return in a single query.
        enable_cross_ref: Whether cross-society reference lookups are allowed.
        context_token_limit: Maximum token budget for the LLM context window
                             when generating augmented responses with KG results.
    """

    level: str = "basic"
    traversal_depth: int = 1
    max_entities: int = 20
    enable_cross_ref: bool = False
    context_token_limit: int = 2048


# WHY: Predefined tiers as module-level constants.
# Each tier object is created once at import time and reused across all
# queries. This avoids repeated allocation and provides a single source
# of truth for tier definitions. The dict key matches the `level` field
# for consistent lookups.
USER_TIERS: dict[str, UserTier] = {
    "basic": UserTier(
        level="basic",
        traversal_depth=1,
        max_entities=20,
        enable_cross_ref=False,
        context_token_limit=2048,
    ),
    "pro": UserTier(
        level="pro",
        traversal_depth=3,
        max_entities=50,
        enable_cross_ref=True,
        context_token_limit=8192,
    ),
    "enterprise": UserTier(
        level="enterprise",
        traversal_depth=5,
        max_entities=200,
        enable_cross_ref=True,
        context_token_limit=32768,
    ),
}
