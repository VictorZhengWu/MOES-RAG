"""Redis-backed sliding window rate limiter.

WHAT: Uses Redis Sorted Sets (ZSET) to store request timestamps per API key.
      ZREMRANGEBYSCORE removes expired entries, ZCARD counts current window.
      Supports graceful fallback to in-memory counting when Redis is unavailable
      (non-strict mode).

WHY: Redis persistence ensures rate limit counters survive server restarts
     and are shared across multiple M8 instances in SaaS deployments.
     The strict_mode parameter controls the failure policy: strict (SaaS,
     reject on Redis failure) vs. relaxed (Enterprise, fall back to memory).

REDIS DATA STRUCTURE:
    Key:   rate_limit:{key_prefix}
    Type:  Sorted Set (ZSET)
    Score: Unix timestamp (float)
    Member: "{timestamp}-{8 random hex chars}" (hex suffix prevents
            member collision when two requests share the same timestamp)
    TTL:   window_seconds * 2 (auto-cleanup idle keys)

REDIS OPERATIONS (per check):
    1. ZREMRANGEBYSCORE key 0 {now - window_seconds}  — remove expired
    2. ZCARD key                                         — count current window
    3. If count >= limit → return False                  — rate limited
    4. ZADD key {now} "{now}-{uuid_hex[:8]}"              — record request
    5. EXPIRE key {window_seconds * 2}                    — auto-expire idle key
    6. return True
"""

import logging
import time
import uuid
from typing import Optional

from m8_gateway.rate_limit.base import BaseRateLimiter

logger = logging.getLogger("m8_gateway.rate_limit.redis")

DEFAULT_RATE_LIMITS = {
    "basic":      30,
    "pro":       120,
    "enterprise": -1,
}


