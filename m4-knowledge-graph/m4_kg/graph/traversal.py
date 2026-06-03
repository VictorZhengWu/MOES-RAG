"""
BFS graph traversal for the Marine & Offshore knowledge graph.

WHAT:
- ``bfs_traverse()`` performs breadth-first search starting from seed entity
  IDs, expanding outward through outgoing relations up to a configurable depth
  limit. Results are returned as a ``Subgraph`` containing all visited entities
  and traversed relations.

WHY:
- Graph traversal is the core exploration primitive that powers:
  * ``graph_search()`` — locate seed entities by name, then expand to find
    all related entities and their connections.
  * User-tier-limited queries — Basic (depth=1), Pro (depth=3),
    Enterprise (depth=5) tiers control how deep the graph can be explored.
  * Cross-reference lookups — find indirect relationships between entities
    across different classification societies.
- BFS (rather than DFS) is chosen because it naturally respects depth-based
  user tier limits and finds the closest neighbors first, which are typically
  the most relevant for maritime regulation queries.
"""

from __future__ import annotations

from contracts.knowledge_graph import Entity, Relation, Subgraph


async def bfs_traverse(
    store,
    seed_entity_ids: list[str],
    depth: int = 1,
    relation_types: list[str] | None = None,
    max_entities: int = 50,
) -> Subgraph:
    """
    BFS graph traversal from seed entities.

    WHAT:
    - Starts from each seed entity, traverses outgoing relations up to
      ``depth`` hops, collecting all encountered entities and relations.
    - Returns a ``Subgraph`` with deduplicated entities and relations.

    WHY:
    - Core graph exploration primitive that powers ``graph_search()`` and
      user-tier-limited queries. BFS ensures closest neighbors are
      discovered first, which is the expected behavior for knowledge
      graph exploration.

    Traversal rules:
    - Only outgoing edges are followed (source -> target direction).
    - Each entity and relation is included at most once (deduplication).
    - Traversal stops early if ``max_entities`` is reached.
    - ``relation_types`` acts as an edge filter — only relations of the
      specified types are traversed.

    Args:
        store: KuzuStore instance with an initialized database connection.
        seed_entity_ids: Starting entity IDs for the traversal.
        depth: Maximum number of hops from seed entities
               (1 = direct neighbors only). Defaults to 1.
        relation_types: Optional filter on relation types to traverse
                        (e.g., ["requires", "constrains"]). If None,
                        all relation types are followed. Defaults to None.
        max_entities: Hard cap on the total number of entities in the
                      returned Subgraph. Defaults to 50.

    Returns:
        Subgraph containing:
        - ``entities``: list of all visited Entity instances.
        - ``relations``: list of all traversed Relation instances.
        - ``query_context``: empty string (reserved for future use by
          downstream consumers like M5's combined search).
    """
    # ----------------------------------------------------------------
    # Initialize tracking structures
    # ----------------------------------------------------------------
    # visited_entities tracks all entity IDs we have already collected
    # or enqueued, preventing duplicate fetches and infinite loops.
    visited_entities: set[str] = set(seed_entity_ids)
    # visited_relations tracks relation IDs already added to the result,
    # preventing the same edge from being included twice.
    visited_relations: set[str] = set()
    # frontier holds the entity IDs to expand from in the current hop.
    frontier: set[str] = set(seed_entity_ids)
    # all_entities maps entity_id -> Entity for deduplication and O(1)
    # lookup when building the final result.
    all_entities: dict[str, Entity] = {}
    all_relations: list[Relation] = []

    # ----------------------------------------------------------------
    # Fetch seed entities
    # ----------------------------------------------------------------
    if seed_entity_ids:
        seed_entities = await store.query_entities_by_ids(seed_entity_ids)
        for entity in seed_entities:
            all_entities[entity.entity_id] = entity

    # ----------------------------------------------------------------
    # BFS expansion loop
    # ----------------------------------------------------------------
    for _hop in range(depth):
        if not frontier:
            # No more entities to expand from — traversal exhausted
            break

        # Get all outgoing relations from the current frontier entities.
        # query_relations already supports relation_types filtering,
        # which we pass through directly.
        relations = await store.query_relations(
            list(frontier), relation_types
        )

        # Collect entity IDs of newly discovered target entities
        new_entity_ids: set[str] = set()

        for rel in relations:
            # Deduplicate relations by relation_id
            if rel.relation_id not in visited_relations:
                visited_relations.add(rel.relation_id)
                all_relations.append(rel)

            # Discover new target entities
            if rel.target_entity_id not in visited_entities:
                visited_entities.add(rel.target_entity_id)
                new_entity_ids.add(rel.target_entity_id)

        # Fetch the newly discovered target entities in a single batch
        if new_entity_ids:
            target_entities = await store.query_entities_by_ids(
                list(new_entity_ids)
            )
            for entity in target_entities:
                all_entities[entity.entity_id] = entity

        # Prepare frontier for the next hop: only entities discovered
        # in this hop (not previously known) become the new frontier.
        frontier = new_entity_ids

        # Apply entity count cap after each hop. This checks the total
        # count rather than per-hop count to enforce the global limit.
        if len(all_entities) >= max_entities:
            break

    # ----------------------------------------------------------------
    # Build and return the result Subgraph
    # ----------------------------------------------------------------
    return Subgraph(
        entities=list(all_entities.values()),
        relations=all_relations,
        query_context="",
    )
