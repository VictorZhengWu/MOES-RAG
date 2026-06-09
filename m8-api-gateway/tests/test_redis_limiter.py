"""Tests for RedisRateLimiter using fakeredis (zero external dependency).

WHAT: Verifies Redis-backed sliding window rate limiting: basic flow,
      unlimited tier, sliding window expiry, strict mode behavior,
      non-strict fallback, and health check.

WHY: fakeredis provides a drop-in replacement for redis.Redis that runs
     entirely in-memory. No real Redis server needed. Tests that need
     to simulate Redis failures use unittest.mock.patch on key methods.
"""

from unittest.mock import patch

import pytest

from m8_gateway.rate_limit.redis_limiter import RedisRateLimiter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis():
    """Create a fakeredis.FakeStrictRedis instance for testing.

    WHAT: Provides a fully functional Redis mock. All commands work
          identically to real Redis (Sorted Sets, TTL, key expiry).

    WHY: Tests run without any external process. CI-friendly.
    """
    from fakeredis import FakeStrictRedis
    return FakeStrictRedis()


@pytest.fixture
def redis_limiter(fake_redis):
    """Create a RedisRateLimiter with low limits for easy testing.

    WHAT: default rate limits: basic=2, pro=5, enterprise=-1.
          non-strict mode, 60s window.
    """
    return RedisRateLimiter(
        redis_client=fake_redis,
        rate_limits={"basic": 2, "pro": 5, "enterprise": -1},
        strict_mode=False,
        window_seconds=60,
    )


# ---------------------------------------------------------------------------
# Basic rate limit tests (fakeredis normal flow)
# ---------------------------------------------------------------------------

def test_basic_rate_limit_allows_within_limit(redis_limiter):
    """First 2 requests allowed, 3rd rejected.

    WHAT: Uses fakeredis real Sorted Set operations. Verifies that
          ZADD increments the count and ZCARD returns the correct
          number after ZREMRANGEBYSCORE.
    """
    assert redis_limiter.check("key-001", "basic") is True
    assert redis_limiter.check("key-001", "basic") is True
    # 3rd request exceeds limit of 2
    assert redis_limiter.check("key-001", "basic") is False


def test_basic_rate_limit_different_keys_independent(redis_limiter):
    """Rate limiting is per-key — key-002 is not affected by key-001.

    WHAT: Two different keys should have independent counters.
          key-001 at limit should not block key-002.
    """
    # Saturate key-001
    assert redis_limiter.check("key-001", "basic") is True
    assert redis_limiter.check("key-001", "basic") is True
    assert redis_limiter.check("key-001", "basic") is False

    # key-002 should be unaffected
    assert redis_limiter.check("key-002", "basic") is True
    assert redis_limiter.check("key-002", "basic") is True


def test_unlimited_tier_skips_redis(redis_limiter, fake_redis):
    """Enterprise tier (limit=-1) returns True without touching Redis.

    WHAT: 200 enterprise requests all pass. Verifies that no Redis
          key is created for enterprise tier (skip ZADD entirely).

    WHY: Enterprise tier is unlimited — we should not waste Redis
         memory storing timestamps that are never checked.
    """
    for i in range(200):
        assert redis_limiter.check("ent-key", "enterprise") is True, (
            f"Enterprise request {i+1}/200 should be allowed"
        )

    # Verify no Redis key was created for enterprise tier
    assert fake_redis.exists("rate_limit:ent-key") == 0, (
        "Enterprise tier should not create Redis keys"
    )


def test_get_usage_returns_correct_count(redis_limiter):
    """get_usage() should reflect the number of requests in the current window.

    WHAT: After 2 basic requests, get_usage should return 2.
    """
    redis_limiter.check("usage-key", "basic")
    redis_limiter.check("usage-key", "basic")
    assert redis_limiter.get_usage("usage-key") == 2


def test_get_usage_returns_zero_for_unknown_key(redis_limiter):
    """get_usage() for a key with no requests should return 0."""
    assert redis_limiter.get_usage("no-such-key") == 0


# ---------------------------------------------------------------------------
# Sliding window expiry test (mock approach)
# ---------------------------------------------------------------------------

