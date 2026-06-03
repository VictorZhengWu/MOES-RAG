"""
Tests for M4 Knowledge Graph Engine — Configuration module.

Tests cover:
  1. Default config values
  2. Custom LLM backend
  3. Custom batch settings
"""

import pytest

# WHAT: Import the config classes from the m4_kg.core.config module.
# WHY: Tests validate that ExtractionConfig and LLMBackend behave as specified.
from m4_kg.core.config import LLMBackend, ExtractionConfig


class TestDefaultConfig:
    """Test that default configuration values match the specification."""

    def test_default_llm_backend_values(self):
        """Verify LLMBackend defaults are correct.

        WHAT: Create an LLMBackend with no arguments and check all fields.
        WHY: Defaults must match the spec: provider='ollama', model='DeepSeek-V3'.
        """
        backend = LLMBackend()
        assert backend.provider == "ollama"
        assert backend.model == "DeepSeek-V3"
        assert backend.api_key is None
        assert backend.base_url is None

    def test_default_extraction_config_values(self):
        """Verify ExtractionConfig defaults are correct.

        WHAT: Create an ExtractionConfig with no arguments and check all fields.
        WHY: Defaults must match the spec: max_chunks_per_doc=200,
             max_tokens_per_batch=6000, max_concurrent=2, fallback_to_rules=True.
        """
        config = ExtractionConfig()
        # llm defaults to None — no LLM backend configured
        assert config.llm is None
        assert config.max_chunks_per_doc == 200
        assert config.max_tokens_per_batch == 6000
        assert config.max_concurrent == 2
        assert config.fallback_to_rules is True


class TestCustomLLMBackend:
    """Test that custom LLM backend configurations work correctly."""

    def test_custom_deepseek_backend(self):
        """Verify a custom DeepSeek LLM backend is properly configured.

        WHAT: Create an LLMBackend for DeepSeek API with custom settings.
        WHY: The system must support multiple LLM providers through the same
             LLMBackend dataclass.
        """
        backend = LLMBackend(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-test-key-12345",
            base_url="https://api.deepseek.com/v1",
        )
        assert backend.provider == "deepseek"
        assert backend.model == "deepseek-chat"
        assert backend.api_key == "sk-test-key-12345"
        assert backend.base_url == "https://api.deepseek.com/v1"

    def test_extraction_config_with_custom_llm(self):
        """Verify ExtractionConfig can be created with a custom LLM backend.

        WHAT: Create an ExtractionConfig with a custom LLMBackend instance.
        WHY: The extraction pipeline must accept an LLM backend to use for
             entity/relation extraction.
        """
        llm = LLMBackend(
            provider="openai",
            model="gpt-4o",
            api_key="sk-openai-key",
        )
        config = ExtractionConfig(llm=llm)
        assert config.llm is not None
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o"
        assert config.llm.api_key == "sk-openai-key"


class TestCustomBatchSettings:
    """Test that custom batch extraction settings work correctly."""

    def test_custom_batch_configuration(self):
        """Verify custom batch processing parameters are stored correctly.

        WHAT: Create an ExtractionConfig with non-default batch settings.
        WHY: Different deployments may need different batch sizes and
             concurrency limits based on available resources.
        """
        config = ExtractionConfig(
            max_chunks_per_doc=500,
            max_tokens_per_batch=12000,
            max_concurrent=4,
            fallback_to_rules=False,
        )
        assert config.max_chunks_per_doc == 500
        assert config.max_tokens_per_batch == 12000
        assert config.max_concurrent == 4
        assert config.fallback_to_rules is False
