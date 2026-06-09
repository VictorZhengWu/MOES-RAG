# WHAT: Unit tests for InMemoryRateLimiter (sliding window, tiered limits).
# WHY: Verifies that the rate limiter correctly allows requests under the
#      limit, rejects requests over the limit, and handles the unlimited
#      enterprise tier. Also verifies the factory function selects the
#      correct backend based on config.

import time

import pytest

from m8_gateway.rate_limit.base import BaseRateLimiter
from m8_gateway.rate_limit.limiter import InMemoryRateLimiter


def test_under_limit_allowed():
    """Basic key, 1 request within 30/min limit — should return True."""
    limiter = InMemoryRateLimiter()
    result: bool = limiter.check("test-key-001", "basic")
    assert result is True, (
        "First request for a basic-tier key should be allowed (1 < 30)"
    )


def test_over_limit_rejected():
    """Basic key (30/min), fire exactly 30 requests (all True),
    then 31st returns False. Verifies the rate limit boundary.

    WHAT: Fires 30 rapid requests (the limit), confirms all pass,
    then fires the 31st which should be rejected.
    WHY: Sliding window's boundary condition is the most common
    source of off-by-one bugs in rate limiter implementations.
    """
    limiter = InMemoryRateLimiter()
    key = "test-key-002"
    tier = "basic"

    # Fire exactly 30 requests — the limit
    for i in range(30):
        result = limiter.check(key, tier)
        assert result is True, (
            f"Request {i + 1}/30 should be allowed (within limit of 30)"
        )

    # 31st request should be rejected
    result_31 = limiter.check(key, tier)
    assert result_31 is False, (
        "31st request should be rejected (exceeds 30/min limit)"
    )


def test_enterprise_unlimited():
    """Enterprise key, fire 200 requests — all should return True.
    -1 means unlimited.

    WHAT: Sends 200 requests with an enterprise-tier key.
    WHY: Enterprise tier has limit=-1 (unlimited), which requires
    a dedicated code path in check(). This test ensures that path
    works correctly without accumulating timestamps unnecessarily.
    """
    limiter = InMemoryRateLimiter()
    key = "test-key-003"
    tier = "enterprise"

    for i in range(200):
        result = limiter.check(key, tier)
        assert result is True, (
            f"Enterprise request {i + 1}/200 should be allowed (unlimited)"
        )

    # Verify that enterprise key does NOT accumulate timestamps
    # (get_usage should return 0 since we skip recording for unlimited)
    usage = limiter.get_usage(key)
    assert usage == 0, (
        f"Enterprise key should have 0 usage (unlimited), got {usage}"
    )


def test_in_memory_limiter_is_base_limiter():
    """InMemoryRateLimiter must be an instance of BaseRateLimiter.

    WHY: Route handlers and middleware depend on BaseRateLimiter as the
         type annotation. This test ensures the class hierarchy is correct
         after the refactoring.
    """
    limiter = InMemoryRateLimiter()
    assert isinstance(limiter, BaseRateLimiter), (
        "InMemoryRateLimiter must inherit from BaseRateLimiter"
    )


def test_in_memory_limiter_custom_window():
    """Verify window_seconds parameter is respected.

    WHAT: Creates a limiter with window_seconds=120 and verifies
          that the check rejects with the extended window.
    """
    limiter = InMemoryRateLimiter(
        rate_limits={"basic": 2},
        window_seconds=120,
    )
    # 2 requests allowed, 3rd rejected
    assert limiter.check("w1", "basic") is True
    assert limiter.check("w1", "basic") is True
    assert limiter.check("w1", "basic") is False


def test_in_memory_limiter_close_is_noop():
    """close() should not raise — InMemoryRateLimiter has no resources."""
    limiter = InMemoryRateLimiter()
    limiter.close()  # Should not raise


def test_in_memory_limiter_health_check():
    """health_check() should always return True — no external dependency."""
    limiter = InMemoryRateLimiter()
    assert limiter.health_check() is True


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------

def test_factory_memory_backend():
    """Factory with memory backend must return InMemoryRateLimiter.

    WHY: Verifies that create_rate_limiter correctly dispatches to
         InMemoryRateLimiter when backend is "memory".
    """
    from m8_gateway.core.config import GatewayConfig
    from m8_gateway.rate_limit import create_rate_limiter

    config = GatewayConfig(
        deployment_mode="personal",
        rate_limit_backend="memory",
    )
    limiter = create_rate_limiter(config)
    assert isinstance(limiter, InMemoryRateLimiter), (
        "create_rate_limiter must return InMemoryRateLimiter for backend='memory'"
    )


def test_factory_with_auto_backend_personal():
    """Factory with auto backend + personal mode must return InMemoryRateLimiter.

    WHY: Verifies the auto-selection logic in the factory. Personal mode
         should default to memory even without explicit backend setting.
    """
    from m8_gateway.core.config import GatewayConfig
    from m8_gateway.rate_limit import create_rate_limiter

    config = GatewayConfig(
        deployment_mode="personal",
        rate_limit_backend="auto",
    )
    config._resolve_rate_limit_backend()  # Simulate __post_init__
    limiter = create_rate_limiter(config)
    assert isinstance(limiter, InMemoryRateLimiter), (
        "create_rate_limiter must return InMemoryRateLimiter for personal + auto"
    )
