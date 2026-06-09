"""Rate limit subpackage for M8 API Gateway.

WHAT: Provides all rate limiter implementations and factory function.
      InMemoryRateLimiter for Personal/Enterprise, RedisRateLimiter for SaaS.

WHY: Separate namespace keeps the limiter isolated from auth and routing
     concerns. Backends are swappable via DI without touching callers.
"""

from m8_gateway.rate_limit.base import BaseRateLimiter
from m8_gateway.rate_limit.limiter import InMemoryRateLimiter

__all__ = [
    "BaseRateLimiter",
    "InMemoryRateLimiter",
    "RedisRateLimiter",
    "create_rate_limiter",
]


def create_rate_limiter(config):
    """Factory: select and construct the appropriate rate limiter.

    WHAT: Reads config.rate_limit_backend and returns the matching
          BaseRateLimiter implementation. For "redis" backend, attempts
          to create a Redis client; falls back to InMemoryRateLimiter
          if Redis is unavailable (unless strict_mode=True).

    WHY: Factory isolates backend selection to a single point. Callers
         (app.py, tests) don't know which backend is active.

    NOTE: Redis imports are deferred to avoid ImportError when the redis
          package is not installed.
    """
    from m8_gateway.core.config import GatewayConfig
    from m8_gateway.rate_limit.redis_client import create_redis_client

    limits = config.rate_limits
    redis_cfg = config.rate_limit_redis

    if config.rate_limit_backend == "redis":
        redis_client = create_redis_client(
            host=redis_cfg.host,
            port=redis_cfg.port,
            db=redis_cfg.db,
            password=redis_cfg.password or None,
            max_connections=redis_cfg.max_connections,
        )
        if redis_client is not None:
            from m8_gateway.rate_limit.redis_limiter import RedisRateLimiter
            return RedisRateLimiter(
                redis_client=redis_client,
                rate_limits=limits,
                strict_mode=redis_cfg.strict_mode,
                window_seconds=redis_cfg.window_seconds,
            )

        if redis_cfg.strict_mode:
            raise RuntimeError(
                "Redis required but unavailable (strict_mode=true). "
                "Check Redis connection settings or set strict_mode=false "
                "to fall back to in-memory rate limiting."
            )
        # Redis unavailable + non-strict → fall through to in-memory

    return InMemoryRateLimiter(
        rate_limits=limits,
        window_seconds=redis_cfg.window_seconds,
    )
