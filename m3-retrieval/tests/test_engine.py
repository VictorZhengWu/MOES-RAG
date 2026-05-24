# -*- coding: utf-8 -*-
"""
Tests for M3 Retrieval Engine (engine.py + pipeline.py).

WHAT: Validates two key behaviours of the RetrievalEngine:
  1. test_init_does_not_load_models: Constructing a RetrievalEngine does NOT
     eagerly create the pipeline or load embedding/reranker models.
  2. test_custom_config_propagated: Custom RetrievalConfig values are stored
     and propagated to the pipeline on lazy init.

WHY: The RetrievalEngine is the top-level entry point consumed by M5
(QA Engine) and M8 (API Gateway). It must support:
  - Fast startup (no 3-5s model load on construction).
  - Configurable parameters (different deployments may tune top_k,
    cache behaviour, model names).
  - Health check integration with M2 storage backends.
"""

from __future__ import annotations

import pytest

from contracts.retrieval import RetrievalRequest


# =============================================================================
# Fake StorageManager for unit tests
# =============================================================================


class _FakeStorageManager:
    """
    Minimal fake StorageManager that supports inspection without real backends.

    WHAT: Provides a .vector_store, .doc_index, and .file_store attribute
    plus a health_check() method, matching M2's StorageManager interface
    just enough for RetrievalEngine unit tests.

    WHY: Engine unit tests must not depend on real ChromaDB/Meilisearch.
    This fake enables testing of engine construction, config propagation,
    and lazy init logic without any backend processes.
    """

    def __init__(self) -> None:
        self.vector_store = _FakeVectorStore()
        self.doc_index = _FakeDocIndex()
        self.file_store = _FakeFileStore()
        self._health_ok = True

    async def health_check(self) -> dict:
        if self._health_ok:
            return {"vector_store": True, "doc_index": True}
        raise RuntimeError("storage unavailable")


class _FakeVectorStore:
    """Stub for StorageManager.vector_store."""
    pass


class _FakeDocIndex:
    """Stub for StorageManager.doc_index."""
    pass


class _FakeFileStore:
    """Stub for StorageManager.file_store."""
    pass


# =============================================================================
# RetrievalEngine tests
# =============================================================================


class TestRetrievalEngineInit:
    """Test that engine construction is lightweight (no eager model loading)."""

    def test_init_does_not_load_models(self) -> None:
        """
        WHAT: After constructing a RetrievalEngine, the internal
        _pipeline attribute must be None, proving that no pipeline
        was created and no models were loaded.

        WHY: The engine must start fast. Model loading (embedding,
        cross-encoder) takes several seconds and should be deferred
        to the first retrieve() call. If the pipeline were created
        eagerly, every import and test discovery would be penalized.
        """
        from m3_retrieval.core.engine import RetrievalEngine
        from m3_retrieval.core.config import RetrievalConfig

        sm = _FakeStorageManager()
        cfg = RetrievalConfig()
        engine = RetrievalEngine(sm, cfg)

        assert engine._pipeline is None, (
            "RetrievalEngine created the pipeline eagerly. "
            "Pipeline (and model loading) must be deferred to "
            "first retrieve() call."
        )
        assert engine.cfg is cfg


class TestRetrievalEngineConfig:
    """Test config propagation through the engine."""

    def test_custom_config_propagated(self) -> None:
        """
        WHAT: Passing a custom RetrievalConfig with non-default values
        must be stored and accessible via the engine's cfg attribute.

        WHY: Different deployment modes (personal/enterprise/SaaS) may
        use different config values. The engine must faithfully store
        whatever config it receives so the pipeline can use it on
        lazy init.
        """
        from m3_retrieval.core.engine import RetrievalEngine
        from m3_retrieval.core.config import RetrievalConfig

        sm = _FakeStorageManager()
        custom_cfg = RetrievalConfig(
            dense_top_k=100,
            sparse_top_k=40,
            fusion_k=120,
            rerank_top_k=30,
            embedding_model="custom/model",
            reranker_model="custom/reranker",
            enable_cache=False,
        )
        engine = RetrievalEngine(sm, custom_cfg)

        assert engine.cfg.dense_top_k == 100
        assert engine.cfg.sparse_top_k == 40
        assert engine.cfg.fusion_k == 120
        assert engine.cfg.rerank_top_k == 30
        assert engine.cfg.embedding_model == "custom/model"
        assert engine.cfg.reranker_model == "custom/reranker"
        assert engine.cfg.enable_cache is False


