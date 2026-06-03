"""
M4: Knowledge Graph Engine
Marine & Offshore Expert System

WHAT:
  This package provides entity/relation extraction, graph storage,
  graph traversal, and cross-reference search for maritime and offshore
  engineering knowledge.

WHY:
  The knowledge graph enriches RAG retrieval with structured entity
  relationships (regulation cross-references, steel-grade constraints,
  equipment specifications) that semantic search alone cannot capture.

Public API:
  - KGEngine: Main orchestrator implementing KGEngineProtocol.
  - ExtractionConfig: Configuration for LLM backend and batch settings.
  - UserTier, USER_TIERS: Tier-based access control (basic/pro/enterprise).
"""

from m4_kg.core.config import ExtractionConfig
from m4_kg.core.engine import KGEngine
from m4_kg.core.tier import USER_TIERS, UserTier

__all__ = ["KGEngine", "ExtractionConfig", "UserTier", "USER_TIERS"]
