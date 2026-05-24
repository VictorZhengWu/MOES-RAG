# -*- coding: utf-8 -*-
"""
Tests for M3 Retrieval configuration (RetrievalConfig dataclass).

WHAT: Validates default values, custom overrides, and input validation.
WHY: The config is the single source of truth for all retrieval parameters;
     any misconfiguration here propagates to the entire pipeline.
"""

from __future__ import annotations

import pytest

from m3_retrieval.core.config import RetrievalConfig


class TestRetrievalConfigDefaults:
    """Test that all default values match the specification."""

    def test_default_values(self) -> None:
        """WHY: Default values must match the design spec exactly."""
        cfg = RetrievalConfig()

        # Search parameters
        assert cfg.dense_top_k == 50, (
            f"Expected dense_top_k=50, got {cfg.dense_top_k}"
        )
        assert cfg.sparse_top_k == 20, (
            f"Expected sparse_top_k=20, got {cfg.sparse_top_k}"
        )
        assert cfg.fusion_k == 60, (
            f"Expected fusion_k=60, got {cfg.fusion_k}"
        )
        assert cfg.rerank_top_k == 20, (
            f"Expected rerank_top_k=20, got {cfg.rerank_top_k}"
        )

        # Deduplication
        assert cfg.dedup_threshold == 0.85, (
            f"Expected dedup_threshold=0.85, got {cfg.dedup_threshold}"
        )

        # Cache
        assert cfg.enable_cache is True, (
            f"Expected enable_cache=True, got {cfg.enable_cache}"
        )
        assert cfg.cache_ttl == 3600, (
            f"Expected cache_ttl=3600, got {cfg.cache_ttl}"
        )

        # Context
        assert cfg.context_window == 3, (
            f"Expected context_window=3, got {cfg.context_window}"
        )

        # Models
        assert cfg.embedding_model == "BAAI/bge-m3", (
            f"Expected embedding_model='BAAI/bge-m3', got {cfg.embedding_model}"
        )
        assert cfg.reranker_model == "BAAI/bge-reranker-v2-m3", (
            f"Expected reranker_model='BAAI/bge-reranker-v2-m3', "
            f"got {cfg.reranker_model}"
        )


class TestRetrievalConfigCustom:
    """Test that all fields can be overridden individually."""

    def test_custom_override_all_fields(self) -> None:
        """WHY: Users must be able to tune every parameter for their deployment."""
        cfg = RetrievalConfig(
            dense_top_k=100,
            sparse_top_k=50,
            fusion_k=120,
            rerank_top_k=10,
            dedup_threshold=0.90,
            enable_cache=False,
            cache_ttl=7200,
            context_window=5,
            embedding_model="custom/model",
            reranker_model="custom/reranker",
        )

        assert cfg.dense_top_k == 100
        assert cfg.sparse_top_k == 50
        assert cfg.fusion_k == 120
        assert cfg.rerank_top_k == 10
        assert cfg.dedup_threshold == 0.90
        assert cfg.enable_cache is False
        assert cfg.cache_ttl == 7200
        assert cfg.context_window == 5
        assert cfg.embedding_model == "custom/model"
        assert cfg.reranker_model == "custom/reranker"


class TestRetrievalConfigValidation:
    """Test that invalid values are rejected."""

    def test_dedup_threshold_out_of_range_raises(self) -> None:
        """WHY: dedup_threshold must be in [0, 1]; out-of-range values
        indicate a misconfiguration that could silently corrupt results."""
        with pytest.raises(ValueError, match="dedup_threshold must be"):
            RetrievalConfig(dedup_threshold=1.5)

    def test_negative_dedup_threshold_raises(self) -> None:
        """WHY: Negative threshold makes no semantic sense for similarity."""
        with pytest.raises(ValueError, match="dedup_threshold must be"):
            RetrievalConfig(dedup_threshold=-0.1)

    def test_boundary_values_accepted(self) -> None:
        """WHY: 0.0 and 1.0 are valid edge values - 0 means no dedup,
        1.0 means exact-match-only."""
        cfg_zero = RetrievalConfig(dedup_threshold=0.0)
        assert cfg_zero.dedup_threshold == 0.0

        cfg_one = RetrievalConfig(dedup_threshold=1.0)
        assert cfg_one.dedup_threshold == 1.0
