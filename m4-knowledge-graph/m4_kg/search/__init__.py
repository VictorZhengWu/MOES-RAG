"""
M4 Knowledge Graph search layer.

WHAT:
- ``graph_search``: search knowledge graph by topic string and expand via BFS traversal.
- ``cross_reference``: hybrid strategy to find equivalent regulation clauses across
  classification societies (graph lookup first, LLM fallback, cache results).

WHY:
- These two functions are the primary query interfaces for the M4 knowledge graph.
  graph_search powers user-facing graph exploration and the M5 QA pipeline's graph
  context. cross_reference enables inter-society regulation mapping, a key feature
  for maritime professionals who need to find equivalent requirements in different
  classification society rulebooks.
- The search layer is separated from the graph layer (kuzu_store, traversal) to
  maintain clean module boundaries: search orchestrates store queries and
  traversal, while the graph layer provides raw CRUD and BFS primitives.
"""

from m4_kg.search.graph_search import graph_search
from m4_kg.search.cross_reference import cross_reference

__all__ = ["graph_search", "cross_reference"]
