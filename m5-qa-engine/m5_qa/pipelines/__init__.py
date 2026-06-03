"""
M5 QA Engine — RAG Pipelines.

WHAT: Provides three RAG pipeline modes:
      - simple:    M3 retrieval -> LLM generation (Basic tier, 4K context)
      - pipeline:  M3+M4 parallel -> fusion + citations -> LLM (Pro tier, 8K context)
      - self_rag:  Iterative retrieval with quality checks (Enterprise tier, 16K context)

WHY: Different user tiers require different retrieval strategies. Rather than
     one monolithic pipeline with conditional branches, each mode is a separate
     module — this makes each pipeline easy to understand, test, and evolve
     independently.
"""

from m5_qa.pipelines.simple import execute_simple
from m5_qa.pipelines.pipeline import execute_pipeline
from m5_qa.pipelines.self_rag import execute_self_rag

__all__ = [
    "execute_simple",
    "execute_pipeline",
    "execute_self_rag",
]
