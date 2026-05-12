"""
Shared test fixtures for contracts/ validation tests.

WHY: Tests across test_api_schemas.py and test_protocols.py
need consistent sample data. Centralizing fixtures avoids
duplication and ensures tests don't drift apart.
"""

import pytest


@pytest.fixture
def sample_chat_request() -> dict:
    """A minimal valid chat completion request matching OpenAI format."""
    return {
        "model": "marine-rag",
        "messages": [{"role": "user", "content": "What is DNV Pt.4 Ch.3?"}],
        "stream": False,
    }


@pytest.fixture
def sample_document_upload() -> dict:
    """A minimal valid document upload request."""
    return {
        "file_name": "dnv-pt4-ch3-2024.pdf",
        "classification_society": "DNV",
        "domain": "structure",
        "version_year": 2024,
    }


@pytest.fixture
def sample_llm_backend() -> dict:
    """A minimal valid LLM backend configuration."""
    return {
        "backend_id": "deepseek-default",
        "backend_type": "deepseek",
        "model_name": "deepseek-chat",
        "is_default": True,
    }
