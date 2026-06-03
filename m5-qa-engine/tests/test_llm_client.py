"""
Tests for M5 QA Engine — LLM Client (llm_client.py).

WHAT: Unit tests for LLMClient and estimate_tokens().
WHY: All tests MUST use Mock objects — no real API calls.
     Validates:
       1. Client initialization with correct base_url per provider
       2. Token estimation for English, Chinese, and empty strings
       3. Non-streaming complete() returns correct response structure
       4. Streaming complete_stream() yields content chunks
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from m5_qa.core.config import LLMBackend
from m5_qa.generation.llm_client import LLMClient, estimate_tokens


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_backend(provider: str = "ollama",
                  model: str = "test-model",
                  api_key: str | None = None,
                  base_url: str | None = None) -> LLMBackend:
    """
    WHAT: Helper to create LLMBackend instances for tests.
    WHY: Avoids repetitive constructor calls across multiple test cases.
    """
    return LLMBackend(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


# ---------------------------------------------------------------------------
# 1. test_client_init — verify correct base_url per provider
# ---------------------------------------------------------------------------

class TestClientInit:
    """
    WHAT: Verify LLMClient constructs AsyncOpenAI with the correct base_url
          and api_key for different LLM providers.
    WHY: The LLMClient's main value is abstracting provider differences
         behind a single OpenAI-compatible interface. If base_url is wrong,
         the client connects to the wrong endpoint.
    """

    def test_ollama_default_url(self):
        """
        WHAT: When no base_url is set for Ollama, the client defaults to
              http://localhost:11434/v1.
        WHY: Ollama's default port is 11434; the /v1 suffix is the
             OpenAI-compatible API path.
        """
        backend = _make_backend(provider="ollama", base_url=None)
        with patch("m5_qa.generation.llm_client.AsyncOpenAI") as mock_openai:
            LLMClient(backend)
            call_kwargs = mock_openai.call_args.kwargs
            assert call_kwargs["base_url"] == "http://localhost:11434/v1"
            # api_key should be a dummy value for local Ollama
            assert call_kwargs["api_key"] == "not-needed"

    def test_ollama_custom_url(self):
        """
        WHAT: When base_url is explicitly provided, it is used directly.
        WHY: Users may run Ollama on a different host/port; the client
             must respect the explicit setting.
        """
        backend = _make_backend(
            provider="ollama",
            base_url="http://192.168.1.100:11434/v1",
        )
        with patch("m5_qa.generation.llm_client.AsyncOpenAI") as mock_openai:
            LLMClient(backend)
            call_kwargs = mock_openai.call_args.kwargs
            assert call_kwargs["base_url"] == "http://192.168.1.100:11434/v1"

    def test_deepseek_base_url(self):
        """
        WHAT: DeepSeek uses https://api.deepseek.com/v1 as base URL
              and requires a real API key.
        WHY: DeepSeek is a cloud provider; the URL must point to their
             official API endpoint with authentication.
        """
        backend = _make_backend(
            provider="deepseek",
            api_key="sk-test-key-123",
            base_url="https://api.deepseek.com/v1",
        )
        with patch("m5_qa.generation.llm_client.AsyncOpenAI") as mock_openai:
            LLMClient(backend)
            call_kwargs = mock_openai.call_args.kwargs
            assert call_kwargs["base_url"] == "https://api.deepseek.com/v1"
            assert call_kwargs["api_key"] == "sk-test-key-123"

    def test_openai_base_url(self):
        """
        WHAT: OpenAI uses the default AsyncOpenAI base URL when none
              is explicitly provided (AsyncOpenAI defaults to api.openai.com).
        WHY: The standard OpenAI Python SDK uses https://api.openai.com/v1
             by default when no base_url is given.
        """
        backend = _make_backend(
            provider="openai",
            api_key="sk-openai-key-456",
            base_url=None,
        )
        with patch("m5_qa.generation.llm_client.AsyncOpenAI") as mock_openai:
            LLMClient(backend)
            call_kwargs = mock_openai.call_args.kwargs
            # AsyncOpenAI default is https://api.openai.com/v1 when base_url is None
            assert call_kwargs["base_url"] == "https://api.openai.com/v1"
            assert call_kwargs["api_key"] == "sk-openai-key-456"


# ---------------------------------------------------------------------------
# 2. test_estimate_tokens
# ---------------------------------------------------------------------------

class TestEstimateTokens:
    """
    WHAT: Test the estimate_tokens() helper function for English, Chinese,
          and empty strings.
    WHY: Token estimation (chars / 4) is a rough approximation used for
         token budget allocation. It must be fast and deterministic.
    """

    def test_english_text(self):
        """
        WHAT: English text — each character is roughly 1 token per 4 chars.
        WHY: ASCII text averages ~4 characters per token with most LLM tokenizers.
        """
        text = "The quick brown fox jumps over the lazy dog"
        # 43 characters → ~10 tokens
        assert estimate_tokens(text) == len(text) // 4

    def test_chinese_text(self):
        """
        WHAT: Chinese text — each character is roughly 1 token per 1-2 chars
              with most tokenizers, but our simplified estimator uses chars/4.
        WHY: estimate_tokens() is intentionally simple. Chinese tokens are
             more compact (fewer chars per token), so chars/4 overestimates.
             This is acceptable for budget allocation — better to over-allocate
             than under-allocate.
        """
        text = "船舶与海洋工程规范"
        # 8 characters → 2 tokens by chars/4
        assert estimate_tokens(text) == len(text) // 4

    def test_empty_string(self):
        """
        WHAT: Empty input returns 0.
        WHY: Zero characters should yield zero tokens, not a division error.
        """
        assert estimate_tokens("") == 0


# ---------------------------------------------------------------------------
# 3. test_complete_mock — mock non-streaming response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_mock():
    """
    WHAT: LLMClient.complete() returns a dict with choices[0].message.content.
    WHY: The non-streaming path must return the full response dict so callers
         can extract the answer text and token usage. We mock AsyncOpenAI
         to return a controlled response.
    """
    backend = _make_backend(provider="ollama")

    # Build a mock chat completion response
    mock_message = MagicMock()
    mock_message.content = "The answer is 42."

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.model_dump.return_value = {
        "choices": [{"message": {"content": "The answer is 42."}}],
        "usage": {"total_tokens": 10},
    }

    # Mock the inner chat.completions.create to return our controlled response
    mock_create = AsyncMock(return_value=mock_response)
    mock_chat = MagicMock()
    mock_chat.completions.create = mock_create
    mock_client_instance = MagicMock()
    mock_client_instance.chat = mock_chat

    with patch("m5_qa.generation.llm_client.AsyncOpenAI",
               return_value=mock_client_instance):
        client = LLMClient(backend)
        result = await client.complete([
            {"role": "user", "content": "What is the answer?"}
        ])

    # Verify the response structure
    assert "choices" in result
    assert result["choices"][0]["message"]["content"] == "The answer is 42."
    # Verify create() was called with correct parameters
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["model"] == "test-model"
    assert call_kwargs["stream"] is False
    assert len(call_kwargs["messages"]) == 1


# ---------------------------------------------------------------------------
# 4. test_stream_mock — mock streaming response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_mock():
    """
    WHAT: LLMClient.complete_stream() yields content chunks from the
          streaming response iterator.
    WHY: The streaming path must asynchronously yield text deltas so that
         the caller can forward them as SSE events to the frontend.
    """
    backend = _make_backend(provider="ollama")

    # Build mock streaming chunks that simulate a real SSE stream
    async def _mock_stream():
        """Simulate 3 streaming chunks, each with a small text delta."""
        for text in ["Hello", " ", "World"]:
            chunk = MagicMock()
            chunk.choices = []
            if text:
                delta = MagicMock()
                delta.content = text
                choice = MagicMock()
                choice.delta = delta
                chunk.choices = [choice]
            yield chunk

    mock_create = AsyncMock(return_value=_mock_stream())
    mock_chat = MagicMock()
    mock_chat.completions.create = mock_create
    mock_client_instance = MagicMock()
    mock_client_instance.chat = mock_chat

    with patch("m5_qa.generation.llm_client.AsyncOpenAI",
               return_value=mock_client_instance):
        client = LLMClient(backend)
        chunks = []
        async for chunk in client.complete_stream([
            {"role": "user", "content": "Say hello"}
        ]):
            chunks.append(chunk)

    # Verify all content chunks were yielded
    assert chunks == ["Hello", " ", "World"]
    # Verify create() was called with stream=True
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["stream"] is True
    assert call_kwargs["model"] == "test-model"
