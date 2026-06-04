"""Tests for the M8 chat completions route.

WHAT: Verifies that the POST /v1/chat/completions endpoint properly enforces
      authentication (401 for missing/invalid Authorization header).
WHY: Authentication is the first layer of defense for the API gateway.
     If auth is bypassed, rate limiting and access control are meaningless.
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_chat_requires_auth(test_app):
    """POST /v1/chat/completions without Authorization header returns 401.

    WHAT: Sends a chat completion request with no Authorization header
          and verifies the response is 401 Unauthorized.

    WHY: Every API endpoint except /health must require a valid API key.
         This is the most fundamental security check — if it fails,
         unauthenticated users can access the QA Engine directly.
    """
    app, raw_key, config = test_app

    # Use ASGITransport without lifespan context (startup was manually triggered)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # Request without Authorization header
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "marine-rag",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        # Expect 401 — auth middleware should reject before hitting the route
        assert response.status_code == 401, (
            f"Expected 401 for missing auth header, got {response.status_code}"
        )

        # Error response should follow OpenAI-compatible error format
        error_data = response.json()
        assert "detail" in error_data, (
            f"Error response should include 'detail' field, got keys: {list(error_data.keys())}"
        )
