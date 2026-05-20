# -*- coding: utf-8 -*-
"""
Unit tests for config.py — deploy.yaml parsing and dataclass models.

WHY: Config is the entry point for the entire M2 module. If config parsing
is broken, every downstream component fails. These tests validate that valid
YAML produces correct config objects and invalid input raises clear errors.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from m2_storage.config import (
    ChromaDBConfig,
    LocalFSConfig,
    MeilisearchConfig,
    SQLiteConfig,
    StorageConfig,
    load_config,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_yaml() -> dict:
    """Return the minimal valid Personal-mode config dict."""
    return {
        "deployment_mode": "personal",
        "storage": {
            "vector_store": {
                "backend": "chromadb",
                "chromadb": {
                    "persist_dir": "./data/chromadb",
                    "collection_name": "test_collection",
                },
            },
            "document_index": {
                "backend": "meilisearch",
                "meilisearch": {
                    "host": "http://127.0.0.1:7700",
                    "api_key": "",
                    "index_name": "test_index",
                },
            },
            "relational_db": {
                "backend": "sqlite",
                "sqlite": {"path": "./data/test.db"},
            },
            "file_store": {
                "backend": "local_fs",
                "local_fs": {"root_dir": "./data/files"},
            },
        },
    }


@pytest.fixture
def config_file(valid_yaml: dict) -> Path:
    """Write valid_yaml to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(valid_yaml, f)
        return Path(f.name)


# ---------------------------------------------------------------------------
# Test 1: Valid YAML parses correctly
# ---------------------------------------------------------------------------

def test_load_valid_config(config_file: Path):
    """All fields from a valid YAML must parse into correct types."""
    cfg = load_config(str(config_file))

    assert cfg.deployment_mode == "personal"

    # Vector store
    assert cfg.vector_store.backend == "chromadb"
    assert isinstance(cfg.vector_store.chromadb, ChromaDBConfig)
    assert cfg.vector_store.chromadb.persist_dir == "./data/chromadb"
    assert cfg.vector_store.chromadb.collection_name == "test_collection"

    # Document index
    assert cfg.document_index.backend == "meilisearch"
    assert isinstance(cfg.document_index.meilisearch, MeilisearchConfig)
    assert cfg.document_index.meilisearch.host == "http://127.0.0.1:7700"

    # Relational DB
    assert cfg.relational_db.backend == "sqlite"
    assert isinstance(cfg.relational_db.sqlite, SQLiteConfig)
    assert cfg.relational_db.sqlite.path == "./data/test.db"

    # File store
    assert cfg.file_store.backend == "local_fs"
    assert isinstance(cfg.file_store.local_fs, LocalFSConfig)
    assert cfg.file_store.local_fs.root_dir == "./data/files"


# ---------------------------------------------------------------------------
# Test 2: Missing fields get default values
# ---------------------------------------------------------------------------

def test_default_values():
    """When YAML omits optional fields, defaults must be applied."""
    minimal = {
        "deployment_mode": "personal",
        "storage": {
            "vector_store": {"backend": "chromadb"},
            "document_index": {"backend": "meilisearch"},
            "relational_db": {"backend": "sqlite"},
            "file_store": {"backend": "local_fs"},
        },
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(minimal, f)
        path = f.name

    cfg = load_config(path)

    # ChromaDB defaults
    assert cfg.vector_store.chromadb.persist_dir == "./data/chromadb"
    assert cfg.vector_store.chromadb.collection_name == "marine_rag"
    # Meilisearch defaults
    assert cfg.document_index.meilisearch.host == "http://127.0.0.1:7700"
    assert cfg.document_index.meilisearch.api_key == ""
    # SQLite defaults
    assert cfg.relational_db.sqlite.path == "./data/marine_rag.db"
    # LocalFS defaults
    assert cfg.file_store.local_fs.root_dir == "./data/files"


# ---------------------------------------------------------------------------
# Test 3: Invalid backend raises ValueError
# ---------------------------------------------------------------------------

def test_invalid_backend_raises():
    """An unsupported backend name must raise ValueError with a clear message."""
    invalid = {
        "deployment_mode": "personal",
        "storage": {
            "vector_store": {"backend": "milvus"},
            "document_index": {"backend": "meilisearch"},
            "relational_db": {"backend": "sqlite"},
            "file_store": {"backend": "local_fs"},
        },
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(invalid, f)
        path = f.name

    with pytest.raises(ValueError, match="milvus"):
        load_config(path)


# ---------------------------------------------------------------------------
# Test 4: Missing file raises FileNotFoundError
# ---------------------------------------------------------------------------

def test_missing_file_raises():
    """Passing a non-existent path must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("./nonexistent_config.yaml")