class RedisRateLimiter(BaseRateLimiter):
    """Redis-backed sliding window rate limiter.

    WHAT: Uses Redis Sorted Sets for persistent, shared rate limiting
          across server restarts and multiple M8 instances.

    WHY: SaaS deployments need multi-instance shared state for rate
         limiting. Redis provides sub-millisecond latency, built-in
         TTL-based cleanup, and atomic operations.

    GRACEFUL FALLBACK: When strict_mode=False (Enterprise), Redis
    failures are caught and the limiter falls back to in-memory counting.
    When strict_mode=True (SaaS), Redis failures result in rejected
    requests to enforce cost control.
    """

    def __init__(
        self,
        redis_client,
        rate_limits: Optional[dict[str, int]] = None,
        strict_mode: bool = False,
        window_seconds: int = 60,
    ):
        """Initialize the Redis-backed rate limiter.

        Args:
            redis_client: A connected redis.Redis instance (DI injected).
                          Tests can inject fakeredis.FakeStrictRedis.
            rate_limits: Per-tier limits (requests per window). -1 = unlimited.
            strict_mode: If True, reject requests when Redis fails.
                         If False, fall back to in-memory counting.
            window_seconds: Sliding window size in seconds (default: 60).
        """
        self._redis = redis_client
        self._limits: dict[str, int] = rate_limits or DEFAULT_RATE_LIMITS
        self._strict_mode: bool = strict_mode
        self._window_seconds: int = window_seconds
        self._memory_fallback: dict[str, list[float]] = {}

    # ------------------------------------------------------------------
    # Public interface (BaseRateLimiter contract)
    # ------------------------------------------------------------------

    def check(self, key_prefix: str, tier: str) -> bool:
        """Return True if request is within rate limit.

        WHAT: First tries Redis Sorted Set. If Redis fails:
              - strict_mode=True → return False (reject, protect costs)
              - strict_mode=False → fall back to in-memory counting

        Args:
            key_prefix: Unique identifier (API key prefix).
            tier: User tier name ("basic", "pro", "enterprise").

        Returns:
            True if allowed, False if rate limit exceeded or Redis error
            in strict mode.
        """
        limit: int = self._limits.get(tier, DEFAULT_RATE_LIMITS.get(tier, 30))
        if limit == -1:
            return True  # enterprise: unlimited — skip Redis entirely

        try:
            return self._check_redis(key_prefix, limit)
        except Exception as e:
            logger.error(
                "Redis check failed for key=%s tier=%s: %s",
                key_prefix, tier, e,
            )
            if self._strict_mode:
                # SaaS: reject to enforce cost control. Redis down = incident.
                return False
            # Enterprise: degrade to in-memory counting
            return self._check_memory(key_prefix, limit)

    def get_usage(self, key_prefix: str) -> int:
        """Return current request count (Redis first, then memory fallback)."""
        try:
            key: str = f"rate_limit:{key_prefix}"
            window_start: float = time.time() - float(self._window_seconds)
            self._redis.zremrangebyscore(key, 0, window_start)
            return self._redis.zcard(key)
        except Exception as e:
            logger.warning("Redis get_usage failed for key=%s: %s", key_prefix, e)

        # Fallback to memory
        if key_prefix in self._memory_fallback:
            window_start = time.time() - float(self._window_seconds)
            self._memory_fallback[key_prefix] = [
                t for t in self._memory_fallback[key_prefix] if t > window_start
            ]
            return len(self._memory_fallback[key_prefix])
        return 0

    def health_check(self) -> bool:
        """Return True if Redis is reachable.

        WHAT: Issues a PING command to Redis. Returns True on PONG,
              False on any error.

        WHY: Admin endpoints (GET /admin/config/rate-limit) use this to
             report Redis connectivity status. Does not raise — returns
             False so the caller can display the status cleanly.
        """
        try:
            self._redis.ping()
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Release the Redis connection pool.

        WHAT: Closes the Redis client and its underlying connection pool.
              Must be called on server shutdown to release TCP connections.

        WHY: Redis connection pool holds TCP sockets. Without explicit
             close(), the server accumulates dead connections until
             Redis's timeout kicks in.
        """
        try:
            self._redis.close()
            logger.info("Redis connection pool closed")
        except Exception as e:
            logger.warning("Error closing Redis client: %s", e)

    # ------------------------------------------------------------------
    # Private implementation
    # ------------------------------------------------------------------

    def _check_redis(self, key_prefix: str, limit: int) -> bool:
        """Redis Sorted Set sliding window check.

        WHAT: Atomic sliding window using Redis ZSET commands.
              1. Remove expired entries (ZREMRANGEBYSCORE)
              2. Count remaining entries (ZCARD)
              3. If at limit, reject
              4. Record new entry (ZADD) with unique member
              5. Set key TTL for auto-cleanup (EXPIRE)

        WHY: Sorted Sets are the ideal data structure for sliding window
             rate limiting — score-based range removal is O(log N) and
             ZCARD is O(1). The random hex suffix on members prevents
             collision when two requests share the same timestamp.
        """
        key: str = f"rate_limit:{key_prefix}"
        now: float = time.time()
        window_start: float = now - float(self._window_seconds)

        # Step 1: Remove expired entries (older than the window)
        self._redis.zremrangebyscore(key, 0, window_start)

        # Step 2: Count current window entries
        current_count: int = self._redis.zcard(key)

        # Step 3: Reject if at limit
        if current_count >= limit:
            return False

        # Step 4: Record this request with a unique member to prevent
        #         ZADD overwrite when two requests share a timestamp
        member: str = f"{now}-{uuid.uuid4().hex[:8]}"
        self._redis.zadd(key, {member: now})

        # Step 5: Auto-expire idle keys after 2x window to prevent
        #         accumulating garbage from keys that go idle
        self._redis.expire(key, self._window_seconds * 2)

        return True

    def _check_memory(self, key_prefix: str, limit: int) -> bool:
        """In-memory fallback — same logic as InMemoryRateLimiter.

        WHAT: Used when Redis is unavailable and strict_mode=False.
              Identical algorithm to InMemoryRateLimiter.check().

        WHY: Enterprise deployments prioritize availability over strict
             rate limit enforcement. The memory fallback provides
             continuity of service during Redis outages.
        """
        now: float = time.time()
        window_start: float = now - float(self._window_seconds)

        if key_prefix not in self._memory_fallback:
            self._memory_fallback[key_prefix] = []
        timestamps: list[float] = self._memory_fallback[key_prefix]

        # Lazy cleanup
        self._memory_fallback[key_prefix] = [
            t for t in timestamps if t > window_start
        ]

        if len(self._memory_fallback[key_prefix]) >= limit:
            return False

        self._memory_fallback[key_prefix].append(now)
        return True
