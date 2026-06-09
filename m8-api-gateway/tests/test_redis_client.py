"""Tests for Redis client factory and BaseRateLimiter.

WHAT: Verify that create_redis_client handles connection failures gracefully
      (returns None, never raises) and that BaseRateLimiter enforces its
      interface contract (cannot instantiate directly).

WHY: The redis client factory is the entry point for Redis connectivity.
     It must never crash the application on connection failure. The base
     class must guarantee that all subclasses implement check/get_usage.
"""

import pytest


# ---------------------------------------------------------------------------
# BaseRateLimiter contract tests
# ---------------------------------------------------------------------------

def test_base_rate_limiter_cannot_instantiate():
    """BaseRateLimiter is abstract — direct instantiation must raise TypeError.

    WHY: Enforces that all rate limiter implementations provide check()
         and get_usage(). Without this, a missing method would only
         fail at runtime when a route handler calls it.
    """
    from m8_gateway.rate_limit.base import BaseRateLimiter

    with pytest.raises(TypeError, match="abstract"):
        BaseRateLimiter()  # type: ignore[abstract]


def test_base_rate_limiter_subclass_must_implement_check():
    """Subclass missing check() must raise TypeError on instantiation.

    WHY: check() is the core rate limiting method. Every limiter must
         implement it. This test verifies ABC enforcement works.
    """
    from m8_gateway.rate_limit.base import BaseRateLimiter

    class IncompleteLimiter(BaseRateLimiter):
        def get_usage(self, key_prefix: str) -> int:
            return 0

    with pytest.raises(TypeError, match="abstract"):
        IncompleteLimiter()


def test_base_rate_limiter_subclass_must_implement_get_usage():
    """Subclass missing get_usage() must raise TypeError on instantiation.

    WHY: get_usage() is needed for monitoring/admin endpoints. ABC
         enforcement ensures it exists on every implementation.
    """
    from m8_gateway.rate_limit.base import BaseRateLimiter

    class IncompleteLimiter(BaseRateLimiter):
        def check(self, key_prefix: str, tier: str) -> bool:
            return True

    with pytest.raises(TypeError, match="abstract"):
        IncompleteLimiter()


def test_base_rate_limiter_valid_subclass_instantiates():
    """A fully implemented subclass must instantiate successfully.

    WHY: Verifies that ABC enforcement doesn't block valid implementations.
         This is a sanity check — if this fails, the ABC rules are too strict.
    """
    from m8_gateway.rate_limit.base import BaseRateLimiter

    class ValidLimiter(BaseRateLimiter):
        def check(self, key_prefix: str, tier: str) -> bool:
            return True

        def get_usage(self, key_prefix: str) -> int:
            return 0

    limiter = ValidLimiter()
    assert limiter.check("test", "basic") is True
    assert limiter.get_usage("test") == 0


def test_base_rate_limiter_close_default_noop():
    """BaseRateLimiter.close() default implementation must be a no-op.

    WHY: InMemoryRateLimiter doesn't need cleanup. The default no-op
         allows app.py shutdown handler to call close() unconditionally
         without checking the limiter type first.
    """
    from m8_gateway.rate_limit.base import BaseRateLimiter

    class SimpleLimiter(BaseRateLimiter):
        def check(self, key_prefix: str, tier: str) -> bool:
            return True

        def get_usage(self, key_prefix: str) -> int:
            return 0

    limiter = SimpleLimiter()
    # Should not raise — default close() is a no-op
    limiter.close()


def test_base_rate_limiter_health_check_default():
    """BaseRateLimiter.health_check() default must return True.

    WHY: InMemoryRateLimiter is always healthy (no external dependency).
         Default True allows unconditional health_check() calls in admin
         endpoints without type checking.
    """
    from m8_gateway.rate_limit.base import BaseRateLimiter

    class SimpleLimiter(BaseRateLimiter):
        def check(self, key_prefix: str, tier: str) -> bool:
            return True

        def get_usage(self, key_prefix: str) -> int:
            return 0

    limiter = SimpleLimiter()
    assert limiter.health_check() is True


# ---------------------------------------------------------------------------
# Redis client factory tests
# ---------------------------------------------------------------------------

def test_create_redis_client_invalid_host_returns_none():
    """Connecting to a non-existent host must return None, not raise.

    WHY: Redis is optional infrastructure. The factory must handle
         connection failures gracefully so the caller can fall back
         to InMemoryRateLimiter. A raised exception would crash startup.
    """
    from m8_gateway.rate_limit.redis_client import create_redis_client

    # Use a short timeout so the test doesn't hang.
    # 255.255.255.255 is a broadcast address that will never respond.
    client = create_redis_client(
        host="255.255.255.255",
        port=6379,
        socket_timeout=1,
        max_connections=5,
    )
    assert client is None, (
        "create_redis_client must return None when Redis is unreachable, "
        "not raise an exception"
    )


def test_create_redis_client_refused_port_returns_none():
    """Connecting to localhost on an unused port must return None.

    WHY: The most common failure mode in development is "Redis not running".
         This must not crash the application.
    """
    from m8_gateway.rate_limit.redis_client import create_redis_client

    # Port 1 is reserved and unlikely to have anything listening.
    client = create_redis_client(
        host="127.0.0.1",
        port=1,
        socket_timeout=1,
        max_connections=5,
    )
    assert client is None, (
        "create_redis_client must return None when connection is refused"
    )
