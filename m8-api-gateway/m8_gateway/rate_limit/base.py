"""Abstract base class for rate limiter implementations.

WHAT: Defines the interface that all rate limiters must implement.
      InMemoryRateLimiter and RedisRateLimiter both inherit from this.

WHY: Enables swapping between memory and Redis backends without changing
     a single line in route handlers or middleware. Callers depend on
     BaseRateLimiter, never on concrete implementations.
"""

from abc import ABC, abstractmethod


class BaseRateLimiter(ABC):
    """Abstract base for rate limiter implementations.

    WHAT: Defines the contract: check() and get_usage() must be
          implemented by all subclasses. Provides default no-op
          implementations for close() and health_check() so that
          callers can invoke them unconditionally.

    WHY: Python ABC enforces the interface at instantiation time,
         not at call time — a missing method is caught when the
         object is created, not when a route handler calls it
         in production.
    """

    @abstractmethod
    def check(self, key_prefix: str, tier: str) -> bool:
        """Return True if the request is within the rate limit.

        WHAT: Checks whether a request identified by key_prefix with
              the given tier should be allowed. Records the request
              if allowed.

        Args:
            key_prefix: Unique identifier for the rate-limited entity
                        (typically the API key prefix, e.g. "sk-m8-a1b2c3d4").
            tier: User tier name ("basic", "pro", "enterprise").

        Returns:
            True if the request is allowed, False if rate limit exceeded.
        """
        ...

    @abstractmethod
    def get_usage(self, key_prefix: str) -> int:
        """Return the current request count in the sliding window.

        WHAT: Returns how many requests have been recorded for this
              key_prefix in the current window. Used by monitoring
              and admin endpoints.

        Args:
            key_prefix: The same identifier used in check().

        Returns:
            Integer count of requests in the current sliding window.
        """
        ...

    def close(self) -> None:
        """Release any resources held by this limiter.

        WHAT: Default no-op. RedisRateLimiter overrides this to close
              the Redis connection pool. InMemoryRateLimiter has no
              resources to release.

        WHY: Callers (app.py shutdown handler) can call close()
             unconditionally without type-checking or hasattr().
        """
        pass

    def health_check(self) -> bool:
        """Return True if the limiter backend is healthy.

        WHAT: Default returns True (InMemoryRateLimiter is always healthy).
              RedisRateLimiter overrides this to ping Redis.

        WHY: Admin endpoints can call health_check() unconditionally
             without knowing which backend is active.
        """
        return True
