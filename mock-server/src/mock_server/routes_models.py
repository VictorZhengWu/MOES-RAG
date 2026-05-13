"""
Mock model listing endpoint (OpenAI-compatible /v1/models).

WHY: OpenAI SDKs call /v1/models to discover available models.
M6 may also display available models in settings. This endpoint
must return a valid model list matching OpenAI's format.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/v1/models")
async def list_models():
    """
    Return available mock models.

    WHY: M6's model selector dropdown sources its options from this
    endpoint. Returning multiple models tests the dropdown rendering
    and selection logic.
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "marine-rag-mock",
                "object": "model",
                "created": 1700000000,
                "owned_by": "marine-offshore-expert-system",
            },
            {
                "id": "marine-rag-structural",
                "object": "model",
                "created": 1700000000,
                "owned_by": "marine-offshore-expert-system",
            },
        ],
    }
