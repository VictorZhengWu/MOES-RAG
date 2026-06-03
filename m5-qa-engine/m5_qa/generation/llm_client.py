"""
M5 QA Engine — Unified LLM Client.

WHAT: LLMClient wraps openai.AsyncOpenAI to provide a single interface for
      all supported LLM backends (Ollama, DeepSeek, OpenAI, Claude via proxy).
      Includes non-streaming `complete()` and streaming `complete_stream()`
      methods, plus a helper `estimate_tokens()` for rough token counting.

WHY: A single client with base_url differentiation avoids the complexity of
     separate provider files. All supported backends expose OpenAI-compatible
     APIs, so one AsyncOpenAI instance handles all of them. The token estimator
     is intentionally simple (chars / 4) — it's used for budget allocation,
     where overestimation is safer than underestimation.
"""

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from m5_qa.core.config import LLMBackend


class LLMClient:
    """
    WHAT: Unified LLM interface via OpenAI-compatible API.
          Covers Ollama, DeepSeek, OpenAI, Claude (Anthropic via proxy)
          — all differentiated through base_url.

    WHY: All modern LLM providers support an OpenAI-compatible chat completions
         endpoint. A single AsyncOpenAI client with a configurable base_url
         handles every provider, eliminating the need for per-provider adapter
         classes and their associated maintenance burden.

    Usage:
        backend = LLMBackend(provider="ollama", model="llama3")
        client = LLMClient(backend)
        response = await client.complete([{"role": "user", "content": "Hi"}])
    """

    def __init__(self, backend: LLMBackend) -> None:
        """
        WHAT: Initialize the LLM client with backend configuration.

        WHY: The constructor wires up openai.AsyncOpenAI with the correct
             base_url and api_key. For local backends like Ollama, the
             api_key is a dummy value (Ollama doesn't require auth).

        Args:
            backend: LLMBackend dataclass with provider, model, api_key, base_url.
        """
        # Determine the effective base URL — each provider has a default
        _base_url = backend.base_url
        if _base_url is None:
            # Use provider-specific defaults when no explicit URL is given
            if backend.provider == "ollama":
                _base_url = "http://localhost:11434/v1"
            else:
                # Default to OpenAI's URL for cloud providers
                _base_url = "https://api.openai.com/v1"

        self._client = AsyncOpenAI(
            api_key=backend.api_key or "not-needed",
            base_url=_base_url,
        )
        self._model = backend.model

    async def complete(self, messages: list[dict], **kwargs) -> dict:
        """
        WHAT: Send a non-streaming chat completion request and return the
              full response as a dict (model_dump format).

        WHY: Non-streaming mode is used by simple and pipeline modes where
             the full answer must be available before returning to the caller.
             Returns the raw dict so callers can extract content, usage stats,
             and finish_reason.

        Args:
            messages: List of message dicts in OpenAI format
                      [{"role": "user", "content": "..."}].
            **kwargs: Additional parameters forwarded to the API
                      (temperature, max_tokens, top_p, etc.).

        Returns:
            dict: The full API response as returned by model_dump(),
                  containing choices, usage, model, etc.
        """
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=False,
            **kwargs,
        )
        return response.model_dump()

    async def complete_stream(
        self, messages: list[dict], **kwargs
    ) -> AsyncIterator[str]:
        """
        WHAT: Send a streaming chat completion request and yield text
              content chunks as they arrive.

        WHY: Streaming is used when the frontend expects SSE events in
             real-time. Each yielded chunk is a text delta that can be
             wrapped in an SSE `data:` event and sent to the browser.
             Chunks with no content (e.g., tool call control tokens)
             are silently skipped.

        Args:
            messages: List of message dicts in OpenAI format.
            **kwargs: Additional parameters forwarded to the API.

        Yields:
            str: Text content delta from each stream chunk.
        """
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            # Only yield chunks that contain actual text content.
            # Control chunks (tool calls, empty deltas) are skipped.
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


def estimate_tokens(text: str) -> int:
    """
    WHAT: Estimate token count by dividing character length by 4.

    WHY: Tokenization varies by model and tokenizer, but chars/4 is a
         well-known rule-of-thumb approximation (1 token ≈ 4 characters
         for English text). This is used for token budget allocation in
         the QA pipeline, where a rough estimate is sufficient. Chinese
         text is intentionally overestimated (it's more compact, ~1-2
         chars/token), which is safe for budget allocation — it's better
         to reserve too much context space than too little.

    Args:
        text: The input string to estimate tokens for.

    Returns:
        int: Estimated token count. Returns 0 for empty input.
    """
    return len(text) // 4
