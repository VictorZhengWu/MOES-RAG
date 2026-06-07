# -*- coding: utf-8 -*-
"""
Retrieval Engine -- top-level entry point for M3 (consumed by M5 and M8).

WHAT: The RetrievalEngine is the sole public API for the M3 Retrieval
Engine. It wraps the RetrievalPipeline with lazy initialization, health
check delegation, and a clean interface that matches RetrievalEngineProtocol
from contracts/.

The engine is intentionally thin: all retrieval logic lives in pipeline.py.
The engine's only responsibilities are:
  1. Lazy pipeline assembly (dense, sparse, reranker creation).
  2. Delegating retrieve() to the pipeline.
  3. Providing health_check() that verifies M2 backend connectivity.

WHY: M5 (QA Engine) and M8 (API Gateway) consume the retrieval engine
through its Protocol interface. The engine must:
  - Start fast (no model loading on construction). Users and tests
    should be able to import and instantiate the engine without the
    3-5 second BGE-M3 model load penalty.
  - Support health checks (for Kubernetes liveness probes and M8
    monitoring dashboard).
  - Accept custom configuration (different deployment modes need
    different retrieval parameters).

Key design decisions:
  - Lazy pipeline init via _ensure_pipeline(): the pipeline (and its
    model-heavy components) is only created on the first retrieve()
    call. This keeps imports, test discovery, and health-check-only
    usage instant.
  - async health_check(): delegates to StorageManager.health_check(),
    catching exceptions and returning a "degraded" status rather than
    crashing. This matches the resilience pattern used in M2.
  - Config injection: RetrievalConfig can be passed at construction
    time or default-constructed. This supports deploy.yaml overrides.
"""

from __future__ import annotations

from contracts.retrieval import RetrievedContext, RetrievalRequest, ScoredChunk

from m3_retrieval.core.config import RetrievalConfig


