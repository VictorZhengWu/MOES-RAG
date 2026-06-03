"""
M5 QA Engine — Context Compressor.

WHAT: Compresses conversation history to fit within a specified token budget.
      The compressor always preserves system messages and the most recent
      exchange (last user query + assistant response), truncating or dropping
      older messages as needed.

WHY: LLMs have finite context windows (4K–128K tokens). Long multi-turn
     conversations can easily exceed these limits. Rather than truncating
     arbitrarily, this compressor uses a token budget to intelligently
     decide which messages to keep and how to truncate them, ensuring
     the most relevant context is always preserved.
"""

from contracts.qa_engine import Message


def _estimate_tokens(text: str) -> int:
    """
    WHAT: Rough token count estimation: 1 token ~ 4 characters for English text.

    WHY: Accurate token counting requires the model-specific tokenizer, which
         may not be available for all backends (especially local Ollama models).
         This heuristic (consistent with token_budget.estimate_tokens) is
         sufficient for budget planning and context window management.

    Args:
        text: The input text to estimate tokens for.

    Returns:
        Estimated token count (minimum 1, to avoid division-by-zero).
    """
    return max(1, len(text) // 4)


class ContextCompressor:
    """
    WHAT: Compresses a list of chat messages to fit within a token budget.

    Compression algorithm:
      1. Always keep system messages (role=="system") as the first messages.
      2. Always keep at least the last 2 non-system messages (most recent
         user query + assistant response) — this is the minimal context
         needed for the LLM to understand the current turn.
      3. Process older messages from newest to oldest, accumulating token
         estimates. Messages that fit within the remaining budget are kept
         intact; the first message that exceeds the budget is truncated.
      4. All messages older than the truncated one are dropped.

    WHY: This "keep most recent, truncate oldest" strategy preserves the
         most conversationally relevant context (recent turns) while
         ensuring the total token count stays within the LLM's limits.
         System messages are always preserved because they define the
         assistant's behavior and personality.
    """

    def compress(self, messages: list[Message], max_tokens: int) -> list[Message]:
        """
        WHAT: Compress message history to fit within max_tokens budget.

        Args:
            messages: The full list of conversation messages in
                      chronological order (oldest first).
            max_tokens: The maximum total estimated tokens allowed.

        Returns:
            A compressed list of messages that fits within the token budget.
            System messages and at least the last 2 non-system messages
            are always preserved.
        """
        if not messages:
            return []

        # Separate system messages from conversation messages.
        # System messages define the assistant's role/behavior and must be
        # kept intact at the beginning of the context.
        system_msgs = [m for m in messages if m.role == "system"]
        other_msgs = [m for m in messages if m.role != "system"]

        # If we have 2 or fewer non-system messages, no compression needed.
        # The conversation is too short to benefit from truncation.
        if len(other_msgs) <= 2:
            return system_msgs + other_msgs

        # Always preserve the last 2 non-system messages (the most recent
        # user query + assistant response). Without these, the LLM has
        # no context for the current conversation turn.
        preserved = other_msgs[-2:]
        older = other_msgs[:-2]   # Messages that may be truncated or dropped

        # Calculate the token cost of system messages + preserved messages.
        # These are non-negotiable — they must fit even if everything else
        # is dropped.
        system_tokens = sum(_estimate_tokens(m.content) for m in system_msgs)
        preserved_tokens = sum(_estimate_tokens(m.content) for m in preserved)
        mandatory_tokens = system_tokens + preserved_tokens

        # If even the mandatory messages exceed the budget, we keep them
        # anyway (truncating them would break the system prompt or the
        # most recent exchange). Return just the mandatory set.
        if mandatory_tokens >= max_tokens:
            return system_msgs + preserved

        # Remaining token budget for older messages
        remaining = max_tokens - mandatory_tokens

        # Process older messages from newest to oldest.
        # We prioritize recent context over older context — a message from
        # 3 turns ago is more relevant than one from 10 turns ago.
        included = []
        for msg in reversed(older):
            msg_tokens = _estimate_tokens(msg.content)

            if remaining >= msg_tokens:
                # Message fits entirely within remaining budget
                included.append(msg)
                remaining -= msg_tokens
            elif remaining > 0:
                # Message partially fits — truncate its content to use the
                # remaining budget. We append "..." to indicate truncation.
                # max_chars = remaining * 4 (reverse of the 1-token-per-4-chars heuristic)
                max_chars = max(0, remaining * 4 - 3)  # -3 for the "..."
                if max_chars > 0:
                    truncated_content = msg.content[:max_chars] + "..."
                else:
                    truncated_content = "..."
                truncated_msg = Message(role=msg.role, content=truncated_content)
                included.append(truncated_msg)
                remaining = 0
                break  # Budget exhausted, stop processing older messages
            else:
                # Budget exhausted, skip this and all older messages
                break

        # Reverse included back to chronological order (oldest first),
        # then prepend system messages and append the preserved pair.
        included.reverse()

        return system_msgs + included + preserved
