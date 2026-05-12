"""
Mock chat completion endpoints (OpenAI-compatible).

WHY: M6's primary function is chat. These endpoints must exactly
match the OpenAI /v1/chat/completions format so that when we swap
the Mock Server for the real M5, the frontend code needs zero changes.
"""

import asyncio
import random

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from .data import mock_chat_response

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Mock non-streaming chat completion.

    Returns a fake but schema-correct response with marine engineering
    content and sample citations. Supports both streaming (SSE) and
    non-streaming (JSON) responses based on the request body's
    'stream' parameter, matching the OpenAI API behavior.
    """
    body = await request.json()
    query = body.get("messages", [{}])[-1].get("content", "")
    is_stream = body.get("stream", False)

    # Simulate processing latency (200-600ms)
    await asyncio.sleep(random.uniform(0.2, 0.6))

    if is_stream:
        return await _stream_response(query)

    return mock_chat_response(query)


async def _stream_response(query: str):
    """
    Return an SSE streaming response.

    WHY: OpenAI SDKs (Python, JS) expect streaming responses to use
    text/event-stream content type with specific chunk format.
    The frontend SDK will break if the format is wrong. EventSourceResponse
    from sse-starlette handles the Content-Type header and framing.
    """
    from .config import MockServerConfig
    from .sse import simulate_stream

    config = MockServerConfig()

    async def event_generator():
        async for chunk in simulate_stream(query, config):
            yield {"data": chunk}

    return EventSourceResponse(event_generator())
