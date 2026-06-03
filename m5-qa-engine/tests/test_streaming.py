"""
Tests for M5 QA Engine — Streaming helpers (streaming.py).

WHAT: Unit tests for the SSE (Server-Sent Events) formatting functions.
WHY: The streaming module produces SSE-compliant output consumed by the
     M6 frontend's EventSource API. Format errors cause silent failures
     in the browser, so exact output format matters.
"""

import pytest

from m5_qa.generation.streaming import sse_chunk, sse_done


# ---------------------------------------------------------------------------
# 1. test_sse_chunk — correct SSE format
# ---------------------------------------------------------------------------

class TestSseChunk:
    """
    WHAT: Verify sse_chunk() produces valid SSE event data lines.
    WHY: SSE requires `data: {json}\n\n` format. The frontend's EventSource
         API parses this format and silently ignores malformed events.
    """

    @pytest.mark.asyncio
    async def test_simple_content_chunk(self):
        """
        WHAT: A plain text content chunk produces `data: {"content":"..."}`.
        WHY: The frontend needs to distinguish content chunks from control
             messages like [DONE]. Content is wrapped in a JSON object
             with a 'content' field.
        """
        result = await sse_chunk("Hello, World!")
        assert "data: " in result
        assert "Hello, World!" in result

    @pytest.mark.asyncio
    async def test_chunk_with_finish_reason(self):
        """
        WHAT: A chunk with finish_reason includes it in the JSON payload.
        WHY: finish_reason signals to the frontend that the stream is
             complete (e.g., 'stop', 'length'). The frontend uses this
             to finalize the message and stop the loading indicator.
        """
        result = await sse_chunk("Final answer.", finish_reason="stop")
        assert "data: " in result
        assert "Final answer." in result
        assert "stop" in result

    @pytest.mark.asyncio
    async def test_sse_format_ends_with_double_newline(self):
        """
        WHAT: Every SSE event MUST end with \n\n.
        WHY: The SSE protocol uses a blank line (\n\n) as the event
             delimiter. Without it, EventSource won't fire the onmessage
             handler and the frontend sees no data.
        """
        result = await sse_chunk("test")
        assert result.endswith("\n\n")

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """
        WHAT: Empty content string should still produce valid SSE format.
        WHY: LLM streaming may yield empty delta.content on some chunks
             (e.g., tool calls or control tokens). These must not break
             the SSE parser.
        """
        result = await sse_chunk("")
        assert "data: " in result
        assert result.endswith("\n\n")


# ---------------------------------------------------------------------------
# 2. test_sse_done — [DONE] marker
# ---------------------------------------------------------------------------

class TestSseDone:
    """
    WHAT: Verify sse_done() produces the SSE stream termination marker.
    WHY: OpenAI-compatible streaming APIs use `data: [DONE]` to signal
         the end of a stream. The frontend EventSource must receive this
         to know the response is complete.
    """

    @pytest.mark.asyncio
    async def test_sse_done_marker(self):
        """
        WHAT: sse_done() returns exactly "data: [DONE]\n\n".
        WHY: This is the standard termination signal for OpenAI-compatible
             streaming. Any deviation causes the frontend to wait indefinitely
             for more data.
        """
        result = await sse_done()
        assert result == "data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_sse_done_is_consistent(self):
        """
        WHAT: Multiple calls to sse_done() return the same value.
        WHY: The [DONE] marker is a constant — it must be idempotent
             and never vary between calls.
        """
        a = await sse_done()
        b = await sse_done()
        assert a == b
