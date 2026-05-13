"""
Server-Sent Events (SSE) helper for mock streaming responses.

WHY: OpenAI-compatible streaming uses SSE (text/event-stream) with
"data: {json}\\n\\n" chunks and a "data: [DONE]\\n\\n" terminator.
The Mock Server must replicate this exactly so M6's streaming UI
works correctly during Phase 1 development. Any format deviation
will cause the frontend streaming parser to fail silently.
"""

import asyncio
import random
from typing import AsyncGenerator

from .config import MockServerConfig
from .data import mock_stream_chunks


async def simulate_stream(
    query: str,
    config: MockServerConfig,
) -> AsyncGenerator[str, None]:
    """
    Yield SSE chunks with simulated latency between each chunk.

    WHY: Real LLM streaming has variable latency between tokens.
    Without simulated delays, all chunks arrive in the same millisecond,
    which hides UI bugs in progressive rendering and scroll behavior.
    Adding 30-80ms between chunks makes the stream feel realistic
    and lets developers verify the streaming UX.
    """
    chunks = mock_stream_chunks(query)
    for chunk in chunks:
        delay = random.uniform(0.03, 0.08)  # 30-80ms between tokens
        await asyncio.sleep(delay)
        yield chunk
