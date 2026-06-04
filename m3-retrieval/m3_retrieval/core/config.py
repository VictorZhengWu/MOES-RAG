# -*- coding: utf-8 -*-
"""
Retrieval configuration dataclass for the M3 Retrieval Engine.

WHAT: A single dataclass (RetrievalConfig) that holds all tunable parameters
for the retrieval pipeline: search depths, deduplication, caching, context
windows, and model names.

WHY: Centralising all configuration in one typed dataclass ensures that:
  1. Every parameter has an explicit default, documented in one place.
  2. Type hints give IDE autocomplete for all consumers.
  3. Validation runs at construction time (via __post_init__) rather than
     silently accepting invalid values that cause mysterious failures later
     in the pipeline.
  4. The dataclass can be serialised/deserialised for deploy.yaml overrides.

Key design decisions:
  - Dataclass (not pydantic): intentionally avoids a heavy dependency for a
    simple configuration container. Validation is simple (one range check)
    and doesn't warrant a validation framework.
  - __post_init__ for range validation: raises ValueError eagerly so that
    misconfiguration is caught at startup, not mid-retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievalConfig:
    """
    Complete configuration for one retrieval pipeline instance.

    WHAT: Holds all parameters that control retrieval behaviour:
      - Search parameters (how many candidates to retrieve from each backend).
      - Deduplication threshold (cosine similarity above which chunks are
        considered duplicates and merged).
      - Cache settings (whether to cache embeddings and search results).
      - Context window (how many neighbouring chunks to include in context
        expansion around a matched chunk).
      - Model names (which embedding and reranking models to use).

    WHY dataclass: provides a single typed object that can be passed through
    the entire pipeline. Each stage reads only the fields it needs. The
    __post_init__ hook validates critical invariants at construction time.

    All fields have defaults that match the design spec (dense_top_k=50,
    sparse_top_k=20, fusion_k=60, rerank_top_k=20, dedup_threshold=0.85,
    enable_cache=True, cache_ttl=3600, context_window=3,
    embedding_model='BAAI/bge-m3', reranker_model='BAAI/bge-reranker-v2-m3').
    """

    # ---- Search parameters --------------------------------------------------
    # WHY separate top_k per backend: dense retrieval (semantic) typically
    # needs more candidates because it's approximate; sparse/BM25 retrieval
    # is more precise and needs fewer. fusion_k controls the combined pool
    # size before reranking.

    dense_top_k: int = 50
    """Number of top candidates to retrieve from the dense/embedding backend."""

    sparse_top_k: int = 20
    """Number of top candidates to retrieve from the sparse/BM25 backend."""

    fusion_k: int = 60
    """Number of candidates after fusion (RRF or weighted) to pass to reranker."""

    rerank_top_k: int = 20
    """Number of final results to return after reranking."""

    rerank_input_k: int = 50
    """Number of fused results to pass to the reranker.
    The reranker processes this many candidates and outputs rerank_top_k.
    Must be >= rerank_top_k. Default 50."""

    # ---- Deduplication ------------------------------------------------------
    dedup_threshold: float = 0.85
    """Cosine similarity threshold above which two chunks are merged.
    Must be in [0.0, 1.0]. 0.0 = no dedup; 1.0 = only exact matches."""

    # ---- Cache --------------------------------------------------------------
    enable_cache: bool = True
    """Whether to cache embeddings and search results for faster repeat queries."""

    cache_ttl: int = 3600
    """Time-to-live for cached entries in seconds (default: 1 hour)."""

    cache_max_size: int = 128
    """Maximum number of entries in the LRU result cache.
    When exceeded, the oldest entry is evicted. Default 128."""

    # ---- Context ------------------------------------------------------------
    context_window: int = 3
    """Number of neighbouring chunks to include in context expansion.
    E.g. window=3 means 3 chunks before + 3 chunks after the matched chunk."""

    # ---- Models -------------------------------------------------------------
    embedding_model: str = "BAAI/bge-m3"
    """HuggingFace model name or path for the embedding model (dense + sparse)."""

    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    """HuggingFace model name or path for the cross-encoder reranker."""

    # ---- HyDE (Hypothetical Document Embeddings) --------------------------
    hyde_enabled: bool = False
    """Whether to use HyDE for query enhancement.
    When True, the pipeline generates a hypothetical answer to the query,
    embeds THAT, and uses the hypothesis embedding for vector search.
    This bridges the semantic gap between short user queries (e.g. 'EH36
    preheat') and the verbose technical language in documents."""

    hyde_llm_url: str = "http://localhost:11434/v1"
    """OpenAI-compatible API base URL for the LLM used by HyDE."""

    hyde_llm_model: str = "DeepSeek-V3"
    """Model name for the HyDE hypothesis generator."""

    # ---- Time-Aware Retrieval --------------------------------------------
    default_year_range: int = 3
    """Number of recent years to search when no explicit year is specified.
    When the query doesn't contain a year reference, the filter is set to
    version_year >= (current_year - default_year_range). This prevents
    mixing outdated norms with current ones. Set to 0 to disable.
    Example: default_year_range=3 in 2026 → version_year >= 2023."""

    # ---- Hierarchical Navigation -----------------------------------------
    enable_chapter_filter: bool = True
    """When True, detected chapter_section numbers are used as metadata
    filters to narrow the search space before ranking. This leverages
    the natural tree structure of classification society documents
    (Pt.→Ch.→Section→Clause) for 5-10x precision improvement on
    chapter-specific queries."""

    def __post_init__(self) -> None:
        """
        Validate config invariants after dataclass __init__.

        WHAT: Checks that dedup_threshold is within the valid range [0.0, 1.0].

        WHY eager validation: if someone passes dedup_threshold=2.5 in a
        deploy.yaml override, we want to fail immediately at startup with a
        clear error message, rather than silently producing incorrect
        deduplication behaviour hours later in production.
        """
        # Validate dedup_threshold is a probability in [0, 1]
        if not (0.0 <= self.dedup_threshold <= 1.0):
            raise ValueError(
                f"dedup_threshold must be in [0.0, 1.0], "
                f"got {self.dedup_threshold}"
            )
