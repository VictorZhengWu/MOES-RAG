"""
QA Engine protocols (M5).

Defines the RAG QA engine interface consumed by M6/M7/M8.
API format is OpenAI-compatible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable


@dataclass
class Message:
    """A single chat message."""
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class Citation:
    """A source citation attached to an answer."""
    index: int
    source_doc: str
    section: str
    clause_id: str | None = None
    excerpt: str = ""
    url: str | None = None


@dataclass
class ChatRequest:
    """Incoming chat completion request (OpenAI-compatible)."""
    model: str
    messages: list[Message]
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    user: str | None = None
    conversation_id: str | None = None
    # RAG-specific extensions
    domain_filter: str | None = None
    vessel_type_filter: str | None = None
    web_search_enabled: bool = False  # Enable live web search via DuckDuckGo


@dataclass
class ChatResponse:
    """Non-streaming chat completion response."""
    id: str
    object: str = "chat.completion"
    created: int = 0
    model: str = ""
    choices: list[Choice] = field(default_factory=list)
    usage: Usage | None = None
    citations: list[Citation] = field(default_factory=list)  # RAG extension


@dataclass
class Choice:
    """A single completion choice."""
    index: int
    message: Message
    finish_reason: str = "stop"


@dataclass
class Usage:
    """Token usage statistics."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class ConversationSummary:
    """Metadata for a user's conversation."""
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


@runtime_checkable
class QAEngineProtocol(Protocol):
    """Interface for the RAG QA engine."""

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Non-streaming chat completion."""
        ...

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Streaming chat completion. Yields SSE chunks."""
        ...

    async def list_conversations(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[ConversationSummary]:
        """List user's conversation history."""
        ...

    async def get_conversation(
        self, conversation_id: str, user_id: str
    ) -> list[Message]:
        """Retrieve full conversation history."""
        ...

    async def delete_conversation(
        self, conversation_id: str, user_id: str
    ) -> bool:
        """Delete a conversation."""
        ...

    async def list_models(self) -> list[dict[str, Any]]:
        """List available LLM models and their configurations."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Verify QA engine and all downstream dependencies."""
        ...
