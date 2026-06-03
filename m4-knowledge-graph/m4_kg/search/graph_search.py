"""
Knowledge graph search by topic string with BFS expansion.

WHAT:
- ``graph_search()`` takes a topic string, finds matching seed entities in the
  knowledge graph via name-based search, then expands outward via BFS traversal
  to collect a connected subgraph.

WHY:
- This is the primary M4 query interface that powers:
  * User-facing graph exploration — "show me everything about EH36 steel".
  * M5 QA pipeline's graph context — provides structured entity-relation
    context alongside M3's semantic document retrieval.
- By combining name search with BFS expansion, callers get not just the
  entities that directly match the topic, but also their immediate neighbors
  (related regulations, steel grades, equipment, etc.).
"""

from __future__ import annotations

from contracts.knowledge_graph import Subgraph
from m4_kg.graph.traversal import bfs_traverse


async def graph_search(
    store,
    topic: str,
    depth: int = 1,
    max_entities: int = 20,
) -> Subgraph:
    """
    Search knowledge graph by topic and expand via BFS traversal.

    WHAT:
    - Finds entities whose names contain the ``topic`` string (CONTAINS
      search via KuzuStore.query_entities_by_name).
    - Uses those seed entities as starting points for a BFS traversal that
      expands outward up to ``depth`` hops.
    - Returns a ``Subgraph`` containing all visited entities and traversed
      relations.

    WHY:
    - Two-phase search (name lookup + BFS) balances precision (only entities
      relevant to the topic) with recall (their connected neighbors are
      included for context).
    - User tiers control depth: Basic users get depth=1 (direct neighbors
      only), Pro users get depth=3, Enterprise users get depth=5.

    Steps:
        1. ``store.query_entities_by_name(topic, limit=max_entities)``
           → find seed entities.
        2. If no seeds, return an empty Subgraph with descriptive
           ``query_context``.
        3. ``bfs_traverse(store, seed_ids, depth, max_entities)``
           → expand from seeds to collect the connected subgraph.

    Args:
        store: KuzuStore instance with an initialized database connection.
        topic: Substring to search for within entity names (CONTAINS match).
        depth: Maximum number of BFS hops from seed entities
               (1 = direct neighbors only). Defaults to 1.
        max_entities: Hard cap on total entities in the returned Subgraph
                      (applied by bfs_traverse). Defaults to 20.

    Returns:
        Subgraph containing:
        - ``entities``: list of Entity instances (may be empty if no match).
        - ``relations``: list of Relation instances connecting the entities.
        - ``query_context``: string describing the search (set to
          ``"topic=<topic>"`` on success, or a "No entities found" message
          on no-match).
    """
    # ----------------------------------------------------------------
    # Phase 1: Find seed entities matching the topic string
    # ----------------------------------------------------------------
    seeds = await store.query_entities_by_name(topic, limit=max_entities)

    # If no entities match the topic, return an empty Subgraph with
    # a descriptive query_context so callers can inform the user.
    if not seeds:
        return Subgraph(
            entities=[],
            relations=[],
            query_context=f"No entities found for: {topic}",
        )

    # ----------------------------------------------------------------
    # Phase 2: BFS traversal from seed entities
    # ----------------------------------------------------------------
    seed_ids = [e.entity_id for e in seeds]
    result = await bfs_traverse(
        store,
        seed_entity_ids=seed_ids,
        depth=depth,
        max_entities=max_entities,
    )

    # Set query_context on the Subgraph returned by bfs_traverse.
    # bfs_traverse returns an empty query_context string by default.
    # We overwrite it with our topic information so downstream consumers
    # (M5 QA pipeline, web UI) can display the search context.
    # Subgraph is a mutable dataclass, so this assignment is valid.
    result.query_context = f"topic={topic}"

    return result
