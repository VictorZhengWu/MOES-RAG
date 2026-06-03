"""
M5 QA Engine — Conversation module.

WHAT: Manages conversation history persistence and context compression
      for the M5 QA Engine. Provides:
        - ConversationManager: SQLite-backed CRUD for conversations,
          messages, and premium quota tracking.
        - ContextCompressor: Token-budget-aware conversation trimming
          to fit within LLM context windows.

WHY: Conversation history is essential for multi-turn chat, and context
     compression is required to stay within the LLM's token limits.
     M5 manages its own SQLite database (not through M2) because
     conversation data is M5-specific business logic — M2 is a storage
     abstraction layer that should remain unaware of M5 schemas.
"""

from m5_qa.conversation.manager import ConversationManager
from m5_qa.conversation.compressor import ContextCompressor

__all__ = ["ConversationManager", "ContextCompressor"]