def test_sliding_window_expiry():
    """Simulate window expiry by mocking zremrangebyscore+zcard.

    WHAT: Sets up a scenario where ZCARD returns 1 after cleanup
          (simulating 1 old request still in window), then mocks
          ZCARD to return 0 (simulating window sliding past all
          entries). The request should be allowed after expiry.

    WHY: fakeredis does not support real time advancement. Mocking
         zremrangebyscore+zcard is the cleanest way to simulate
         the "all entries expired" state without sleep().

    APPROACH:
        1. First request: real ZCARD = 0 → allowed
        2. Second request: real ZCARD = 1 → allowed
        3. Third request: mock ZCARD = 0 → simulated expiry → allowed
    """
    from fakeredis import FakeStrictRedis

    redis = FakeStrictRedis()
    limiter = RedisRateLimiter(
        redis_client=redis,
        rate_limits={"basic": 2},
    )

    # First 2 requests fill the window
    assert limiter.check("expire-key", "basic") is True
    assert limiter.check("expire-key", "basic") is True

    # 3rd: exceed limit check
    assert limiter.check("expire-key", "basic") is False

    # Simulate expiry: ZCARD returns 0 (all entries beyond window)
    with (patch.object(redis, 'zremrangebyscore', return_value=2),
          patch.object(redis, 'zcard', return_value=0)):
        assert limiter.check("expire-key", "basic") is True, (
            "After all entries expire, requests should be allowed again"
        )


# ---------------------------------------------------------------------------
# Strict mode tests (simulate Redis failure)
# ---------------------------------------------------------------------------

def test_strict_mode_rejects_on_redis_error():
    """strict_mode=True: Redis ConnectionError → return False.

    WHAT: When strict_mode is True and Redis raises ConnectionError,
          the limiter must reject the request to protect cost control.

    WHY: SaaS deployments rely on Redis for multi-instance shared state.
         If Redis is down, the system should fail closed (reject) rather
         than fail open (allow uncontrolled traffic).
    """
    from fakeredis import FakeStrictRedis

    redis = FakeStrictRedis()
    limiter = RedisRateLimiter(
        redis_client=redis,
        rate_limits={"basic": 30},
        strict_mode=True,
    )

    with patch.object(redis, 'zcard', side_effect=ConnectionError("Redis down")):
        result = limiter.check("strict-key", "basic")
        assert result is False, (
            "strict_mode=True must reject when Redis is unavailable"
        )


def test_non_strict_fallback_on_redis_error():
    """strict_mode=False: Redis ConnectionError → fall back to memory.

    WHAT: When strict_mode is False and Redis fails, the limiter
          uses in-memory counting as fallback. Service continuity
          is prioritized over strict rate limit enforcement.

    WHY: Enterprise deployments prioritize availability. A temporary
         Redis outage should not block all API traffic.
    """
    from fakeredis import FakeStrictRedis

    redis = FakeStrictRedis()
    limiter = RedisRateLimiter(
        redis_client=redis,
        rate_limits={"basic": 2},
        strict_mode=False,
    )

    # All Redis operations fail — fallback to memory
    with patch.object(redis, 'zremrangebyscore', side_effect=ConnectionError("Redis down")):
        # Memory fallback allows 2 requests per window
        assert limiter.check("fb-key", "basic") is True
        assert limiter.check("fb-key", "basic") is True
        # 3rd should be rejected by in-memory counter
        assert limiter.check("fb-key", "basic") is False


def test_strict_mode_rejects_on_zadd_error():
    """Even ZADD failure should cause strict_mode reject.

    WHAT: If zremrangebyscore succeeds but zadd fails (partial Redis
          outage), strict_mode should still reject. Any Redis error
          is treated as a failure.
    """
    from fakeredis import FakeStrictRedis

    redis = FakeStrictRedis()
    limiter = RedisRateLimiter(
        redis_client=redis,
        rate_limits={"basic": 30},
        strict_mode=True,
    )

    with patch.object(redis, 'zadd', side_effect=ConnectionError("Redis write error")):
        result = limiter.check("partial-key", "basic")
        assert result is False, (
            "Any Redis error in strict_mode should reject"
        )


# ---------------------------------------------------------------------------
# Health check tests
# ---------------------------------------------------------------------------

def test_health_check_healthy(fake_redis):
    """health_check() returns True when Redis responds to PING.

    WHAT: fakeredis always responds to PING correctly.
    """
    limiter = RedisRateLimiter(redis_client=fake_redis)
    assert limiter.health_check() is True


def test_health_check_unhealthy():
    """health_check() returns False when Redis is unreachable.

    WHAT: Simulated PING failure should return False, not raise.
          Admin endpoints call this to display connectivity status.
    """
    from fakeredis import FakeStrictRedis

    redis = FakeStrictRedis()

    with patch.object(redis, 'ping', side_effect=ConnectionError("Redis down")):
        limiter = RedisRateLimiter(redis_client=redis)
        assert limiter.health_check() is False, (
            "health_check should return False on Redis failure, not raise"
        )


# ---------------------------------------------------------------------------
# Close test
# ---------------------------------------------------------------------------

def test_close_releases_redis_connection(fake_redis):
    """close() should call redis.close() to release the connection pool.

    WHAT: Verifies that RedisRateLimiter.close() delegates to the
          underlying Redis client's close() method.
    """
    limiter = RedisRateLimiter(redis_client=fake_redis)

    with patch.object(fake_redis, 'close') as mock_close:
        limiter.close()
        mock_close.assert_called_once()
