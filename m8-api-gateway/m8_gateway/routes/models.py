"""OpenAI-compatible models listing route.

WHAT: GET /v1/models endpoint that returns available LLM models in the
      OpenAI /v1/models JSON format. This endpoint is required for
      OpenAI SDK compatibility — the SDK calls this on initialization
      to discover available models.

WHY: Every OpenAI-compatible API must expose /v1/models. Without it,
     the OpenAI Python SDK (openai.OpenAI(base_url="...")) fails on
     client initialization because it calls models.list() during
     client construction. This endpoint ensures seamless SDK integration.

     When the QA Engine is not available (lazy init), a fallback model
     entry is returned so that basic connectivity checks pass.
"""

from fastapi import APIRouter, Depends, Request

from m8_gateway.auth.key_manager import APIKey
from m8_gateway.auth.middleware import get_api_key

router = APIRouter(tags=["Models"])


@router.get("/v1/models")
async def list_models(
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """List available models (OpenAI-compatible format).

    WHAT: Returns {"object": "list", "data": [...]} per the OpenAI /v1/models
          specification. Each model entry has at minimum 'id' and 'object'
          fields. When the QA Engine is available, delegates to engine.list_models().
          When the engine is not yet initialized, returns a fallback model entry
          so that basic connectivity and SDK initialization succeed.

    WHY: The OpenAI Python SDK calls this endpoint automatically during
         client construction (openai.OpenAI(base_url="...")). If it returns
         a 404 or non-standard format, the SDK raises an error before any
         chat requests can be made.

    Args:
        request: FastAPI Request for accessing app.state.
        api_key: Validated API key (injected by get_api_key dependency).

    Returns:
        dict: {"object": "list", "data": [...]} in OpenAI models list format.
    """
    # Access the QA Engine from app state
    engine = request.app.state.qa_engine

    if engine is not None:
        # Delegate to the engine for the real model list
        models = await engine.list_models()
    else:
        # Engine not initialized — return a minimal fallback entry.
        # This allows the OpenAI SDK to succeed during client init
        # even before the QA Engine is fully wired up.
        models = [{"id": "m5-qa", "object": "model"}]

    return {"object": "list", "data": models}
