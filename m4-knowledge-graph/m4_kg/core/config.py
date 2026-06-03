"""
M4 Knowledge Graph Engine — Configuration module.

Defines the extraction configuration and LLM backend settings for the
knowledge graph entity/relation extraction pipeline.

WHAT:
  - LLMBackend: Dataclass holding LLM provider connection details.
  - ExtractionConfig: Dataclass controlling the extraction pipeline behavior.

WHY:
  - LLM backends must be pluggable (Ollama local, DeepSeek/OpenAI/Claude cloud).
  - Extraction parameters (batch size, concurrency) vary by deployment size.
  - Fallback-to-rules ensures extraction works even when no LLM is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMBackend:
    """Configuration for an LLM backend connection.

    WHAT: Holds the provider type, model name, API key, and optional
          custom base URL for LLM API calls.
    WHY: The M4 module supports multiple LLM backends (Ollama local,
         DeepSeek, OpenAI, Claude) that are user-configurable via M7 admin UI.
         This dataclass provides a type-safe container for those settings.

    Attributes:
        provider: LLM provider identifier — "ollama", "deepseek", "openai", or "claude".
        model: Model name string (e.g. "DeepSeek-V3", "gpt-4o").
        api_key: API key for cloud providers; None for local Ollama.
        base_url: Custom base URL for the API endpoint; defaults to None
                  (use provider default). Example: "http://localhost:11434/v1" for Ollama.
    """

    provider: str = "ollama"
    model: str = "DeepSeek-V3"
    api_key: str | None = None
    base_url: str | None = None


@dataclass
class ExtractionConfig:
    """Configuration for the entity/relation extraction pipeline.

    WHAT: Controls all parameters of the extraction process including the LLM
          backend to use, batch sizes, concurrency limits, and fallback behavior.
    WHY: Different deployment sizes need different resource limits.
         The LLM field is optional — when None, only rule-based extraction runs.
         fallback_to_rules ensures graceful degradation when LLM calls fail.

    Attributes:
        llm: LLMBackend instance for entity extraction, or None for rule-only.
        max_chunks_per_doc: Maximum chunks to process per document.
        max_tokens_per_batch: Maximum tokens per LLM batch request.
        max_concurrent: Maximum concurrent LLM API calls (Semaphore limit).
        fallback_to_rules: If True, fall back to rule-based extraction when
                           LLM calls fail; if False, raise the error.
    """

    llm: LLMBackend | None = None
    max_chunks_per_doc: int = 200
    max_tokens_per_batch: int = 6000
    max_concurrent: int = 2
    fallback_to_rules: bool = True
