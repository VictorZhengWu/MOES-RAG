import time

# Default rate limits per tier (requests per minute)
# -1 means unlimited
DEFAULT_RATE_LIMITS = {
    "basic":      30,
    "pro":       120,
    "enterprise": -1,
}


class RateLimiter:
    """Per-key sliding window rate limiter (in-memory).

    WHAT: Tracks request timestamps per API key (keyed by key_prefix).
    Each check() call removes expired timestamps (>60s old), then
    verifies the count is under the tier's limit.

    WHY: In-memory sliding window is the simplest correct approach for
    Personal mode. No Redis dependency. Restarting the server resets
    all counters — acceptable for Personal/Enterprise, needs Redis in
    Phase 3 SaaS deployment.
    """

    def __init__(self, rate_limits: dict[str, int] | None = None):
        self._limits: dict[str, int] = rate_limits or DEFAULT_RATE_LIMITS
        self._windows: dict[str, list[float]] = {}  # key_prefix → timestamps

    def check(self, key_prefix: str, tier: str) -> bool:
        """Return True if request is within rate limit.

        Sliding window: count requests in the last 60 seconds.
        Expired timestamps are cleaned up on each check (lazy cleanup).
        """
        limit: int = self._limits.get(tier, DEFAULT_RATE_LIMITS.get(tier, 30))
        if limit == -1:
            return True  # enterprise: unlimited

        now: float = time.time()
        window_start: float = now - 60.0  # 1-minute sliding window

        # Get or create the list of timestamps for this key
        if key_prefix not in self._windows:
            self._windows[key_prefix] = []
        timestamps: list[float] = self._windows[key_prefix]

        # Lazy cleanup: remove timestamps older than 60 seconds
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
        window_start = time.time() - 60.0
        self._windows[key_prefix] = [t for t in self._windows[key_prefix] if t > window_start]
        return len(self._windows[key_prefix])
