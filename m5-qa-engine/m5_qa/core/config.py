"""
M5 QA Engine — Configuration (QAConfig + LLMBackend).

Defines the runtime configuration for the QA engine, including:
  - LLM backend selection (provider, model, base URL for OpenAI-compatible API)
  - Database path for M5-owned SQLite storage
  - Prompt template selection
  - Self-RAG quality thresholds
"""

from dataclasses import dataclass, field


@dataclass
class LLMBackend:
    """
    WHAT: Configuration for a single LLM backend instance.
    WHY: M5 uses a unified OpenAI-compatible client. By varying provider/model/base_url,
         the same client works with Ollama, DeepSeek API, OpenAI, and Claude (via proxy).
         api_key is optional for local backends like Ollama.
    """

    provider: str = "ollama"
    """Backend provider name: ollama, deepseek, openai, claude."""

    model: str = "DeepSeek-V3"
    """Model identifier string, passed directly to the API."""

    api_key: str | None = None
    """API key for cloud backends. None for local Ollama."""

    base_url: str | None = None
    """Custom base URL for OpenAI-compatible API endpoint.
    Example: http://localhost:11434/v1 for local Ollama."""


@dataclass
class QAConfig:
    """
    WHAT: Master configuration for the M5 QA Engine.
    WHY: All runtime parameters are centralized here so the main engine
         (engine.py) receives a single config object. This avoids scattered
         env-var reads and makes testing straightforward.

    Fields:
      - llm: LLM backend configuration (provider, model, credentials)
      - db_path: Path to M5-owned SQLite database for conversations and quotas
      - system_prompt_id: Which prompt template to use for the system message
      - retrieval_score_threshold: Minimum M3 cosine similarity for Self-RAG quality check
      - max_self_rag_iterations: Maximum Self-RAG rewrite/retrieve loops
    """

    llm: LLMBackend | None = None
    """LLM backend config. If None, a default LLMBackend() is created in __post_init__."""

    db_path: str = "./data/m5_qa.db"
    """Path to the M5-owned SQLite database file (conversations, messages, quotas)."""

    system_prompt_id: str = "system_en"
    """Prompt template ID to use for the system message (e.g., 'system_en', 'system_cn')."""

    default_tier: str = "basic"
    """Default user tier: 'basic' | 'pro' | 'enterprise'.
    Overridden by request.tier if present (future: M8 API gateway passes it)."""

    # ---- Web Search -------------------------------------------------------
    web_search_engine: str = "duckduckgo"
    """Web search backend: 'duckduckgo' | 'searxng' | 'tavily' | 'brave'.
    Personal mode defaults to duckduckgo (free). Enterprise can use tavily."""

    web_search_api_key: str | None = None
    """API key for paid search engines (tavily, brave). None for free engines."""

    web_search_searxng_url: str = "http://localhost:8888"
    """SearXNG instance URL when engine='searxng'."""

    web_search_google_cx: str | None = None
    """Google Custom Search Engine ID (cx). Required when engine='google'."""

    retrieval_score_threshold: float = 0.5
    """Minimum cosine similarity score for M3 retrieval chunks in Self-RAG mode.
    Chunks below this threshold trigger a re-query with rewritten search terms."""

    max_self_rag_iterations: int = 3
    """Maximum number of Self-RAG rewrite/retrieve iterations before giving up.
    Prevents infinite loops when no relevant documents exist for a query."""

    def __post_init__(self):
        """Initialize default LLMBackend if none was provided."""
        if self.llm is None:
            self.llm = LLMBackend()
