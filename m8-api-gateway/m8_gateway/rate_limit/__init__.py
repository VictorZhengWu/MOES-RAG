"""Rate limit subpackage for M8 API Gateway.

WHAT: Provides all rate limiter implementations and factory function.
      InMemoryRateLimiter for Personal/Enterprise, RedisRateLimiter for SaaS.

WHY: Separate namespace keeps the limiter isolated from auth and routing
     concerns. Backends are swappable via DI without touching callers.
"""

from m8_gateway.rate_limit.base import BaseRateLimiter

__all__ = [
    "BaseRateLimiter",
    "InMemoryRateLimiter",
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

    NOTE: Imports are deferred to avoid circular dependencies and to
          allow the package to be imported even when redis is not installed.
    """
    from m8_gateway.core.config import GatewayConfig
    from m8_gateway.rate_limit.redis_client import create_redis_client

    limits = config.rate_limits if isinstance(config, GatewayConfig) else config.get("rate_limits", {})
    redis_cfg = config.rate_limit_redis if isinstance(config, GatewayConfig) else config.get("rate_limit_redis", None)

    if hasattr(config, 'rate_limit_backend') and config.rate_limit_backend == "redis":
        if redis_cfg is None:
            raise RuntimeError("rate_limit_backend='redis' but rate_limit_redis config is missing")

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

    # Default: in-memory limiter
    window_seconds = redis_cfg.window_seconds if redis_cfg else 60
    from m8_gateway.rate_limit.limiter import RateLimiter
    return RateLimiter(rate_limits=limits)
