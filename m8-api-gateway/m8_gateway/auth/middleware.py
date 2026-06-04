"""FastAPI authentication and rate-limiting middleware dependencies.

WHAT: Two FastAPI dependency functions that together enforce API key
      authentication (via Bearer token) and per-tier rate limiting.
      Both are designed to be used with Depends() in route handlers.

      get_api_key:
          Extracts the Bearer token from the Authorization header,
          validates it against the KeyManager database, and returns
          an APIKey object on success. Raises HTTPException(401) for
          missing, malformed, or revoked keys.

      check_rate_limit:
          Depends on get_api_key (receives the APIKey automatically).
          Checks the rate limiter for the key's prefix + tier combination.
          Raises HTTPException(429) if the limit is exceeded. Returns
          True to signal the route can proceed.

WHY: Using FastAPI's dependency injection system (Depends) keeps auth
     logic decoupled from route handlers. Each route simply declares
     `api_key: APIKey = Depends(get_api_key)` and FastAPI handles the
     rest. This pattern enables:
     - Centralized auth logic (one place to change, audit, or test).
     - Composability (check_rate_limit depends on get_api_key).
     - Testability (dependencies can be overridden in tests).
     - OpenAPI auto-documentation (each dependency adds to the schema).
"""

from fastapi import Depends, HTTPException, Request

from m8_gateway.auth.key_manager import APIKey, KeyManager
from m8_gateway.rate_limit.limiter import RateLimiter


async def get_api_key(request: Request) -> APIKey:
    """FastAPI dependency: extract Bearer token, validate, return APIKey.

    WHAT: Reads the Authorization header from the incoming request,
          strips the "Bearer " prefix, and validates the remaining
          token against the KeyManager. On success, touches the key's
          last_used_at timestamp and returns the APIKey object.

    WHY: This is the single entry point for all authenticated routes.
         No route handler needs to know how key validation works —
         they just declare this dependency and receive an APIKey.

    Args:
        request: The FastAPI Request object, used to access the
                 Authorization header and app.state components.

    Returns:
        APIKey: The validated key's metadata dataclass.

    Raises:
        HTTPException(401): If the Authorization header is missing,
                            malformed (not a Bearer token), or the
                            key is invalid/revoked.
    """
    # Extract the Authorization header; must start with "Bearer "
    auth_header: str = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. "
                   "Expected format: 'Bearer sk-m8-...'",
        )

    # Strip "Bearer " prefix (7 chars) to get the raw key
    raw_key: str = auth_header[7:]

    # Retrieve the KeyManager singleton from app state
    key_manager: KeyManager = request.app.state.key_manager
    api_key: APIKey | None = await key_manager.validate_key(raw_key)

    if api_key is None:
        # Key not found in DB or has been revoked
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked API key",
        )

    # Update last_used_at timestamp for key rotation policies
    await key_manager.touch_key(api_key.key_prefix)

    return api_key


async def check_rate_limit(
    request: Request,
    api_key: APIKey = Depends(get_api_key),
) -> bool:
    """FastAPI dependency: check rate limit for this key. Raises 429 if exceeded.

    WHAT: Depends on get_api_key to receive the validated APIKey.
          Queries the RateLimiter using the key's prefix and tier.
          If the rate limit for this tier has been exceeded, raises
          HTTPException(429). Otherwise, returns True.

    WHY: Rate limiting must happen AFTER authentication (so we know
         the tier) but BEFORE the route handler runs (so we don't
         waste resources on over-limit requests). Using Depends
         chains allows this ordering naturally.

    Args:
        request: The FastAPI Request object for accessing app.state.
        api_key: The validated APIKey (injected by get_api_key dependency).

    Returns:
        True if the request is within the rate limit.

    Raises:
        HTTPException(429): If the key has exceeded its tier's rate limit.
    """
    # Retrieve the RateLimiter singleton from app state
    limiter: RateLimiter = request.app.state.limiter

    # Check if this key is within its rate limit for the current window
    if not limiter.check(api_key.key_prefix, api_key.tier):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please retry after the current "
                   "window resets (60 seconds from first request).",
        )

    return True
