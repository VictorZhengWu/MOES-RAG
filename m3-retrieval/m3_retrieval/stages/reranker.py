# -*- coding: utf-8 -*-
"""
Cross-Encoder Reranker stage for the M3 Retrieval Pipeline.

WHAT: The Reranker class uses a cross-encoder model (BGE-Reranker-v2-m3
by default) to compute precise relevance scores for each query-chunk pair.
Unlike bi-encoders (which embed query and document independently), a
cross-encoder processes the query and document text together through a
transformer, capturing fine-grained semantic interactions. This achieves
higher precision at the cost of higher latency -- it is applied only to
the top-N fused candidates, not the full index.

WHY: Dense retrieval (cosine similarity over BGE-M3 embeddings) and BM25
both produce approximate rankings. The cross-encoder provides a second-pass
reranking that corrects errors from the first-pass retrievers. This is a
standard two-stage retrieval architecture: fast approximate search followed
by slow precise reranking of the top candidates.

Key design decisions:
  - Lazy model loading: the model is loaded only on the first call to
    rerank(), not at construction time. This keeps pipeline assembly fast
    (no 3-5 second model load on import).
  - Sync rerank_sync() + async rerank(): the core logic is synchronous
    because FlagEmbedding's predict() is synchronous. The async wrapper
    uses loop.run_in_executor() to avoid blocking the event loop.
  - Source annotation: reranked results have source=f"reranked({orig})"
    to preserve the provenance chain (e.g. "reranked(fusion)" shows the
    chunk came from fusion before being reranked).
"""

from __future__ import annotations

import asyncio
from typing import Any

from contracts.retrieval import ScoredChunk


