"""
M5 QA Engine — Generation module.

WHAT: Provides LLM client abstraction and SSE streaming helpers for the QA engine.
WHY: Centralizes all LLM communication behind a single OpenAI-compatible interface,
     supporting Ollama (local), DeepSeek, OpenAI, and Claude (via proxy) through
     the same client. The streaming module produces SSE-formatted output consumed
     by the M6 frontend's EventSource API.
"""

from m5_qa.generation.llm_client import LLMClient, estimate_tokens
from m5_qa.generation.streaming import sse_chunk, sse_done

__all__ = [
    "LLMClient",
    "estimate_tokens",
    "sse_chunk",
    "sse_done",
]