class RetrievalEngine:
    """
    Top-level retrieval engine implementing RetrievalEngineProtocol.

    WHAT: Wraps a RetrievalPipeline with lazy initialization.
    Provides retrieve() for query execution and health_check() for
    backend connectivity verification.

    The pipeline is assembled lazily on the first retrieve() call:
      - Embedder (BGE-M3) -- created by the engine.
      - DenseRetriever (ChromaDB via StorageManager).
      - SparseRetriever (Meilisearch via StorageManager).
      - Reranker (BGE-Reranker-v2-m3) -- created by the engine.
      - RetrievalPipeline (orchestrator).

    Configuration is provided via RetrievalConfig, which can be
    customized at construction time or defaulted.

    Usage::

        engine = RetrievalEngine(storage_manager, config)
        result = await engine.retrieve(
            RetrievalRequest(query="DNV hull welding", top_k=20)
        )
        hc = await engine.health_check()
    """

    def __init__(
        self,
        storage_manager,
        config: RetrievalConfig | None = None,
    ) -> None:
        """
        Create a RetrievalEngine without loading any models.

        WHAT: Stores the storage manager reference and config.
        Does NOT create the pipeline or load any embedding/reranker
        models. The pipeline attribute is initialized to None and
        populated by _ensure_pipeline() on first retrieve() call.

        WHY lazy init: model loading (BGE-M3 embedding model ~2GB,
        BGE-Reranker-v2-m3 ~2GB) takes 3-5 seconds each. Loading at
        construction time would penalize every import, test discovery,
        and health check probe. Deferring to first retrieve() means:
          - Health check probes are instant.
          - Tests that don't call retrieve() are fast.
          - Module imports don't trigger heavy model loading.

        Args:
            storage_manager: An M2 StorageManager instance providing
                .vector_store, .doc_index, and .health_check().
            config: RetrievalConfig with pipeline parameters. If None,
                uses sensible defaults from RetrievalConfig().
        """
        # WHAT: M2 StorageManager reference, used to create retrievers
        # and for health_check() delegation.
        # WHY stored: _ensure_pipeline() needs it to construct
        # DenseRetriever and SparseRetriever. health_check() delegates
        # to storage_manager.health_check().
        self._sm = storage_manager

        # WHAT: pipeline configuration with all tunable parameters.
        # WHY stored: passed to RetrievalPipeline and individual stage
        # constructors (DenseRetriever, SparseRetriever, Reranker).
        self.cfg = config or RetrievalConfig()

        # WHAT: the RetrievalPipeline instance (or None if not yet created).
        # Initialized lazily by _ensure_pipeline() on first retrieve() call.
        # WHY None: gate for lazy initialization. The first retrieve() call
        # checks if self._pipeline is None and creates it if so. Subsequent
        # calls use the cached instance.
        self._pipeline = None

    async def _ensure_pipeline(self) -> None:
        """
        Lazily create the retrieval pipeline on first use.

        WHAT: Creates the Embedder, DenseRetriever, SparseRetriever,
        and Reranker, then assembles them into a RetrievalPipeline.
        If the pipeline already exists (subsequent calls), returns
        immediately (no-op).

        This method is called automatically by retrieve() -- external
        code should never need to call it directly.

        WHY: Model loading is expensive (~3-5s per model). We defer
        it to the first actual query rather than paying the cost at
        engine construction time. The Embedder and Reranker both use
        lazy loading internally as well, so the model is only loaded
        when the first encode() or rerank() call happens.

        Implementation detail:
          - Imports are inline (inside the method) to avoid making the
            module import heavyweight. If FlagEmbedding is not installed,
            the import only fails when retrieve() is actually called,
            not when the module is imported.
          - The pipeline is stored as self._pipeline for reuse across
            multiple retrieve() calls within the same engine lifecycle.
        """
        # WHAT: if pipeline already exists, do nothing.
        # WHY: avoids re-creating the pipeline on every retrieve() call.
        # The pipeline is created once and reused.
        if self._pipeline is not None:
            return

        # WHAT: inline imports to keep module-level import lightweight.
        # WHY: FlagEmbedding and heavy ML imports should not load at
        # module import time. They are only needed when retrieve() is
        # actually called.
        from m3_retrieval.core.pipeline import RetrievalPipeline
        from m3_retrieval.embeddings.embedder import Embedder
        from m3_retrieval.stages.dense_retriever import DenseRetriever
        from m3_retrieval.stages.reranker import Reranker
        from m3_retrieval.stages.sparse_retriever import SparseRetriever

        # WHAT: create the Embedder with the configured model name.
        # WHY: the Embedder is shared between the pipeline and any
        # external code that needs to pre-compute embeddings. The model
        # is NOT loaded here -- Embedder uses its own lazy init.
        embedder = Embedder(model_name=self.cfg.embedding_model)

        # WHAT: create the DenseRetriever (ChromaDB-backed vector search).
        # WHY: uses self.cfg.dense_top_k for the number of candidates
        # to retrieve. The DenseRetriever does NOT load the embedder
        # model -- it only holds a reference.
        dense = DenseRetriever(
            self._sm, embedder, top_k=self.cfg.dense_top_k
        )

        # WHAT: create the SparseRetriever (Meilisearch-backed BM25).
        # WHY: uses self.cfg.sparse_top_k for candidate count.
        sparse = SparseRetriever(
            self._sm, top_k=self.cfg.sparse_top_k
        )

        # WHAT: create the Reranker (cross-encoder precision filter).
        # WHY: uses self.cfg.reranker_model for model selection and
        # self.cfg.rerank_top_k for output size. The model is NOT
        # loaded here -- Reranker uses its own lazy init.
        reranker = Reranker(
            model_name=self.cfg.reranker_model,
            top_k=self.cfg.rerank_top_k,
        )

        # WHAT: assemble the pipeline with all three components.
        # WHY: the pipeline orchestrates the stages. All components
        # areNone-safe (the pipeline handles None gracefully).
        self._pipeline = RetrievalPipeline(
            dense_retriever=dense,
            sparse_retriever=sparse,
            reranker=reranker,
            config=self.cfg,
        )

    async def retrieve(
        self, request: RetrievalRequest
    ) -> RetrievedContext:
        """
        Execute a retrieval query through the full pipeline.

        WHAT: Ensures the pipeline is initialized (lazy), then
        delegates to pipeline.retrieve() for the actual retrieval.

        This is the sole method that M5 (QA Engine) and M8 (API
        Gateway) call to get retrieval results. It implements
        RetrievalEngineProtocol.retrieve().

        Args:
            request: A RetrievalRequest with query text and parameters.

        Returns:
            A RetrievedContext containing ranked, deduplicated chunks,
            total count, and search latency.
        """
        # WHAT: lazy pipeline initialization on first call.
        # WHY: defers ~6-10s of model loading to when it's actually
        # needed, keeping engine construction instant.
        await self._ensure_pipeline()

        # WHAT: delegate to the pipeline for all retrieval logic.
        # WHY: the engine is a thin wrapper. All retrieval stages are
        # in pipeline.py for single-responsibility.
        return await self._pipeline.retrieve(request)

    async def retrieve_propositions(
        self, query: str, top_k: int = 20, filters: dict | None = None
    ) -> list[ScoredChunk]:
        """
        Search the propositional index for atomic facts.

        WHAT: Public API method exposed to M5's RetrievalClient. Delegates
        to pipeline.retrieve_propositions() which searches the dedicated
        ChromaDB propositions collection.

        Phase 3: Propositional indexing extracts atomic facts at document
        parse time. This method retrieves them at query time alongside
        regular chunks and knowledge graph data.

        Args:
            query: The user's natural language question.
            top_k: Max number of propositions to return (default 20).
            filters: Optional metadata filters (society, chapter, etc.).

        Returns:
            List of ScoredChunk from the propositions collection.
            Empty list if pipeline or proposition index is unavailable.
        """
        await self._ensure_pipeline()
        return await self._pipeline.retrieve_propositions(query, top_k, filters)

    async def health_check(self) -> dict:
        """
        Verify retrieval engine and backend connectivity.

        WHAT: Delegates to StorageManager.health_check() to verify
        that ChromaDB (vector store) and Meilisearch (document index)
        are reachable and responsive.

        Returns a dict with "status" ("ok" or "degraded") and
        "backends" (detailed per-backend health status from M2).
        On error, returns "degraded" with the error message.

        WHY: health_check() is used by:
          - Kubernetes liveness/readiness probes (M8).
          - M7 Admin Portal monitoring dashboard.
          - Startup verification in personal mode.
        Graceful degradation (returning "degraded" instead of
        raising) allows the system to continue serving partial
        results when one backend is down.

        Returns:
            A dict with keys:
              - "status": "ok" or "degraded"
              - "backends": per-backend health dict (on success), or
              - "error": error message string (on failure).
        """
        try:
            # WHAT: delegate health check to M2 StorageManager.
            # WHY: the engine does not maintain its own backend
            # connections -- it uses M2's through the StorageManager.
            # The StorageManager's health_check already verifies all
            # four backends (vector, doc_index, relational, file_store).
            hc = await self._sm.health_check()
            return {"status": "ok", "backends": hc}
        except Exception as e:
            # WHAT: catch any exception and return degraded status.
            # WHY: health check must never crash. If backends are
            # unreachable, we report "degraded" rather than raising
            # so the monitoring system can continue probing.
            return {"status": "degraded", "error": str(e)}