class Reranker:
    """
    Cross-encoder reranker for second-pass relevance scoring.

    WHAT: Takes a query and a list of ScoredChunk candidates, computes
    cross-encoder relevance scores for each pair, and returns the top_k
    candidates sorted by the new scores.

    Uses BGE-Reranker-v2-m3 by default. The model is loaded lazily on
    the first call to rerank() or rerank_sync().

    Usage::

        reranker = Reranker(model_name="BAAI/bge-reranker-v2-m3", top_k=20)
        # Async (preferred, does not block event loop):
        refined = await reranker.rerank(query, fused_chunks)
        # Sync (for testing or non-async contexts):
        refined = reranker.rerank_sync(query, fused_chunks)
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        top_k: int = 20,
    ) -> None:
        """
        Initialize the Reranker without loading the model.

        WHAT: Stores the model_name and top_k configuration. The model
        is NOT loaded here -- it loads on first use.

        WHY: Pipeline assembly creates all stages sequentially. If each
        stage loaded its model at construction time, total import + init
        time would be 10+ seconds. Lazy loading spreads this cost to
        when the model is actually needed.

        Args:
            model_name: HuggingFace model ID for the cross-encoder.
                Default: "BAAI/bge-reranker-v2-m3".
            top_k: Maximum number of results to return after reranking.
                Default 20 (narrower than fusion's 50, since reranker
                is a precision filter).
        """
        # WHAT: HuggingFace model identifier.
        # WHY stored: passed to FlagEmbedding's FlagModel or
        # FlagReranker when _load() is called. Kept as instance state
        # so different Reranker instances can use different models.
        self.model_name: str = model_name

        # WHAT: Maximum results to return.
        # WHY stored: controls output size. Smaller than fusion's top_k
        # because the reranker is a precision filter that narrows down
        # to the most relevant results for the LLM context window.
        self.top_k: int = top_k

        # WHAT: the loaded FlagEmbedding reranker model instance.
        # Starts as None; set by _load() on first use.
        # WHY lazy: loading a ~2GB transformer model is expensive.
        # We defer it until the first rerank() call so that pipeline
        # assembly and imports are fast.
        self._model: Any = None

    def _load(self) -> Any:
        """
        Load the cross-encoder model (lazy init).

        WHAT: Imports FlagEmbedding's FlagReranker and instantiates it
        with the configured model_name. Returns the model object.

        WHY separate method: called only on first rerank(), not at
        construction time. This keeps imports fast.

        Returns:
            The FlagReranker model instance.
        """
        # WHAT: import FlagReranker inside the method body.
        # WHY: FlagEmbedding is a heavy dependency (~2GB model download).
        # Importing at module level would slow down every import of this
        # module, even if the Reranker is never used. Lazy import keeps
        # the module lightweight.
        from FlagEmbedding import FlagReranker

        # WHAT: create the reranker model instance.
        # WHY use_flag_embedding=False: use raw model output instead of
        # creating FlagEmbedding objects. This gives simpler, more
        # predictable output that we can convert to float scores directly.
        # use_fp16=True: half-precision reduces VRAM usage from ~2GB to
        # ~1GB with negligible accuracy loss for reranking.
        self._model = FlagReranker(
            self.model_name,
            use_fp16=True,
        )
        return self._model

    def rerank_sync(
        self,
        query: str,
        chunks: list[ScoredChunk],
    ) -> list[ScoredChunk]:
        """
        Synchronous rerank: compute cross-encoder scores and reorder.

        WHAT: For each chunk, pairs it with the query and passes the
        pair through the cross-encoder. The model outputs a relevance
        score. Chunks are then sorted by descending score and the top_k
        are returned with source annotated as "reranked({original_source})".

        Short-circuits to [] on empty input without loading the model.

        Args:
            query: The user's query text.
            chunks: List of ScoredChunk candidates to rerank. Typically
                the output of rrf_fusion(). Must be non-empty for
                meaningful results.

        Returns:
            List of ScoredChunk objects sorted by cross-encoder relevance
            score (descending), limited to top_k. Empty list if input
            is empty.
        """
        # WHAT: short-circuit on empty input.
        # WHY: if there are no chunks to rerank, we must not load the
        # model (expensive, wasteful for a no-op). Return immediately.
        if not chunks:
            return []

        # WHAT: lazy-load the model on first use.
        # WHY: deferring the 3-5 second model load to when it is
        # actually needed keeps pipeline assembly fast.
        if self._model is None:
            self._load()

        # WHAT: build query-chunk pairs for the cross-encoder.
        # WHY: the cross-encoder takes a list of (query, document) pairs
        # and scores each pair's relevance. Unlike bi-encoders, the
        # query and document are concatenated and processed together.
        pairs: list[list[str]] = [
            [query, sc.chunk.text] for sc in chunks
        ]

        # WHAT: run the cross-encoder model to get relevance scores.
        # WHY FlagReranker.compute_score(): returns a list of float
        # scores, one per pair, indicating relevance.
        # normalize=True: applies sigmoid to get scores in [0, 1] range,
        # which makes scores more interpretable and comparable.
        scores: list[float] = self._model.compute_score(
            pairs,
            normalize=True,
        )

        # WHAT: handle single-score return (FlagReranker returns a scalar
        # float, not a list, when given a single pair).
        # WHY: FlagReranker.compute_score() has inconsistent return types:
        # list[float] for multiple pairs, float for single pair.
        if not isinstance(scores, list):
            # Single pair case -- wrap in a list for uniform handling.
            scores = [float(scores)]

        # Ensure all scores are Python float (some backends return numpy floats)
        scores = [float(s) for s in scores]

        # WHAT: pair each chunk with its new cross-encoder score, then
        # sort by descending score.
        # WHY: the cross-encoder score is more accurate than the original
        # retrieval score (cosine similarity or BM25). Sorting by cross-
        # encoder score produces the final relevance ordering.
        ranked: list[tuple[ScoredChunk, float]] = sorted(
            zip(chunks, scores),
            key=lambda item: item[1],
            reverse=True,
        )

        # WHAT: build the output ScoredChunk list with updated scores
        # and reranked source annotation.
        # WHY: the source annotation "reranked({original_source})" preserves
        # the provenance chain. This is useful for debugging and for the
        # citation system to show where the score came from.
        result: list[ScoredChunk] = []
        for sc, new_score in ranked[:self.top_k]:
            result.append(ScoredChunk(
                chunk=sc.chunk,
                score=new_score,
                source=f"reranked({sc.source})",
                citation=sc.citation,
            ))

        return result

    async def rerank(
        self,
        query: str,
        chunks: list[ScoredChunk],
    ) -> list[ScoredChunk]:
        """
        Asynchronous rerank: runs the synchronous rerank in a thread pool.

        WHAT: Wraps rerank_sync() with asyncio's run_in_executor() so
        the blocking FlagEmbedding model inference does not block the
        event loop. This is critical for web server deployments where
        the event loop must remain responsive for other requests.

        WHY async wrapper: FlagReranker.compute_score() is a synchronous
        CPU-bound operation. Calling it directly in an async context
        blocks the event loop, preventing other coroutines (like other
        HTTP requests) from making progress. run_in_executor() moves
        the blocking work to a thread pool, keeping the event loop free.

        Args:
            query: The user's query text.
            chunks: List of ScoredChunk candidates to rerank.

        Returns:
            List of ScoredChunk objects sorted by cross-encoder relevance
            score (descending), limited to top_k.
        """
        # WHAT: get the current running event loop.
        # WHY: asyncio.get_event_loop() is deprecated in Python 3.10+
        # but still needed for backward compatibility. The loop is used
        # to schedule the blocking rerank_sync() in a thread pool.
        loop = asyncio.get_event_loop()

        # WHAT: run rerank_sync() in the default thread pool executor.
        # WHY: this prevents the CPU-bound model.predict() call from
        # blocking the event loop. The thread pool runs the synchronous
        # code in a background thread while the event loop remains free.
        result = await loop.run_in_executor(
            None,  # Use the default ThreadPoolExecutor
            self.rerank_sync,
            query,
            chunks,
        )
        return result
