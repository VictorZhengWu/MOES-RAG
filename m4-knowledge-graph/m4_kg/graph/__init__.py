"""
M4 Knowledge Graph — Graph storage subpackage.

WHAT:
- Provides graph database persistence via Kuzu embedded graph database.
- Exports KuzuStore, the primary interface for entity/relation CRUD
  operations and schema management.

WHY:
- The graph/ subpackage isolates all graph database concerns from the
  extraction and search layers of M4, maintaining clean separation of
  concerns within the knowledge graph engine.
"""

from __future__ import annotations

from m4_kg.graph.kuzu_store import KuzuStore

__all__ = ["KuzuStore"]
