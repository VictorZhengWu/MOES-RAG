"""Redis client factory for rate limiting.

WHAT: Pure factory function that creates and verifies a Redis connection
      with connection pooling. No global state — caller owns the instance.

WHY: DI-friendly design: tests inject fakeredis, production injects real
     Redis. Each RedisRateLimiter owns its Redis client — lifecycle is
     explicit (caller creates, caller closes).

DEPENDENCY: pip install redis>=5.0.0
"""

import logging
from typing import Optional

try:
    import redis
    from redis import ConnectionPool, Redis
    REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    REDIS_AVAILABLE = False

logger = logging.getLogger("m8_gateway.rate_limit.redis")


def create_redis_client(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    password: str = "",
    max_connections: int = 50,
    socket_timeout: int = 5,
) -> "Optional[Redis]":
    """Create a Redis client with connection pooling. Returns None on failure.

    WHAT: Creates a redis.Redis instance backed by a ConnectionPool.
          Tests the connection with a PING. If anything fails (import,
          connect, auth, ping), logs the error and returns None — never
          raises an exception.

    WHY: Redis is optional infrastructure for rate limiting. The caller
         (create_rate_limiter factory) uses the return value to decide
         whether to use RedisRateLimiter or fall back to InMemoryRateLimiter.
         A raised exception would crash application startup.

    Args:
        host: Redis server hostname or IP (default: localhost).
        port: Redis server port (default: 6379).
        db: Redis database number (default: 0).
        password: Redis AUTH password, empty string for no auth.
        max_connections: Maximum connections in the pool (default: 50).
        socket_timeout: Socket timeout in seconds for connect/read (default: 5).

    Returns:
        A connected redis.Redis instance, or None if connection fails.
    """
    if not REDIS_AVAILABLE:
        logger.warning("redis package not installed — Redis rate limiting unavailable")
        return None

    try:
        pool = ConnectionPool(
            host=host,
            port=port,
            db=db,
            password=password or None,
            max_connections=max_connections,
            decode_responses=True,
            socket_connect_timeout=socket_timeout,
            socket_timeout=socket_timeout,
        )
        client = Redis(connection_pool=pool)

        # Verify the connection works before returning.
        # PING is O(1) and validates auth + connectivity in one round-trip.
        client.ping()
        logger.info("Redis connected: %s:%d (db=%d)", host, port, db)
        return client

    except Exception as e:
        logger.warning("Redis connection failed (%s:%d): %s", host, port, e)
        # Clean up any partially-created pool to avoid leaking file descriptors
        try:
            if 'pool' in locals():
                pool.disconnect()
        except Exception:
            pass
        return None