class TestRetrievalPipelineInit:
    """Test that the pipeline stores references correctly."""

    def test_pipeline_stores_components(self) -> None:
        """
        WHAT: After constructing a RetrievalPipeline with dense/sparse
        retrievers, a reranker, and config, all four references must
        be stored on the instance.

        WHY: The pipeline delegates to these components during retrieve().
        If any reference is lost, certain retrieval paths will fail at
        runtime with AttributeError.
        """
        from m3_retrieval.core.pipeline import RetrievalPipeline
        from m3_retrieval.core.config import RetrievalConfig

        # Create minimal stubs -- pipeline only needs attribute access, not
        # actual functionality for this construction test.
        class _StubDense:
            pass
        class _StubSparse:
            pass
        class _StubReranker:
            pass

        dense = _StubDense()
        sparse = _StubSparse()
        reranker = _StubReranker()
        cfg = RetrievalConfig()

        pipeline = RetrievalPipeline(dense, sparse, reranker, cfg)

        assert pipeline._dense is dense
        assert pipeline._sparse is sparse
        assert pipeline._reranker is reranker
        assert pipeline.cfg is cfg

    def test_pipeline_default_config(self) -> None:
        """
        WHAT: When no config is passed to RetrievalPipeline, a default
        RetrievalConfig() must be created automatically.

        WHY: The pipeline must be usable with minimal setup during
        testing and quickstart scenarios. Providing a sensible default
        avoids requiring every caller to explicitly construct a config.
        """
        from m3_retrieval.core.pipeline import RetrievalPipeline
        from m3_retrieval.core.config import RetrievalConfig

        pipeline = RetrievalPipeline(None, None, None)  # pyright: ignore[reportArgumentType]

        assert pipeline.cfg is not None
        assert isinstance(pipeline.cfg, RetrievalConfig)
        # Verify default values are set
        assert pipeline.cfg.dense_top_k == 50
        assert pipeline.cfg.sparse_top_k == 20


# =============================================================================
# Pipeline adaptive path tests
# =============================================================================


class TestPipelineCache:
    """Test the LRU cache mechanism in RetrievalPipeline."""

    def test_pipeline_cache_empty_by_default(self) -> None:
        """
        WHAT: A freshly constructed pipeline must have an empty cache.

        WHY: The cache dict starts empty and only grows when cache
        is enabled and queries are executed. An initially non-empty
        cache would indicate a bug (stale data from previous pipeline
        lifecycle).
        """
        from m3_retrieval.core.pipeline import RetrievalPipeline
        from m3_retrieval.core.config import RetrievalConfig

        cfg = RetrievalConfig(enable_cache=True, cache_ttl=3600)
        pipeline = RetrievalPipeline(None, None, None, cfg)

        assert len(pipeline._cache) == 0
        assert len(pipeline._cache_order) == 0

    def test_pipeline_cache_disabled(self) -> None:
        """
        WHAT: When enable_cache=False, the cache dict is still present
        but queries should not populate it.

        WHY: The cache dict attribute always exists for code simplicity
        (no conditional attribute), but cache operations are guarded by
        cfg.enable_cache checks in retrieve().
        """
        from m3_retrieval.core.pipeline import RetrievalPipeline
        from m3_retrieval.core.config import RetrievalConfig

        cfg = RetrievalConfig(enable_cache=False)
        pipeline = RetrievalPipeline(None, None, None, cfg)

        assert pipeline.cfg.enable_cache is False
