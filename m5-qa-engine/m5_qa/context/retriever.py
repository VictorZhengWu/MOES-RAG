"""
M5 QA Engine — Retrieval Client.

WHAT: Coordinates M3 semantic retrieval and M4 knowledge graph search
      into a unified RetrievalContext for the RAG pipeline. Supports
      two modes: simple (M3-only) and parallel (M3+M4 via asyncio.gather).

WHY: M5 pipelines need different retrieval strategies depending on the
     user tier and pipeline mode:
     - simple mode (Basic tier): M3 semantic search only, fast and cheap
     - parallel mode (Pro/Enterprise): M3 + M4 together for richer context
     The RetrievalClient encapsulates the coordination logic so pipeline
     code doesn't need to manage M3/M4 lifecycle directly.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

from contracts.knowledge_graph import CrossReferenceResult, Subgraph
from contracts.retrieval import RetrievedContext, RetrievalRequest, ScoredChunk


@dataclass
class RetrievalContext:
    """
    WHAT: Merged context from M3 retrieval and M4 knowledge graph search.

    WHY: The RAG pipeline needs a single unified data structure to pass
         retrieved chunks and graph data to the fusion formatter. Using
         a dataclass ensures type safety.

    Attributes:
        chunks: Ranked semantic search results from M3 retrieval engine.
        graph: Knowledge graph subgraph from M4 engine (None if not used).
        cross_refs: Cross-classification-society references from M4.
    """
    chunks: list[ScoredChunk]
    graph: Subgraph | None = None
    propositions: list[ScoredChunk] = field(default_factory=list)
    """Atomic facts from propositional index (new in Phase 3)."""
    errors: list[str] = field(default_factory=list)
    """Non-fatal errors encountered during retrieval (e.g., M4 unavailable)."""
    cross_refs: list[CrossReferenceResult] = field(default_factory=list)


class RetrievalClient:
    """
    WHAT: Client that coordinates M3 retrieval and M4 graph search.

    WHY: The M5 pipelines (simple, pipeline, self_rag) need to call M3 and M4
         in different combinations. This class provides:
         - simple_retrieve(): M3-only, used by the simple pipeline
         - parallel_retrieve(): M3+M4 in parallel, used by pipeline and self_rag
         Both engines are optional — the client degrades gracefully if either
         is unavailable.

    Attributes:
        _m3: The M3 retrieval engine (RetrievalEngineProtocol). May be None.
        _m4: The M4 knowledge graph engine (KGEngineProtocol). May be None.
    """

    def __init__(self, m3_engine=None, m4_engine=None):
        """
        WHAT: Initialize the retrieval client with optional engine references.

        WHY: Engines are optional to support graceful degradation:
             - M3 may be unavailable during early development
             - M4 may be optional for Basic tier users
             Accepting None for either allows the caller to decide what's needed.

        Args:
            m3_engine: An object implementing RetrievalEngineProtocol (or compatible).
            m4_engine: An object implementing KGEngineProtocol (or compatible).
        """
        self._m3 = m3_engine
        self._m4 = m4_engine

    async def simple_retrieve(self, query: str, top_k: int = 10) -> RetrievalContext:
        """
        WHAT: Perform M3-only semantic retrieval (simple pipeline mode).

        WHY: The simple pipeline is designed for Basic-tier users with limited
             context windows (4K tokens). M4 graph traversal adds token overhead
             and latency — simple mode skips it entirely.

        Args:
            query: The user's natural language question.
            top_k: Maximum number of chunks to retrieve (default 10).

        Returns:
            A RetrievalContext with M3 chunks and graph=None.
            Returns empty context if M3 is unavailable.
        """
        if self._m3 is None:
            return RetrievalContext(chunks=[], graph=None)

        try:
            result: RetrievedContext = await self._m3.retrieve(
                RetrievalRequest(query=query, top_k=top_k)
            )
            return RetrievalContext(chunks=result.chunks, graph=None)
        except Exception as exc:
            logger.error("M3 retrieval failed: %s. Returning empty context.", exc)
            return RetrievalContext(chunks=[], graph=None, errors=[f"M3 retrieval failed: {exc}"])

    async def parallel_retrieve(
        self, query: str, top_k: int = 20, kg_depth: int = 1
    ) -> RetrievalContext:
        """
        WHAT: Retrieve from M3 and M4 in parallel via asyncio.gather.

        WHY: M3 semantic search and M4 graph traversal are independent
             operations — they don't depend on each other's results.
             Running them in parallel reduces total latency from
             (M3_time + M4_time) to max(M3_time, M4_time).

        Args:
            query: The user's natural language question.
            top_k: Maximum number of M3 chunks to retrieve (default 20).
            kg_depth: Depth for M4 graph BFS traversal (default 1).

        Returns:
            A RetrievalContext with M3 chunks and optionally M4 graph data.
            If M4 fails or is unavailable, graph is None but chunks are returned.
        """
        # Create async tasks for each engine — run independently
        m3_task = None
        m4_task = None

        if self._m3:
            m3_task = asyncio.create_task(
                self._m3.retrieve(RetrievalRequest(query=query, top_k=top_k))
            )

        if self._m4:
            m4_task = asyncio.create_task(
                self._m4.graph_search(topic=query, depth=kg_depth)
            )

        # Collect results — each engine failure is isolated
        chunks: list[ScoredChunk] = []
        graph: Subgraph | None = None

        errors: list[str] = []
        if m3_task:
            try:
                result: RetrievedContext = await m3_task
                chunks = result.chunks
            except Exception as exc:
                logger.error("M3 retrieval failed: %s", exc)
                errors.append(f"M3: {exc}")

        if m4_task:
            try:
                graph = await m4_task
            except Exception as exc:
                logger.error("M4 graph search failed: %s", exc)
                errors.append(f"M4: {exc}")

        return RetrievalContext(chunks=chunks, graph=graph, errors=errors)
