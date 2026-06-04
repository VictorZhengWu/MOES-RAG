"""Tests for M8 API Gateway configuration.

WHAT: Verify GatewayConfig dataclass behavior across deployment modes.
WHY: Configuration is the foundation — wrong rate limits cause either
     blocked legitimate traffic or unbounded cost in SaaS deployments.
"""

import pytest
from m8_gateway.core.config import GatewayConfig


def test_default_config():
    """WHAT: Verify default config uses personal mode with lenient rate limits.

    WHY: Personal mode is the default (single user, no contention),
         so rate limits should be generous.
    """
    cfg = GatewayConfig()
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8000
    assert cfg.deployment_mode == "personal"
    assert cfg.rate_limits == {"basic": 100, "pro": -1, "enterprise": -1}


def test_saas_config():
    """WHAT: Verify SaaS deployment mode applies strict rate limits.

    WHY: SaaS is multi-tenant — each tenant's usage must be bounded
         for cost control and fair resource sharing.
    """
    cfg = GatewayConfig(deployment_mode="saas")
    assert cfg.deployment_mode == "saas"
    assert cfg.rate_limits == {"basic": 30, "pro": 120, "enterprise": -1}


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
