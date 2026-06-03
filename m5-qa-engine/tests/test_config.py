"""
Tests for m5_qa.core.config — QAConfig and LLMBackend.

Tests cover:
  1. Default config values
  2. Custom LLM backend configuration
  3. Custom db_path and retrieval threshold
"""

import pytest
from dataclasses import asdict

from m5_qa.core.config import QAConfig, LLMBackend


class TestDefaultConfig:
    """Verify that QAConfig defaults match the design spec."""

    def test_default_config_values(self):
        """
        WHAT: Test that a default-constructed QAConfig has all expected default values.
        WHY: Default values are the contract for personal/development mode
             and must match the design specification exactly.
        """
        config = QAConfig()

        # LLM backend defaults to Ollama with DeepSeek-V3
        assert config.llm is not None, "Default llm backend should not be None"
        assert config.llm.provider == "ollama"
        assert config.llm.model == "DeepSeek-V3"
        assert config.llm.api_key is None, "Default api_key should be None for local Ollama"
        assert config.llm.base_url is None, "Default base_url should be None"

        # M5-owned SQLite database path
        assert config.db_path == "./data/m5_qa.db"

        # System prompt template ID
        assert config.system_prompt_id == "system_en"

        # Self-RAG retrieval quality threshold (cosine similarity)
        assert config.retrieval_score_threshold == 0.5

        # Maximum Self-RAG iterations before giving up
        assert config.max_self_rag_iterations == 3


class TestCustomLLMBackend:
    """Verify that LLMBackend supports custom provider/model/URL combinations."""

    def test_custom_llm_backend(self):
        """
        WHAT: Test constructing a QAConfig with a fully customized LLM backend.
        WHY: Users must be able to switch between Ollama, DeepSeek API,
             OpenAI, and Claude backends via configuration — not hardcoded logic.
        """
        custom_llm = LLMBackend(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test-12345",
            base_url="https://api.deepseek.com/v1",
        )
        config = QAConfig(llm=custom_llm)

        # Verify custom backend is preserved
        assert config.llm.provider == "deepseek"
        assert config.llm.model == "deepseek-chat"
        assert config.llm.api_key == "sk-test-12345"
        assert config.llm.base_url == "https://api.deepseek.com/v1"

        # Non-LLM fields should remain at defaults
        assert config.system_prompt_id == "system_en"
        assert config.retrieval_score_threshold == 0.5


class TestCustomDBAndThreshold:
    """Verify that db_path and retrieval threshold can be independently configured."""

    def test_custom_db_path_and_threshold(self):
        """
        WHAT: Test non-default db_path and retrieval_score_threshold values.
        WHY: Production deployments need custom database paths and may need
             different retrieval quality thresholds based on document corpus.
        """
        config = QAConfig(
            db_path="/prod/data/m5_qa_prod.db",
            retrieval_score_threshold=0.7,
            max_self_rag_iterations=5,
        )

        assert config.db_path == "/prod/data/m5_qa_prod.db"
        assert config.retrieval_score_threshold == 0.7
        assert config.max_self_rag_iterations == 5

        # LLM should still use defaults when not explicitly set
        assert config.llm is not None
        assert config.llm.provider == "ollama"
