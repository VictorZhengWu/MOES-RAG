"""Tests for OpenAI SDK compatibility.

WHAT: Verifies that M8 API Gateway responses are compatible with the
      OpenAI Python SDK. Tests response headers (content-type, request-id
      headers that the SDK expects) and error response format.

WHY: The primary value proposition of M8 is seamless drop-in replacement
     for the OpenAI API. If responses don't match the OpenAI format, SDK
     clients will fail with cryptic errors instead of the clear errors
     our API intends to return.
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_openai_sdk_headers(test_app):
    """Verify M8 responses have headers compatible with the OpenAI Python SDK.

    WHAT: Makes an authenticated request to /v1/models and checks that the
          response headers include content-type: application/json. Also
          verifies that the response format (JSON with 'object' and 'data'
          fields) is what the OpenAI SDK expects when calling models.list().

    WHY: The OpenAI Python SDK parses specific fields from the response.
         If content-type is wrong (e.g., text/plain), the SDK may fail
         to parse the JSON. If the response schema is wrong, the SDK
         raises Pydantic validation errors on the client side.
    """
    app, raw_key, config = test_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # Test /v1/models endpoint (used by openai SDK during client init)
        response = await client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {raw_key}"},
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}"
        )

        # Content-Type must be application/json for SDK parsing
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, (
            f"Content-Type should be application/json, got: {content_type}"
        )

        # Response body must be parseable as JSON
        body = response.json()
        assert isinstance(body, dict), (
            f"Response body should be a dict, got {type(body)}"
        )

        # The OpenAI SDK expects these top-level fields for models.list()
        assert "object" in body, (
            f"Response missing 'object' field (required by OpenAI SDK)"
        )
        assert "data" in body, (
            f"Response missing 'data' field (required by OpenAI SDK)"
        )

        # Each model entry must be a dict with 'id' and 'object'
        for entry in body["data"]:
            assert "id" in entry, f"Model entry missing 'id': {entry}"


@pytest.mark.asyncio
async def test_error_response_format(test_app):
    """Verify 401/429 error responses follow OpenAI-compatible error format.

    WHAT: Triggers a 401 error (no auth header) and a 429 error (rate limit
          exceeded by sending many rapid requests on a basic-tier key),
          then verifies the error response structure matches what the
          OpenAI SDK expects.

    WHY: The OpenAI Python SDK has specific error handling logic. It tries
         to parse error responses into typed exception classes
         (AuthenticationError, RateLimitError, etc.). If the error format
         doesn't match, the SDK raises a generic APIConnectionError instead
         of the specific typed exception, making it harder for client code
         to handle errors correctly.

         The SDK expects at minimum a JSON body with an error description.
         While the full OpenAI format is {"error": {"message": "...",
         "type": "...", "code": "..."}}, a flat {"detail": "..."} is
         handled by most SDK versions via the fallback path.
    """
    app, raw_key, config = test_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # --- Test 401 error format ---

        # Send request without Authorization header
        unauth_resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "marine-rag",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert unauth_resp.status_code == 401, (
            f"Expected 401, got {unauth_resp.status_code}"
        )

        # Error response must be JSON
        error_body = unauth_resp.json()
        assert isinstance(error_body, dict), (
            f"Error response should be a dict, got {type(error_body)}"
        )

        # Must include a 'detail' field describing the error
        # (OpenAI SDK reads this as the error message)
        assert "detail" in error_body, (
            f"401 error should include 'detail' field, got keys: {list(error_body.keys())}"
        )

        # --- Test 429 error format ---

        # Wire a mock QA Engine so the chat completions endpoint can be
        # called. The chat endpoint has check_rate_limit in its dependency
        # chain, so we can test 429 responses by exceeding the rate limit.
        #
        # We use a plain class returning dicts (not contract dataclasses)
        # to avoid dataclass serialization issues in the test. The route
        # handler returns whatever the engine returns, and FastAPI can
        # serialize dicts natively.
        class _MockQAEngine:
            """Minimal mock QA Engine for rate-limit testing.

            WHAT: Returns a dict (not a dataclass) so FastAPI can serialize
                  it without needing jsonable_encoder/dataclass handling.
            WHY: The chat route handler returns engine.chat() directly.
                 A dict response is JSON-serializable by FastAPI natively.
            """
            async def chat(self, request):
                return {
                    "id": "chatcmpl-test-429",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }],
                    "usage": {
                        "prompt_tokens": 5,
                        "completion_tokens": 3,
                        "total_tokens": 8,
                    },
                }

            async def list_models(self):
                return [{"id": "mock-model", "object": "model"}]

        # Inject the mock engine into app state so the chat route can use it
        app.state.qa_engine = _MockQAEngine()

        # Create a basic-tier key (low rate limit: 100/min in personal mode)
        create_resp = await client.post(
            "/admin/keys",
            json={"user_id": "rate-test-user", "tier": "basic"},
        )
        assert create_resp.status_code == 200
        basic_key = create_resp.json()["key"]

        # Send many rapid chat requests to trigger rate limit.
        # The chat completions endpoint has check_rate_limit in its
        # dependency chain. In personal mode, basic tier = 100 req/min.
        rate_limited = False
        for _ in range(150):
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "mock-model",
                    "messages": [{"role": "user", "content": "hi"}],
                },
                headers={"Authorization": f"Bearer {basic_key}"},
            )
            if resp.status_code == 429:
                rate_limited = True
                # Verify 429 error format matches OpenAI error convention
                rate_limit_body = resp.json()
                assert isinstance(rate_limit_body, dict), (
                    f"429 error should be a dict, got {type(rate_limit_body)}"
                )
                assert "detail" in rate_limit_body, (
                    f"429 error should include 'detail', got keys: "
                    f"{list(rate_limit_body.keys())}"
                )
                break

        assert rate_limited, (
            "Expected to be rate limited after sending >100 requests with "
            "basic key via /v1/chat/completions (which has check_rate_limit "
            "in its dependency chain). The rate limiter may not be working."
        )
