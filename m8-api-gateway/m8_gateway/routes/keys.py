"""Admin API key management routes.

WHAT: Admin endpoints for API key lifecycle management: create new keys,
      list existing keys (with optional user filtering), and revoke keys
      by prefix.

      POST /admin/keys         — Generate a new API key (raw key returned once).
      GET  /admin/keys         — List all API keys (only prefixes shown).
      DELETE /admin/keys/{pfx} — Revoke a key by its visible prefix.

WHY: The M8 API Gateway manages its own API keys independently from M5
     user authentication. These admin endpoints provide the CRUD surface
     for key management. Note: these endpoints are NOT secured by API key
     auth — they are intended to be protected at the network level
     (firewall/private subnet) or by a separate admin auth mechanism
     added in a later phase.

Security note:
    These admin routes currently have no authentication. In production,
    they should be placed behind a separate admin auth middleware or
    restricted to localhost/private network access only.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from m8_gateway.auth.key_manager import KeyManager
from m8_gateway.models.schemas import (
    APIKeyCreate,
    APIKeyInfo,
    CreateKeyResponse,
    RevokeKeyResponse,
)

router = APIRouter(tags=["Admin: API Keys"])


@router.post("/admin/keys", response_model=CreateKeyResponse)
async def create_key(
    body: APIKeyCreate,
    request: Request,
):
    """Generate a new API key. The raw key is returned ONCE in the response.

    WHAT: Creates a cryptographically random API key (format: sk-m8-{16hex}),
          stores only its SHA-256 hash in the database, and returns the raw
          key to the caller. This is the ONLY time the full key will be
          visible — it cannot be recovered later.

    WHY: API keys are bearer credentials. The server must never store them
         in plaintext (only the hash is persisted). The raw key must be
         presented to the caller immediately so they can save it. If the
         caller loses the key, a new one must be generated.

    Request body (JSON):
        {"user_id": "user-001", "tier": "pro"}

    Returns:
        CreateKeyResponse with the raw key, its visible prefix, and tier.

    Raises:
        HTTPException(500): If key generation fails (DB error, etc.).
    """
    # Access the KeyManager from app state (set by create_app factory)
    km: KeyManager = request.app.state.key_manager

    # Generate the key — this returns the raw key string
    raw_key: str = await km.generate_key(body.user_id, body.tier)

    return CreateKeyResponse(
        key=raw_key,
        prefix=raw_key[:10],
        tier=body.tier,
    )


@router.get("/admin/keys", response_model=list[APIKeyInfo])
async def list_keys(
    request: Request,
    user_id: str | None = Query(None, description="Filter keys by user ID"),
):
    """List API keys, optionally filtered by user. Only prefixes are shown.

    WHAT: Returns a list of APIKeyInfo objects (prefix + metadata only).
          Full key material and hashes are never included in the response.
          Can be filtered to a specific user via the 'user_id' query parameter.

    WHY: Administrators need visibility into which keys exist, their status,
         and when they were last used — without ever seeing the secret
         material. This enables key auditing and rotation without exposing
         credentials.

    Query params:
        user_id (optional): Filter results to this user's keys only.

    Returns:
        List of APIKeyInfo objects (prefix, user_id, tier, created_at,
        is_active, last_used_at).
    """
    km: KeyManager = request.app.state.key_manager
    keys: list[dict] = await km.list_keys(user_id)

    # Convert the dict list to APIKeyInfo Pydantic models for response
    return [APIKeyInfo(**k) for k in keys]


@router.delete("/admin/keys/{key_prefix}", response_model=RevokeKeyResponse)
async def revoke_key(
    key_prefix: str,
    request: Request,
):
    """Revoke an API key by its visible prefix.

    WHAT: Sets the key's is_active flag to False in the database, immediately
          invalidating it for all future API requests. Already-authenticated
          requests in flight are not affected (we don't maintain a session).

    WHY: Revocation by prefix is the admin-facing operation. The prefix is
         what admins see in the list_keys() output. Since full keys are
         never shown after generation, the prefix is the only identifier
         available for revocation.

    Path params:
        key_prefix: First 10 characters of the key (e.g., "sk-m8-a1b2").

    Returns:
        RevokeKeyResponse with status "revoked" and the key prefix.

    Raises:
        HTTPException(404): If no active key matches the given prefix.
    """
    km: KeyManager = request.app.state.key_manager
    ok: bool = await km.revoke_key(key_prefix)

    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"Key not found or already revoked: {key_prefix}",
        )

    return RevokeKeyResponse(status="revoked", key_prefix=key_prefix)


@router.post("/admin/initialize-engine")
async def initialize_engine(
    engine_config: dict,
    request: Request,
):
    """Initialize the QA Engine with provided configuration.

    WHAT: Sets the QA Engine instance in app.state.qa_engine based on
          the provided configuration dictionary. This endpoint allows
          runtime initialization of the QA Engine after the gateway
          has started.

    WHY: The QA Engine requires an LLM backend configuration which may
         not be available at gateway startup. This endpoint allows the
         admin portal (M7) or deployment scripts to initialize the
         engine with the appropriate configuration.

    Request body (JSON):
        {
            "llm_backend": "deepseek",
            "api_key": "...",
            "base_url": "...",
            "model": "...",
            ...other QA Engine config
        }

    Returns:
        {"status": "ok", "message": "QA Engine initialized successfully"}

    Raises:
        HTTPException(400): If the QA Engine is already initialized.
        HTTPException(500): If initialization fails (invalid config, etc.).
    """
    # Check if QA Engine is already initialized
    if request.app.state.qa_engine is not None:
        raise HTTPException(
            status_code=400,
            detail="QA Engine already initialized. Use PUT /admin/initialize-engine to reconfigure.",
        )

    try:
        # Import the QA Engine here to avoid hard dependency at import time
        # This allows the gateway to start even if M5 is not installed
        from m5_qa import QAEngine
        from m5_qa.core.config import QAConfig

        # Create the QA Engine configuration from the provided dictionary
        config = QAConfig(**engine_config)

        # Initialize the QA Engine
        qa_engine = QAEngine(config)

        # Store the QA Engine in app state
        request.app.state.qa_engine = qa_engine

        return {
            "status": "ok",
            "message": "QA Engine initialized successfully",
        }

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"M5 QA Engine not available: {e}. Ensure M5 is properly installed.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize QA Engine: {e}",
        )


@router.put("/admin/initialize-engine")
async def reconfigure_engine(
    engine_config: dict,
    request: Request,
):
    """Reconfigure the QA Engine with new configuration.

    WHAT: Replaces the existing QA Engine instance in app.state.qa_engine
          with a new instance created from the provided configuration.

    WHY: Allows runtime reconfiguration of the QA Engine when LLM backend
         settings change (e.g., switching API providers, updating model
         parameters). Useful for A/B testing and gradual rollout.

    Request body (JSON):
        Same as POST /admin/initialize-engine

    Returns:
        {"status": "ok", "message": "QA Engine reconfigured successfully"}

    Raises:
        HTTPException(500): If reconfiguration fails.
    """
    try:
        from m5_qa import QAEngine
        from m5_qa.core.config import QAConfig

        config = QAConfig(**engine_config)
        qa_engine = QAEngine(config)

        # Replace the existing QA Engine
        request.app.state.qa_engine = qa_engine

        return {
            "status": "ok",
            "message": "QA Engine reconfigured successfully",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reconfigure QA Engine: {e}",
        )
