"""M8 API Gateway configuration.

WHAT: All runtime parameters for the gateway, including deployment mode
      which controls rate limit defaults, and RedisConfig for Redis-backed
      rate limiting in SaaS mode.
WHY: Centralized configuration dataclass allows different deployment
     scenarios (personal/enterprise/saas) to auto-configure appropriate
     rate limits and storage backends while still allowing manual overrides.
"""

from dataclasses import dataclass, field


@dataclass
class RedisConfig:
    """Redis connection and rate limiting parameters.

    WHAT: All Redis-related configuration for the rate limiter backend.
          All fields are configurable via M7 Admin UI → Storage → Rate Limit tab.

    Attributes:
        host: Redis server hostname or IP (default: localhost).
        port: Redis server port (default: 6379).
        db: Redis database number, 0-15 (default: 0).
        password: Redis AUTH password, empty for no auth (default: "").
        max_connections: Connection pool size, 5-200 (default: 50).
        backend: Rate limiter backend — "memory" or "redis" (default: "memory").
        strict_mode: If True, reject requests when Redis is unavailable.
                     If False, fall back to in-memory counting (default: False).
        window_seconds: Sliding window size in seconds, 10-300 (default: 60).
    """
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    max_connections: int = 50
    backend: str = "memory"  # "memory" | "redis"
    strict_mode: bool = False
    window_seconds: int = 60


@dataclass
class GatewayConfig:
    """M8 API Gateway configuration.

    WHAT: All runtime parameters for the gateway, including deployment mode
          which controls rate limit defaults and rate-limit backend selection.

    Attributes:
        host: Bind address for uvicorn (default: 0.0.0.0).
        port: Listen port (default: 8000).
        db_path: Path to the SQLite database for API key storage.
        deployment_mode: One of "personal", "enterprise", or "saas".
                         Controls default rate limit presets and backend.
        rate_limits: Per-tier rate limits (requests/minute).
                     -1 means unlimited.
        rate_limit_backend: "auto", "memory", or "redis". "auto" selects
                            based on deployment_mode (default: "auto").
        rate_limit_redis: RedisConfig instance for Redis connection params.
    """
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "./data/m8_gateway.db"
    deployment_mode: str = "personal"  # "personal" | "enterprise" | "saas"
    rate_limits: dict[str, int] = field(default_factory=dict)
    rate_limit_backend: str = "auto"  # "auto" | "memory" | "redis"
    rate_limit_redis: RedisConfig = field(default_factory=RedisConfig)

    def __post_init__(self):
        """Apply defaults based on deployment mode.

        WHY: Different deployment scenarios have different traffic patterns
             and infrastructure requirements. Auto-selection reduces
             configuration burden while allowing explicit overrides.
        """
        # Rate limit presets
        if not self.rate_limits:
            if self.deployment_mode == "personal":
                self.rate_limits = {"basic": 100, "pro": -1, "enterprise": -1}
            elif self.deployment_mode == "enterprise":
                self.rate_limits = {"basic": 30, "pro": 120, "enterprise": -1}
            else:  # saas
                self.rate_limits = {"basic": 30, "pro": 120, "enterprise": -1}

        # Rate limit backend auto-selection
        self._resolve_rate_limit_backend()

    def _resolve_rate_limit_backend(self):
        """Auto-select rate limit backend based on deployment mode.

        WHAT: If rate_limit_backend is "auto", selects "redis" for SaaS
              and "memory" for Personal/Enterprise. Explicit values
              ("memory", "redis") are preserved as-is.

        WHY: SaaS needs Redis for multi-instance shared state and
             persistence. Personal/Enterprise are single-instance and
             should have zero external dependencies by default.
        """
        if self.rate_limit_backend == "auto":
            if self.deployment_mode == "saas":
                self.rate_limit_backend = "redis"
            else:
                self.rate_limit_backend = "memory"
