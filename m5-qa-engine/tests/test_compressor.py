"""
Tests for M5 QA Engine — Context Compressor (compressor.py).

WHAT: Unit tests for ContextCompressor.compress() — verifying that
      conversation history is properly truncated to fit within token budgets
      while preserving system messages and the most recent exchange.

WHY: Context compression is critical for the RAG pipeline: without it,
     long conversations would exceed the LLM's context window, causing
     API errors or truncated responses. These tests verify the compressor
     correctly balances preservation and truncation.
"""

import pytest

from contracts.qa_engine import Message
from m5_qa.conversation.compressor import ContextCompressor


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_messages(count: int, content_length: int = 100) -> list[Message]:
    """
    WHAT: Create a list of alternating user/assistant messages for testing.

    Each message has role "user" or "assistant" alternating, with a
    predictable content string of the given length.

    Args:
        count: Number of messages to create.
        content_length: Approximate length of each message's content string.

    Returns:
        A list of Message objects.
    """
    messages = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        # Fill content to desired length with padding
        content = f"[msg{i:03d}] " + "X" * max(0, content_length - 10)
        messages.append(Message(role=role, content=content))
    return messages


# ---------------------------------------------------------------------------
# Tests: ContextCompressor.compress
# ---------------------------------------------------------------------------

class TestCompressorKeepWithinBudget:
    """Tests that all messages are kept when they fit within the token budget."""

    def test_keep_within_budget(self):
        """
        WHAT: Short messages that fit within budget are all kept.
        WHY: No compression needed when total estimated tokens <= max_tokens.
        """
        compressor = ContextCompressor()
        messages = make_messages(count=4, content_length=80)  # ~80 chars = ~20 tokens each
        # 4 messages * 20 tokens = ~80 tokens, budget of 200 is plenty
        result = compressor.compress(messages, max_tokens=200)

        assert len(result) == 4
        # Order must be preserved
        assert result[0].content == messages[0].content
        assert result[1].content == messages[1].content
        assert result[2].content == messages[2].content
        assert result[3].content == messages[3].content


class TestCompressorTruncateWhenOverBudget:
    """Tests that old messages are truncated when token budget is exceeded."""

    def test_truncate_when_over_budget(self):
        """
        WHAT: 10 long messages exceed 1000-token budget, so older messages
              get truncated or dropped.
        WHY: The compressor must enforce the token budget by truncating
             old messages' content while preserving recent ones intact.
        """
        compressor = ContextCompressor()
        # 10 messages, each ~200 chars = ~50 tokens → ~500 tokens total
        messages = make_messages(count=10, content_length=200)

        # Budget of 250 tokens: only about 5 messages fit
        result = compressor.compress(messages, max_tokens=250)

        # Should have fewer messages than original (some truncated/dropped)
        assert len(result) < len(messages)
        # Last 2 messages must be preserved intact
        assert result[-1].content == messages[-1].content
        assert result[-2].content == messages[-2].content
        # Total estimated tokens should be within budget
        total_estimated = sum(max(1, len(m.content) // 4) for m in result)
        assert total_estimated <= 250, f"Expected <= 250 tokens, got ~{total_estimated}"


class TestCompressorPreserveLastMessages:
    """Tests that the last 2 messages are always preserved."""

    def test_preserve_last_messages(self):
        """
        WHAT: Even under extreme truncation (tiny budget), the last 2 messages
              (most recent user query + assistant response) are always kept.
        WHY: The most recent exchange is the core of the current conversation
             context. Without it, the LLM has no idea what the user just asked.
        """
        compressor = ContextCompressor()
        messages = make_messages(count=8, content_length=200)

        # Extremely small budget — barely enough for 1 message
        result = compressor.compress(messages, max_tokens=60)

        # Must have at least 2 non-system messages preserved
        assert len(result) >= 2
        # The last 2 original messages must be present
        assert result[-1].content == messages[-1].content
        assert result[-2].content == messages[-2].content
