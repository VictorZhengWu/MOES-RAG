"""M8 API Gateway configuration.

WHAT: All runtime parameters for the gateway, including deployment mode
      which controls rate limit defaults.
WHY: Centralized configuration dataclass allows different deployment
     scenarios (personal/enterprise/saas) to auto-configure appropriate
     rate limits while still allowing manual overrides.
"""

from dataclasses import dataclass, field


@dataclass
class GatewayConfig:
    """M8 API Gateway configuration.

    WHAT: All runtime parameters for the gateway, including deployment mode
          which controls rate limit defaults.

    Attributes:
        host: Bind address for uvicorn (default: 0.0.0.0).
        port: Listen port (default: 8000).
        db_path: Path to the SQLite database for API key storage.
        deployment_mode: One of "personal", "enterprise", or "saas".
                         Controls default rate limit presets.
        rate_limits: Per-tier rate limits (requests/minute).
                     -1 means unlimited.
    """
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "./data/m8_gateway.db"
    deployment_mode: str = "personal"  # "personal" | "enterprise" | "saas"
    rate_limits: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Apply rate limits based on deployment mode if not explicitly set.

        WHY: Different deployment scenarios have different traffic patterns.
             Personal mode is lenient (single user, no contention).
             SaaS is strict (multi-tenant cost control).
             Explicit overrides are never overwritten.
        """
        if not self.rate_limits:
            if self.deployment_mode == "personal":
                # Personal: single user, generous limits
                self.rate_limits = {"basic": 100, "pro": -1, "enterprise": -1}
            elif self.deployment_mode == "enterprise":
                # Enterprise: internal team, moderate limits
                self.rate_limits = {"basic": 30, "pro": 120, "enterprise": -1}
            else:  # saas
                # SaaS: multi-tenant, strict cost control
                self.rate_limits = {"basic": 30, "pro": 120, "enterprise": -1}
