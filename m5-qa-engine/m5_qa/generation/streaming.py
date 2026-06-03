"""
M5 QA Engine — SSE Streaming Helpers.

WHAT: Functions to format Server-Sent Events (SSE) for LLM streaming output.
WHY: The M6 frontend uses the browser's EventSource API to receive streaming
     responses. SSE requires a specific wire format (`data: {json}\n\n`),
     and the `data: [DONE]\n\n` termination marker follows the OpenAI-compatible
     streaming convention. Getting this format wrong causes silent failures
     in the browser — EventSource will never fire onmessage handlers.
"""

import json


async def sse_chunk(
    content: str,
    finish_reason: str | None = None,
) -> str:
    """
    WHAT: Format a text content delta as an SSE event chunk.

    WHY: The SSE protocol requires each event to be a `data:` line followed
         by a blank line (\n\n). We wrap the content in a JSON object so the
         frontend can distinguish event types (content vs. error vs. metadata).
         finish_reason is included when the LLM signals stream completion
         (typically 'stop' or 'length'), allowing the frontend to finalize
         the message and stop the loading indicator.

    Args:
        content: The text delta from the LLM streaming response.
        finish_reason: Optional reason the LLM stopped ('stop', 'length',
                       'tool_calls', etc.). None for intermediate chunks.

    Returns:
        str: A complete SSE event string in `data: {json}\n\n` format.
    """
    payload: dict[str, str] = {"content": content}
    if finish_reason is not None:
        payload["finish_reason"] = finish_reason

    # Build the SSE data line: "data: " prefix + JSON body + double newline
    data_line = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    return data_line


async def sse_done() -> str:
    """
    WHAT: Return the SSE stream termination marker.

    WHY: OpenAI-compatible streaming APIs use `data: [DONE]` to signal the
         end of a stream. The frontend's EventSource API relies on this exact
         marker to close the connection and finalize the message. Without it,
         the browser will keep the connection open indefinitely, waiting for
         more data that never arrives.

    Returns:
        str: The literal string "data: [DONE]\n\n".
    """
    return "data: [DONE]\n\n"
