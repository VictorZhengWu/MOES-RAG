"""
Retrieval engine protocols (M3).

Defines the retrieval pipeline interface consumed by M5 (QA Engine).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .document import Chunk


@dataclass
class RetrievedContext:
    """Output of the retrieval pipeline."""
    chunks: list[ScoredChunk]
    total_found: int
    search_latency_ms: float
    query_rewrites: list[str] = field(default_factory=list)


@dataclass
class ScoredChunk:
    """A single retrieved chunk with confidence and source."""
    chunk: Chunk
    score: float
    source: str  # "dense" | "sparse" | "bm25" | "knowledge_graph"
    citation: str  # Human-readable citation string


@dataclass
class RetrievalRequest:
    """Input to the retrieval engine."""
    query: str
    top_k: int = 20
    filters: dict[str, Any] | None = None
    enable_query_rewriting: bool = True
    enable_hyde: bool = True
    fusion_strategy: str = "rrf"  # "rrf" | "weighted" | "hybrid"


@runtime_checkable
class RetrievalEngineProtocol(Protocol):
    """Interface for the retrieval engine."""

    async def retrieve(self, request: RetrievalRequest) -> RetrievedContext:
        """Execute the full retrieval pipeline."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Verify retrieval engine status and backend connectivity."""
        ...
