# -*- coding: utf-8 -*-
"""
Retrieval Pipeline -- 7-stage adaptive retrieval orchestration.

WHAT: The RetrievalPipeline class orchestrates the complete retrieval flow:
  1. Query Analysis (extract metadata, keywords, semantic core)
  2a. Dense Retrieval (vector similarity via ChromaDB)  ─┐
  2b. Sparse Retrieval (BM25 keyword via Meilisearch)   ─┤ parallel
  3. Fusion (RRF merge of dense + sparse results)        ─┘
  4. Reranking (cross-encoder precision filter)
  5. Context Expansion (neighbouring chunks -- placeholder)
  6. Deduplication (Jaccard-based near-duplicate removal)
  7. Result Assembly (top_k truncation, citation)

It supports three adaptive paths to balance speed and quality:
  - Fast path (exact match): BM25 only, bypasses embedding and reranking.
  - Medium path (keyword query): Dense + sparse + fusion, skip reranking.
  - Full path (natural language): All 7 stages, highest quality.

An in-memory LRU cache (with configurable size) accelerates repeated
queries by returning cached results directly without re-executing the
pipeline.

WHY: A multi-stage retrieval pipeline is the standard architecture for
production RAG systems. Each stage addresses a different failure mode:
  - Dense alone misses exact codes (AH36, DNV-ST-N001).
  - Sparse alone misses semantic paraphrases ("welding requirements"
    vs "joining process specifications").
  - Without reranking, fusion results have noisy ordering.
  - Without dedup, overlapping chunks waste the LLM context window.
  - Without caching, repeated queries incur unnecessary compute cost.

Key design decisions:
  - Async throughout: all retrieval backend calls are async (ChromaDB,
    Meilisearch), so the pipeline uses asyncio.gather for parallel
    dense+sparse execution.
  - LRU cache: simple dict + order list implementation rather than
    functools.lru_cache, because retrieval results (RetrievedContext)
    contain mutable objects and the cache needs TTL-awareness.
  - Adaptive path detection: reuses the query_analyzer's _is_exact_match
    and _is_keyword_query helpers, which are already tested and proven.
  - Component injection: DenseRetriever, SparseRetriever, and Reranker
    are injected via constructor, allowing easy mocking in tests and
    backend swapping in deploy.yaml.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import TYPE_CHECKING

from contracts.retrieval import RetrievedContext, RetrievalRequest, ScoredChunk

from m3_retrieval.core.config import RetrievalConfig
from m3_retrieval.stages.context_expander import deduplicate_chunks, expand_context
from m3_retrieval.stages.fusion import rrf_fusion
from m3_retrieval.stages.query_analyzer import (
    QueryAnalysis,
    _is_exact_match,
    _is_keyword_query,
    analyze_query,
)

if TYPE_CHECKING:
    from m3_retrieval.stages.dense_retriever import DenseRetriever
    from m3_retrieval.stages.reranker import Reranker
    from m3_retrieval.stages.sparse_retriever import SparseRetriever


# =============================================================================
# Helpers
# =============================================================================


def _cache_key(request: RetrievalRequest) -> str:
    """
    Build a deterministic cache key from a RetrievalRequest.

    WHAT: Hashes the query, top_k, filters, and strategy flags into a
    compact hex string. The hash ensures that requests with different
    parameters produce different cache keys.

    WHY: Cache keys must be deterministic for the same input. Using
    hashlib.md5 gives a short, fixed-length key that is safe for
    in-memory caching (no security concerns with md5 since this is
    not exposed externally). The key includes all parameters that
    affect the retrieval result, so two equivalent requests always
    hit the same cache entry.

    Args:
        request: The retrieval request to hash.

    Returns:
        A 32-character hex digest string.
    """
    # WHAT: build a canonical JSON representation of the request.
    # sort_keys=True ensures deterministic serialization regardless
    # of dict insertion order.
    raw: str = json.dumps(
        {
            "query": request.query,
            "top_k": request.top_k,
            "filters": request.filters,
            "enable_query_rewriting": request.enable_query_rewriting,
            "enable_hyde": request.enable_hyde,
            "fusion_strategy": request.fusion_strategy,
        },
        sort_keys=True,
        default=str,  # Handle non-JSON-serializable values gracefully
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _build_filters(qa: QueryAnalysis) -> dict | None:
    """
    Build metadata filters from a QueryAnalysis for storage backends.

    WHAT: Translates QueryAnalysis fields into a filter dict that both
    ChromaDB (VectorStore) and Meilisearch (DocumentIndex) understand.
    The filter dict uses the key names expected by the storage backends:
      - classification_society (if detected)
      - chapter_section (if detected)
      - version_year (if detected)

    Only includes filters for fields that were actually detected.
    None means no filters to apply.

    WHY: Metadata filtering is the first precision layer in the retrieval
    pipeline. Before any semantic similarity or BM25 keyword matching, we
    narrow the candidate set to only documents matching the user's detected
    constraints (e.g. only DNV documents, only chapter Pt.3 Ch.2).
    This dramatically improves precision for structured queries.

    Args:
        qa: The QueryAnalysis output from analyze_query().

    Returns:
        A dict of filter key-value pairs, or None if no filters detected.
    """
    filters: dict = {}

    if qa.classification_society is not None:
        filters["classification_society"] = qa.classification_society

    if qa.chapter_section is not None:
        filters["chapter_section"] = qa.chapter_section

    if qa.version_year is not None:
        filters["version_year"] = qa.version_year

    # WHAT: return None instead of empty dict when no filters detected.
    # WHY: storage backends may treat empty dict {} differently from
    # None (e.g. ChromaDB treats {} as "no filter" but Meilisearch
    # may treat it as "empty filter expression"). None is unambiguous.
    return filters if filters else None


# =============================================================================
# RetrievalPipeline
# =============================================================================


class RetrievalPipeline:
    """
    7-stage adaptive retrieval pipeline with LRU result cache.

    WHAT: Orchestrates the complete retrieval flow from raw query to
    ranked, deduplicated results. Supports three adaptive paths that
    automatically trade off speed vs quality based on query type.

    Components (injected via constructor):
      - _dense: DenseRetriever -- vector similarity via ChromaDB
      - _sparse: SparseRetriever -- BM25 keyword via Meilisearch
      - _reranker: Reranker -- cross-encoder precision filter

    Cache: An in-memory LRU dict that stores RetrievedContext objects
    keyed by request fingerprint. When cache is enabled (cfg.enable_cache),
    identical queries with identical parameters return cached results in
    sub-millisecond time without re-executing the pipeline.

    Usage::

        pipeline = RetrievalPipeline(dense, sparse, reranker, config)
        context = await pipeline.retrieve(RetrievalRequest(query="...", top_k=20))
    """

    def __init__(
        self,
        dense_retriever: DenseRetriever | None,
        sparse_retriever: SparseRetriever | None,
        reranker: Reranker | None,
        config: RetrievalConfig | None = None,
    ) -> None:
        """
        Create a RetrievalPipeline with injected components.

        WHAT: Stores references to the three retrieval backends and
        configuration. Initializes an empty cache. No models are loaded
        at this point -- loading is deferred to first retrieve() call.

        Components may be None for testing or for adaptive paths that
        don't use all stages (e.g. BM25-only path doesn't need the
        dense retriever or reranker).

        WHY: Injection allows the engine (engine.py) to control which
        concrete implementations to use, making the pipeline testable
        with fakes/mocks and swappable for different backends.

        Args:
            dense_retriever: DenseRetriever instance or None.
            sparse_retriever: SparseRetriever instance or None.
            reranker: Reranker instance or None.
            config: RetrievalConfig instance. If None, uses defaults.
        """
        # WHAT: dense/vector retrieval component (optional for fast paths)
        self._dense = dense_retriever

        # WHAT: sparse/BM25 retrieval component (optional)
        self._sparse = sparse_retriever

        # WHAT: cross-encoder reranker component (optional for medium path)
        self._reranker = reranker

        # WHAT: pipeline configuration with all tunable parameters
        # WHY default: avoids requiring callers to always pass a config
        self.cfg = config or RetrievalConfig()

        # WHAT: in-memory result cache dict: cache_key -> RetrievedContext
        # WHY dict: O(1) lookup by key. Paired with _cache_order for LRU eviction.
        self._cache: dict[str, RetrievedContext] = {}

        # WHAT: ordered list of cache keys, most recent last.
        # WHY: enables O(1) LRU eviction: pop(0) removes the oldest entry.
        self._cache_order: list[str] = []

    # =========================================================================
    # Public API
    # =========================================================================

    async def retrieve(self, request: RetrievalRequest) -> RetrievedContext:
        """
        Execute the full retrieval pipeline for a query request.

        WHAT: The main entry point. Performs:
          1. Cache check (if enabled): return cached result if found.
          2. Query analysis: extract metadata, keywords, semantic query.
          3. Build metadata filters from QueryAnalysis.
          4. Adaptive path selection: choose fast/medium/full path.
          5. Execute the chosen path (async parallel retrieval).
          6. Deduplicate results (Jaccard-based).
          7. Truncate to request.top_k.
          8. Cache write (if enabled): store result for future reuse.

        WHY: This method is the single integration point consumed by
        RetrievalEngine and, through it, by M5 (QA Engine). All pipeline
        logic is encapsulated here so callers don't need to understand
        the internal stages.

        Args:
            request: A RetrievalRequest with query, top_k, filters, and
                strategy flags.

        Returns:
            A RetrievedContext containing the ranked, deduplicated chunks.
        """
        start_time: float = time.perf_counter()

        # ---- Stage 0: Cache check ----
        # WHAT: if caching is enabled and the result is already cached,
        # return it immediately without re-executing the pipeline.
        # WHY: repeated queries (e.g. pagination, re-query) should not
        # incur the full compute cost of embedding + retrieval + reranking.
        if self.cfg.enable_cache:
            key: str = _cache_key(request)
            if key in self._cache:
                return self._cache[key]
        else:
            key = ""  # Not used when cache is disabled

        # ---- Stage 1: Query Analysis ----
        # WHAT: extract classification_society, chapter_section,
        # version_year, keywords, and semantic_query from raw text.
        # WHY: separates structured metadata from the semantic core.
        # The metadata becomes filter constraints; the semantic core
        # goes to the embedding model; keywords go to BM25.
        qa: QueryAnalysis = analyze_query(request.query)

        # WHAT: build metadata filters from extracted fields.
        # WHY: filters narrow the search space before ranking, improving
        # precision for structured queries (e.g. "DNV Pt.3 Ch.2 hull").
        filters: dict | None = _build_filters(qa)

        # ---- Adaptive Path Selection ----
        # WHAT: choose the retrieval path based on query characteristics.
        # WHY: not all queries need the full 7-stage pipeline. Exact
        # match queries (e.g. "DNV-ST-N001") only need BM25. Short
        # keyword queries skip the expensive cross-encoder reranker.
        # This saves 1-3 seconds per query without quality loss.

        if _is_exact_match(request.query):
            # Fast path: regulation identifier -> BM25 only.
            # No embedding model loading, no fusion, no reranking.
            # Latency: ~50-100ms (Meilisearch round-trip).
            chunks: list[ScoredChunk] = await self._bm25_only(
                qa.keywords, filters
            )
        elif _is_keyword_query(request.query):
            # Medium path: short keyword query -> hybrid without rerank.
            # Dense + sparse + fusion. Skip reranker to save ~1s.
            # Latency: ~100-300ms.
            chunks = await self._hybrid_no_rerank(
                qa.semantic_query, qa.keywords, filters
            )
        else:
            # Full path: natural language query -> all 7 stages.
            # Dense + sparse + fusion + rerank + dedup.
            # Latency: ~500-2000ms (includes cross-encoder time).
            chunks = await self._full_pipeline(
                qa.semantic_query, qa.keywords, filters
            )

        # ---- Stage 6: Deduplication ----
        # WHAT: remove near-duplicate adjacent chunks using Jaccard.
        # WHY: overlapping chunks from dense+sparse fusion and adjacent
        # document sections produce redundant results. Dedup ensures
        # the LLM context window is used efficiently.
        chunks = deduplicate_chunks(chunks, self.cfg.dedup_threshold)

        # ---- Stage 7: Result Assembly ----
        # WHAT: truncate to the requested top_k and compute latency.
        # WHY: the pipeline may produce more candidates than requested
        # (e.g. fusion_k=60, but request.top_k=20). We slice to the
        # exact number the caller wants.
        elapsed_ms: float = (time.perf_counter() - start_time) * 1000.0
        result = RetrievedContext(
            chunks=chunks[:request.top_k],
            total_found=len(chunks),
            search_latency_ms=elapsed_ms,
        )

        # ---- Cache write ----
        # WHAT: store the result in the LRU cache for future reuse.
        # Evict the oldest entry if cache exceeds max size.
        # WHY: cache population ensures the next identical query is fast.
        if self.cfg.enable_cache:
            self._cache[key] = result
            self._cache_order.append(key)
            # LRU eviction: pop the oldest (first) entry when over capacity.
            while len(self._cache_order) > self.cfg.cache_max_size:
                oldest_key: str = self._cache_order.pop(0)
                del self._cache[oldest_key]

        return result

    # =========================================================================
    # Adaptive retrieval paths
    # =========================================================================

    async def _bm25_only(
        self,
        keywords: list[str],
        filters: dict | None,
    ) -> list[ScoredChunk]:
        """
        Fast path: BM25 keyword search only (exact match queries).

        WHAT: Calls the sparse retriever with the extracted keywords.
        Does NOT use dense embedding or reranking.

        This is the fastest path, suitable for regulation identifier
        queries like "DNV-ST-N001" or "ABS-RULE-2023" where exact
        keyword matching is all that is needed.

        WHY: Exact match queries have deterministic answers. There is
        no benefit to semantic similarity or cross-encoder scoring
        when the query is a document identifier. Skipping embedding
        and reranking saves 3-5 seconds of model loading and inference.

        Args:
            keywords: Extracted technical keywords from QueryAnalysis.
            filters: Metadata filters (classification society, chapter, etc.).

        Returns:
            List of BM25-ranked ScoredChunk results.
        """
        # WHAT: if no sparse retriever is available, return empty.
        # WHY: graceful degradation -- some test configurations may not
        # have a sparse retriever. Returning [] is better than crashing.
        if self._sparse is None:
            return []

        return await self._sparse.search(keywords, filters)

    async def _hybrid_no_rerank(
        self,
        semantic_query: str,
        keywords: list[str],
        filters: dict | None,
    ) -> list[ScoredChunk]:
        """
        Medium path: dense + sparse retrieval + RRF fusion (no reranker).

        WHAT: Runs dense and sparse retrievers in parallel via
        asyncio.gather, then fuses results with RRF. Skips the
        expensive cross-encoder reranker.

        This is the balanced path for short keyword queries with
        proper nouns (e.g. "DNV hull welding"). It captures both
        semantic and keyword signals without the ~1s reranker cost.

        WHY: Short keyword queries have enough signal for fusion to
        produce reasonable rankings. The cross-encoder adds precision
        but costs ~1s. For keyword queries, the precision gain is
        marginal because BM25 already ranks exact matches high, and
        the cross-encoder mainly corrects semantic ambiguities that
        keyword queries don't have.

        Args:
            semantic_query: Cleaned semantic text for embedding.
            keywords: Extracted keywords for BM25 search.
            filters: Metadata filters.

        Returns:
            List of fused ScoredChunk results (source="fusion").
        """
        tasks: list = []

        # WHAT: launch dense and sparse retrieval tasks.
        # WHY: these are independent and can run in parallel, halving
        # the retrieval wall-clock time from ~200ms to ~100ms.
        if self._dense is not None and semantic_query:
            # Compute query embedding, then search ChromaDB
            query_vec: list[float] = self._dense._embedder.encode_query(
                semantic_query
            )
            tasks.append(self._dense.search(query_vec, filters))
        else:
            tasks.append(asyncio.sleep(0))  # No-op placeholder

        if self._sparse is not None and keywords:
            tasks.append(self._sparse.search(keywords, filters))
        else:
            tasks.append(asyncio.sleep(0))

        # WHAT: wait for both retrievers to complete.
        # WHY: asyncio.gather runs both coroutines concurrently.
        results: list = await asyncio.gather(*tasks)

        # WHAT: extract the actual ScoredChunk lists from results.
        # Some elements may be None (from the sleep(0) placeholder).
        result_sets: list[list[ScoredChunk]] = [
            r for r in results if isinstance(r, list)
        ]

        # WHAT: fuse the result sets with RRF.
        # WHY: RRF combines the ranked lists without requiring score
        # normalization, producing a single ranked output.
        # We use fusion_k as the number of fused results to return.
        return rrf_fusion(
            result_sets,
            k=self.cfg.fusion_k,
            top_k=self.cfg.rerank_input_k,
        )

    async def _full_pipeline(
        self,
        semantic_query: str,
        keywords: list[str],
        filters: dict | None,
    ) -> list[ScoredChunk]:
        """
        Full path: all 7 stages including cross-encoder reranking.

        WHAT: Runs parallel dense+sparse retrieval, RRF fusion, then
        cross-encoder reranking for maximum precision. This is the
        highest-quality path for natural language queries.

        Pipeline: dense || sparse -> RRF fusion -> cross-encoder rerank

        WHY: Natural language queries (e.g. "what are the welding
        requirements for AH36 steel in offshore structures?") benefit
        from all stages:
          - Dense captures semantic similarity.
          - Sparse captures exact keyword matches (AH36, welding).
          - Fusion combines both signals.
          - Reranker corrects fusion ordering errors.

        The ~1s reranker cost is justified here because natural language
        queries have more ambiguity than keyword queries, and the
        cross-encoder significantly improves result precision.

        Args:
            semantic_query: Cleaned semantic text for embedding.
            keywords: Extracted keywords for BM25 search.
            filters: Metadata filters.

        Returns:
            List of reranked ScoredChunk results.
        """
        # ---- Step 1: Hybrid retrieval + RRF fusion ----
        # WHAT: reuse _hybrid_no_rerank for the first two stages.
        # WHY: the dense+sparse+fusion logic is identical to the medium
        # path. Only the post-fusion reranking differs.
        fused: list[ScoredChunk] = await self._hybrid_no_rerank(
            semantic_query, keywords, filters
        )

        # ---- Step 2: Cross-encoder reranking ----
        # WHAT: apply the reranker to the fused results for precision.
        # WHY: the cross-encoder directly compares the query with each
        # chunk's full text, capturing fine-grained semantic interactions
        # that cosine similarity and BM25 miss.
        if self._reranker is not None and fused:
            # Use the semantic query for the reranker (cleaned text
            # without technical codes, which the reranker would not
            # understand as well).
            fused = await self._reranker.rerank(semantic_query, fused)

        return fused
