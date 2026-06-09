"""Tests for M8 API Gateway configuration.

WHAT: Verify GatewayConfig and RedisConfig dataclass behavior across
      deployment modes, including the new rate-limit backend auto-selection.
WHY: Configuration is the foundation — wrong rate limits cause either
     blocked legitimate traffic or unbounded cost in SaaS deployments.
"""

import pytest
from m8_gateway.core.config import GatewayConfig, RedisConfig


# ---------------------------------------------------------------------------
# RedisConfig tests
# ---------------------------------------------------------------------------

def test_redis_config_defaults():
    """WHAT: Verify RedisConfig has sensible defaults for local development.

    WHY: Defaults must be safe for development — localhost, no password,
         reasonable pool size. Production overrides via deploy.yaml.
    """
    cfg = RedisConfig()
    assert cfg.host == "localhost"
    assert cfg.port == 6379
    assert cfg.db == 0
    assert cfg.password == ""
    assert cfg.max_connections == 50
    assert cfg.backend == "memory"  # Default: no Redis required
    assert cfg.strict_mode is False
    assert cfg.window_seconds == 60


def test_redis_config_custom_values():
    """WHAT: Verify all RedisConfig fields accept custom values.

    WHY: Production deployments override every field via deploy.yaml
         or environment variables. Type safety must be preserved.
    """
    cfg = RedisConfig(
        host="redis.internal",
        port=6380,
        db=1,
        password="secret",
        max_connections=100,
        backend="redis",
        strict_mode=True,
        window_seconds=120,
    )
    assert cfg.host == "redis.internal"
    assert cfg.port == 6380
    assert cfg.db == 1
    assert cfg.password == "secret"
    assert cfg.max_connections == 100
    assert cfg.backend == "redis"
    assert cfg.strict_mode is True
    assert cfg.window_seconds == 120


# ---------------------------------------------------------------------------
# GatewayConfig rate-limit backend auto-selection tests
# ---------------------------------------------------------------------------

def test_default_config():
    """WHAT: Verify default config uses personal mode with lenient rate limits.

    WHY: Personal mode is the default (single user, no contention),
         so rate limits should be generous. Backend auto-selects "memory".
    """
    cfg = GatewayConfig()
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8000
    assert cfg.deployment_mode == "personal"
    assert cfg.rate_limits == {"basic": 100, "pro": -1, "enterprise": -1}
    # Auto-selection: personal → memory
    assert cfg.rate_limit_backend == "memory"


def test_saas_config():
    """WHAT: Verify SaaS deployment mode applies strict rate limits
    and auto-selects Redis backend.

    WHY: SaaS is multi-tenant — each tenant's usage must be bounded
         for cost control and fair resource sharing. Redis is required
         for shared state across instances.
    """
    cfg = GatewayConfig(deployment_mode="saas")
    assert cfg.deployment_mode == "saas"
    assert cfg.rate_limits == {"basic": 30, "pro": 120, "enterprise": -1}
    # Auto-selection: saas → redis
    assert cfg.rate_limit_backend == "redis"


def test_enterprise_auto_selects_memory():
    """WHAT: Enterprise deployment mode auto-selects memory backend.

    WHY: Enterprise is single-instance on-premise — no shared state
         needed. In-memory is simpler and has zero dependencies.
    """
    cfg = GatewayConfig(deployment_mode="enterprise")
    assert cfg.rate_limit_backend == "memory"


def test_explicit_backend_overrides_auto_selection():
    """WHAT: Explicitly setting rate_limit_backend must override
    the deployment-mode auto-selection.

    WHY: Administrators must be able to force a specific backend
         regardless of deployment mode. E.g., an Enterprise customer
         who wants Redis for multi-instance HA.
    """
    # Force Redis even in personal mode
    cfg = GatewayConfig(
        deployment_mode="personal",
        rate_limit_backend="redis",
    )
    assert cfg.rate_limit_backend == "redis"

    # Force memory even in SaaS mode
    cfg2 = GatewayConfig(
        deployment_mode="saas",
        rate_limit_backend="memory",
    )
    assert cfg2.rate_limit_backend == "memory"


def test_explicit_rate_limits():
    """WHAT: Verify explicitly provided rate limits are NOT overwritten
    by deployment mode auto-detection.

    WHY: Administrators must be able to override defaults.
         The __post_init__ guard (if not self.rate_limits) ensures
         explicit values are preserved.
    """
    custom_limits = {"basic": 5, "pro": 10, "enterprise": 50}
    cfg = GatewayConfig(
        deployment_mode="saas",
        rate_limits=custom_limits,
    )
    # Explicit custom limits must be preserved, not overridden by mode
    assert cfg.rate_limits == custom_limits
    assert cfg.deployment_mode == "saas"


def test_gateway_config_has_redis_config():
    """WHAT: GatewayConfig must include a RedisConfig instance by default.

    WHY: Even when using memory backend, the RedisConfig fields are
         referenced by admin endpoints (GET /admin/config/rate-limit).
         It must always be present, never None.
    """
    cfg = GatewayConfig()
    assert cfg.rate_limit_redis is not None
    assert isinstance(cfg.rate_limit_redis, RedisConfig)
    assert cfg.rate_limit_redis.host == "localhost"
