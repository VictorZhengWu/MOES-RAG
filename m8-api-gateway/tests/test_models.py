"""Tests for the M8 models listing route.

WHAT: Verifies that GET /v1/models returns a valid OpenAI-compatible models
      list response when provided with a valid API key.
WHY: The OpenAI Python SDK calls /v1/models during client initialization.
     If this endpoint returns an error or non-standard format, the SDK
     fails before any chat requests can be made.
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_models_list(test_app):
    """GET /v1/models with a valid API key returns 200 with models list.

    WHAT: Sends a GET request to /v1/models with a valid Bearer token
          and verifies the response structure matches the OpenAI
          models list format: {"object": "list", "data": [...]}.

    WHY: OpenAI SDK compatibility depends on this endpoint returning
         a correctly structured response. The SDK parses the data array
         to discover available model IDs.
    """
    app, raw_key, config = test_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {raw_key}"},
        )

        # Expect 200 — the endpoint should return successfully
        assert response.status_code == 200, (
            f"Expected 200 for valid key, got {response.status_code}: {response.text}"
        )

        # Verify response structure matches OpenAI format
        body = response.json()
        assert body["object"] == "list", (
            f"Expected 'object': 'list', got {body.get('object')}"
        )
        assert "data" in body, (
            f"Response should include 'data' array, got keys: {list(body.keys())}"
        )
        assert isinstance(body["data"], list), (
            f"'data' should be a list, got {type(body['data'])}"
        )

        # Verify at least one model is listed
        assert len(body["data"]) >= 1, (
            "Models list should contain at least one entry"
        )

        # Verify each model entry has required fields
        for model_entry in body["data"]:
            assert "id" in model_entry, (
                f"Each model entry must have 'id', got keys: {list(model_entry.keys())}"
            )
            assert "object" in model_entry, (
                f"Each model entry must have 'object', got keys: {list(model_entry.keys())}"
            )
