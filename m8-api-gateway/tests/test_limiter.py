# WHAT: Unit tests for RateLimiter (sliding window, tiered limits).
# WHY: Verifies that the rate limiter correctly allows requests under the
#      limit, rejects requests over the limit, and handles the unlimited
#      enterprise tier. TDD — tests written before implementation.

import time

from m8_gateway.rate_limit.limiter import RateLimiter


def test_under_limit_allowed():
    """Basic key, 1 request within 30/min limit — should return True."""
    limiter = RateLimiter()
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
    limiter = RateLimiter()
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
    limiter = RateLimiter()
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
