"""In-memory sliding window rate limiter.

WHAT: Tracks request timestamps per API key using a Python dict.
      Each check() call removes expired timestamps (>window_seconds old),
      then verifies the count is under the tier's limit.

WHY: In-memory is the simplest correct approach for Personal and
     Enterprise deployments — zero external dependencies, sub-microsecond
     latency. For SaaS multi-instance deployments, use RedisRateLimiter
     instead (persistent, shared state across instances).
"""

import time

from m8_gateway.rate_limit.base import BaseRateLimiter

# Default rate limits per tier (requests per minute)
# -1 means unlimited
DEFAULT_RATE_LIMITS = {
    "basic":      30,
    "pro":       120,
    "enterprise": -1,
}


class InMemoryRateLimiter(BaseRateLimiter):
    """Per-key sliding window rate limiter (in-memory).

    WHAT: Tracks request timestamps per API key (keyed by key_prefix).
          Each check() call removes expired timestamps (>window_seconds old),
          then verifies the count is under the tier's limit. Lazy cleanup
          keeps the timestamp lists small without a background thread.

    WHY: In-memory sliding window is the simplest correct approach for
         Personal mode. No Redis dependency. Restarting the server resets
         all counters — acceptable for Personal/Enterprise, use
         RedisRateLimiter for SaaS.

    RESTART BEHAVIOR: All rate limit counters are stored in-memory and
    reset to zero on server restart. For SaaS deployments requiring
    persistent rate limiting across restarts, use RedisRateLimiter.
    """

    def __init__(
        self,
        rate_limits: dict[str, int] | None = None,
        window_seconds: int = 60,
    ):
        """Initialize the in-memory rate limiter.

        Args:
            rate_limits: Per-tier limits (requests per window). -1 = unlimited.
                         Defaults to DEFAULT_RATE_LIMITS.
            window_seconds: Sliding window size in seconds (default: 60).
        """
        self._limits: dict[str, int] = rate_limits or DEFAULT_RATE_LIMITS
        self._windows: dict[str, list[float]] = {}  # key_prefix → timestamps
        self._window_seconds = window_seconds

    def check(self, key_prefix: str, tier: str) -> bool:
        """Return True if request is within rate limit.

        WHAT: Counts requests in the last window_seconds seconds.
              Expired timestamps are cleaned up lazily on each check.
              Unlimited tiers (limit=-1) skip all counting.

        Args:
            key_prefix: Unique identifier for the rate-limited entity.
            tier: User tier name ("basic", "pro", "enterprise").

        Returns:
            True if allowed, False if rate limit exceeded.
        """
        limit: int = self._limits.get(tier, DEFAULT_RATE_LIMITS.get(tier, 30))
        if limit == -1:
            return True  # enterprise: unlimited

        now: float = time.time()
        window_start: float = now - float(self._window_seconds)

        # Get or create the list of timestamps for this key
        if key_prefix not in self._windows:
            self._windows[key_prefix] = []
        timestamps: list[float] = self._windows[key_prefix]

        # Lazy cleanup: remove timestamps older than the window
        # This keeps the list small even for high-traffic keys
        self._windows[key_prefix] = [t for t in timestamps if t > window_start]

        # Check if adding one more request would exceed the limit
        if len(self._windows[key_prefix]) >= limit:
            return False

        # Record this request
        self._windows[key_prefix].append(now)
        return True

    def get_usage(self, key_prefix: str) -> int:
        """Return current request count in the sliding window (for monitoring)."""
        if key_prefix not in self._windows:
            return 0
        window_start = time.time() - float(self._window_seconds)
        self._windows[key_prefix] = [
            t for t in self._windows[key_prefix] if t > window_start
        ]
        return len(self._windows[key_prefix])

    def health_check(self) -> bool:
        """In-memory limiter is always healthy — no external dependency."""
        return True

    def close(self) -> None:
        """No resources to release — no-op."""
        pass
