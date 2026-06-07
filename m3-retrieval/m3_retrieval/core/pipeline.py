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
    strip_section,
    build_fallback_chain,
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


def _build_filters(qa: QueryAnalysis, default_year_range: int = 3) -> dict | None:
    """
    Build metadata filters from a QueryAnalysis for storage backends.

    WHAT: Translates QueryAnalysis fields into a filter dict that both
    ChromaDB (VectorStore) and Meilisearch (DocumentIndex) understand.
    The filter dict uses the key names expected by the storage backends:
      - classification_society (if detected)
      - chapter_section (if detected, enables hierarchical navigation)
      - version_year (if detected, or default recent range for time-aware)

    Only includes filters for fields that were actually detected,
    except for version_year which falls back to a default range.

    WHY: Metadata filtering is the first precision layer in the retrieval
    pipeline. Before any semantic similarity or BM25 keyword matching, we
    narrow the candidate set to only documents matching the user's detected
    constraints (e.g. only DNV documents, only chapter Pt.3 Ch.2).
    This dramatically improves precision for structured queries.

    Time-aware default: if no explicit year is detected in the query,
    we filter to the last N years to prevent mixing outdated norms with
    current ones. This avoids compliance risk (e.g., applying a deprecated
    2018 formula when the 2024 version changed the calculation).

    Hierarchical navigation: when chapter_section is detected (e.g., user
    asks "Ch.3 welding"), the filter narrows the search from 50 pages to
    5 pages, providing 5-10x precision improvement.

    Args:
        qa: The QueryAnalysis output from analyze_query().
        default_year_range: Number of recent years to search when no
            explicit year is in the query. 0 = disable time filtering.

    Returns:
        A dict of filter key-value pairs, or None if no filters detected.
    """
    import datetime

    filters: dict = {}

    # Classification society filter (e.g., "DNV", "ABS")
    if qa.classification_society is not None:
        filters["classification_society"] = qa.classification_society

    # Hierarchical navigation: narrow search to specific chapter/section
    if qa.chapter_section is not None:
        filters["chapter_section"] = qa.chapter_section

    # Time-aware retrieval: explicit year from query, or default range
    if qa.version_year is not None:
        filters["version_year"] = qa.version_year
    elif default_year_range > 0:
        current_year: int = datetime.datetime.now().year
        min_year: int = current_year - default_year_range
        filters["version_year"] = str(min_year)  # ChromaDB filter: >= min_year

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
    # Hierarchical Chapter Fallback
    # =========================================================================

    async def _execute_path(
        self, query: str, qa: QueryAnalysis, filters: dict | None
    ) -> list[ScoredChunk]:
        """Execute the appropriate retrieval path for the current filter level."""
        if _is_exact_match(query):
            return await self._bm25_only(qa.keywords, filters)
        elif _is_keyword_query(query):
            return await self._hybrid_no_rerank(qa.semantic_query, qa.keywords, filters)
        else:
            return await self._full_pipeline(qa.semantic_query, qa.keywords, filters)

    async def _retrieve_with_chapter_fallback(
        self, query: str, qa: QueryAnalysis
    ) -> list[ScoredChunk]:
        """
        Retrieve with progressive broadening of chapter filter.

        WHAT: Builds a fallback chain from the chapter_section (e.g.,
        ["Pt.4 Ch.3 §2.1", "Pt.4 Ch.3", "Pt.4", None]) and tries each
        filter level until enough results are found.

        WHY: Prevent zero-result queries when the user's section reference
        doesn't exactly match the extracted metadata. Falls back one level
        at a time: section → chapter → part → no filter.
        """
        min_results: int = 3

        if qa.chapter_section:
            fallback_chain: list[str | None] = build_fallback_chain(qa.chapter_section)
        else:
            fallback_chain = [None]

        best_chunks: list[ScoredChunk] = []

        for level in fallback_chain:
            if level:
                qa.chapter_section = level
            else:
                qa.chapter_section = None
            filters = _build_filters(qa, self.cfg.default_year_range)
            level_chunks = await self._execute_path(query, qa, filters)
            if level_chunks:
                best_chunks = level_chunks
                if len(best_chunks) >= min_results:
                    break

        return best_chunks

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

        # ---- Stage 1a: HyDE hypothesis generation (if enabled) ----
        if request.enable_hyde and self.cfg.hyde_enabled:
            hypothesis: str = await self._generate_hyde_hypothesis(request.query)
            if hypothesis and hypothesis != request.query:
                qa.semantic_query = hypothesis

        # ---- Stage 1b: Hierarchical Chapter Fallback Retrieval ----
        # WHAT: Try progressively broader chapter filters. If the query
        # mentions "Pt.4 Ch.3 §2.1" but §2.1 yields too few results,
        # retry with "Pt.4 Ch.3", then "Pt.4", then no chapter filter.
        # WHY: Chapter-based queries in marine domain must not return empty
        # just because section numbering doesn't match perfectly.
        chunks: list[ScoredChunk] = await self._retrieve_with_chapter_fallback(
            request.query, qa
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

    async def retrieve_propositions(
        self, query: str, top_k: int = 20, filters: dict | None = None
    ) -> list[ScoredChunk]:
        """
        Search the propositions collection for atomic facts.

        WHAT: Embeds the query and searches the dedicated propositions
              ChromaDB collection (separate from chunks). Returns the
              top-K matching atomic facts.

        WHY: Propositions are self-contained facts extracted by LLM at
             index time. Searching them directly means the LLM gets
             precise answers ("EH36 preheat = 150°C") instead of scanning
             200-word paragraphs.
        """
        if self._dense is None:
            return []

        try:
            from m3_retrieval.embeddings.embedder import Embedder
            embedder = Embedder(self.cfg.embedding_model)
            query_vec = embedder.encode_query(query)

            # Search propositions collection (not the default chunks collection)
            results = await self._dense._sm.vector_store.search(
                query_vector=query_vec,
                top_k=top_k,
                filters=filters,
                collection_name=getattr(
                    self.cfg, "propositions_collection", "marine_rag_propositions"
                ),
            )
            return [
                ScoredChunk(chunk=c, score=s, source="proposition", citation=_build_citation(c))
                for c, s in results
            ]
        except Exception:
            return []

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

    async def _generate_hyde_hypothesis(self, query: str) -> str:
        """
        Generate a hypothetical ideal answer for HyDE embedding.

        WHAT: Calls a lightweight LLM to write a short technical paragraph
        that a hypothetical ideal document would contain about the query.
        The HYPOTHESIS TEXT (not the query) is then embedded and used for
        vector search, bridging the semantic gap between terse user queries
        (e.g. "EH36 preheat") and verbose technical documents.

        WHY: Short, terminology-heavy queries have poor semantic overlap with
        full-sentence document text. A hypothetical answer expands the query
        into the language distribution of the target documents, giving the
        embedding model more signal to work with. This is a proven technique
        (HyDE, Gao et al. 2022) that costs one LLM call per query.

        Falls back to the original query if the LLM is unreachable.
        """
        import httpx

        prompt = (
            f"Write a short technical paragraph (3-5 sentences) answering "
            f"this question about ship and offshore engineering: {query}\n\n"
            f"Include specific technical values and classification society "
            f"references where relevant. Write in English."
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.cfg.hyde_llm_url}/chat/completions",
                    json={
                        "model": self.cfg.hyde_llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 200,
                        "temperature": 0.7,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    hypothesis = data["choices"][0]["message"]["content"].strip()
                    if hypothesis:
                        return hypothesis
        except Exception:
            pass  # Graceful fallback to original query

        return query  # Fallback: use original query as embedding text

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
