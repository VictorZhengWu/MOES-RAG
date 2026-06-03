"""
Hybrid cross-reference: find equivalent regulation clauses across classification societies.

WHAT:
- ``cross_reference()`` maps a clause from one classification society (e.g., DNV)
  to its equivalent in another (e.g., ABS) using a hybrid strategy:
  1. **Graph lookup**: search for existing ``similar_to`` relations between
     entities in the source and target societies. This is the fast path
     (<1 ms via Kuzu indexes).
  2. **LLM fallback**: if no match with confidence > 0.8, call an LLM to
     compute semantic equivalence between clauses.
  3. **Cache**: store LLM results as new ``similar_to`` relations so future
     queries use the fast graph-lookup path.

WHY:
- Maritime professionals frequently need to find equivalent requirements across
  different classification society rulebooks (e.g., "What is the ABS equivalent
  of DNV's welding preheat clause?").
- The hybrid strategy gives us:
  * Speed: cached cross-references are sub-millisecond graph lookups.
  * Coverage: LLM fallback handles new clause pairs on demand.
  * Learning: each LLM call permanently enriches the graph.
- The 0.8 confidence threshold for graph results ensures we only skip the LLM
  when the cached match is highly reliable.
"""

from __future__ import annotations

import uuid

from contracts.knowledge_graph import (
    CrossReferenceResult,
    Entity,
    Relation,
)


async def cross_reference(
    store,
    source_clause: str,
    source_society: str,
    target_society: str,
    llm_backend=None,
) -> CrossReferenceResult | None:
    """
    Find equivalent regulation clause across classification societies.

    WHAT:
    - Hybrid strategy combining graph lookup (fast) and LLM fallback (accurate).
    - First tries to find a cached ``similar_to`` relation in the graph.
    - If no high-confidence match, optionally falls back to LLM and caches
      the result as a new graph edge.

    WHY:
    - Graph lookup is fast and free (no API cost), LLM is slow and costs money.
      By caching LLM results as graph edges, we amortize the LLM cost: each
      clause pair is computed once, then served from the graph forever.
    - The two confidence thresholds serve different purposes:
      * 0.8 for graph results: only high-confidence cached matches skip the LLM.
      * 0.6 for LLM results: moderate-confidence LLM results are still better
        than nothing and get cached for future refinement.

    Args:
        store: KuzuStore instance with an initialized database connection.
        source_clause: Name/substring of the source regulation clause
                       (e.g., "preheat", "Pt.4 Ch.3 §2.1").
        source_society: Classification society code for the source
                        (e.g., "DNV", "ABS", "CCS").
        target_society: Classification society code to cross-reference to
                        (e.g., "ABS", "LR", "BV").
        llm_backend: Optional LLM configuration dict for fallback. If None,
                     the function returns None when graph lookup fails.

    Returns:
        CrossReferenceResult if found, None otherwise.
    """
    # Step 1: Graph lookup (fast path via Kuzu indexes)
    result = await _graph_lookup(
        store, source_clause, source_society, target_society
    )
    if result is not None and result.confidence > 0.8:
        return result

    # Step 2: LLM fallback (only if an LLM backend is provided)
    if llm_backend is not None:
        llm_result = await _llm_cross_reference(
            source_clause, source_society, target_society, llm_backend
        )
        if llm_result is not None and llm_result.confidence > 0.6:
            # Step 3: Cache the LLM result as a graph edge so future
            # queries for this clause pair use the fast path.
            await _cache_cross_reference(store, llm_result)
            return llm_result

    # No match found via either method
    return None


# ---------------------------------------------------------------------------
# Internal: graph lookup
# ---------------------------------------------------------------------------


async def _graph_lookup(
    store,
    source_clause: str,
    source_society: str,
    target_society: str,
) -> CrossReferenceResult | None:
    """
    Search for existing ``similar_to`` or ``equivalent_to`` relations in the graph.

    WHAT:
    - Finds entities in ``source_society`` whose names contain ``source_clause``.
    - Finds all entities in ``target_society``.
    - Checks for ``similar_to`` or ``equivalent_to`` relations from any source
      entity to any target entity.
    - Returns the highest-confidence match as a ``CrossReferenceResult``.

    WHY:
    - This is the fast path of the hybrid strategy: O(log N) index lookups
      against Kuzu, no API calls, sub-millisecond latency.
    - We query by society first (indexed) then filter by name in Python
      because KuzuStore does not expose a combined name+society filter.
      For typical deployments (<100k entities per society), this is fast.

    Args:
        store: KuzuStore instance.
        source_clause: Substring to match against entity names in source_society.
        source_society: Classification society code.
        target_society: Classification society code.

    Returns:
        CrossReferenceResult if a match is found, None otherwise.
    """
    # Find candidate source entities: entities in source_society whose
    # names contain the source_clause substring.
    source_candidates = await store.query_entities_by_society(
        source_society, limit=200
    )
    source_matches = [
        e for e in source_candidates
        if source_clause.lower() in e.name.lower()
    ]
    if not source_matches:
        return None

    # Find candidate target entities: all entities in target_society.
    target_entities = await store.query_entities_by_society(
        target_society, limit=200
    )
    if not target_entities:
        return None

    # Build a set of target entity IDs for O(1) lookup when matching relations.
    target_id_set = {e.entity_id for e in target_entities}

    # Check each source entity's outgoing relations for similar_to /
    # equivalent_to edges pointing to a target-society entity.
    best_match: CrossReferenceResult | None = None

    for source_entity in source_matches:
        relations = await store.query_relations(
            [source_entity.entity_id],
            relation_types=["similar_to", "equivalent_to"],
        )
        for rel in relations:
            if rel.target_entity_id in target_id_set:
                # Found a matching target — build the result
                target_entity = next(
                    (e for e in target_entities
                     if e.entity_id == rel.target_entity_id),
                    None,
                )
                if target_entity is None:
                    continue

                candidate = CrossReferenceResult(
                    source_society=source_society,
                    source_clause=source_entity.name,
                    target_society=target_society,
                    target_clause=target_entity.name,
                    relation_type=(
                        "equivalent"
                        if rel.relation_type == "equivalent_to"
                        else "similar"
                    ),
                    confidence=rel.confidence,
                    notes="Found via graph lookup",
                )

                # Keep track of the highest-confidence match
                if (
                    best_match is None
                    or candidate.confidence > best_match.confidence
                ):
                    best_match = candidate

    return best_match


# ---------------------------------------------------------------------------
# Internal: LLM fallback
# ---------------------------------------------------------------------------


async def _llm_cross_reference(
    source_clause: str,
    source_society: str,
    target_society: str,
    llm_backend,
) -> CrossReferenceResult | None:
    """
    Use LLM to compute cross-society equivalence between clauses.

    WHAT:
    - Calls the configured LLM backend with a prompt asking it to determine
      whether a clause in ``source_society`` has an equivalent in
      ``target_society``, and if so, what that equivalent is.
    - Parses the JSON response to extract the target clause and confidence.

    WHY:
    - LLMs can understand semantic equivalence between differently-worded
      clauses in different rulebooks, which is beyond the capability of
      simple string matching or regex.
    - This function is the fallback path: slow but accurate. Results are
      cached as graph edges so the cost is paid only once per clause pair.

    Args:
        source_clause: Name or text of the source clause.
        source_society: Source classification society code.
        target_society: Target classification society code.
        llm_backend: LLM backend configuration dict with keys:
                     ``provider``, ``model``, ``api_key`` (optional),
                     ``base_url`` (optional).

    Returns:
        CrossReferenceResult if the LLM finds a match, None otherwise.

    Note:
        This is a STUB implementation. The actual LLM call will be
        implemented when M7's LLM backend configuration is available.
        Currently returns None, which forces callers without a mock to
        rely only on graph lookup.
    """
    # TODO: Implement actual LLM call when M7 LLM backend is available.
    # The implementation will:
    # 1. Build a prompt with source_clause, source_society, target_society.
    # 2. Call the LLM API (OpenAI / DeepSeek / Ollama compatible).
    # 3. Parse the JSON response for target_clause, confidence, relation_type.
    # 4. Return a CrossReferenceResult or None if the LLM is uncertain.
    #
    # For now, return None so the function is safe to call but does not
    # produce LLM results. Tests mock this function to simulate LLM behavior.
    _ = source_clause, source_society, target_society, llm_backend
    return None


# ---------------------------------------------------------------------------
# Internal: cache LLM result as graph edge
# ---------------------------------------------------------------------------


async def _cache_cross_reference(
    store,
    result: CrossReferenceResult,
) -> None:
    """
    Store a cross-reference result as a ``similar_to`` relation in the graph.

    WHAT:
    - Finds the source entity (by name match in source_society) and target
      entity (by name match in target_society) that correspond to the
      cross-reference result.
    - Creates a ``similar_to`` relation between them with the LLM confidence
      score, storing the cross-reference metadata in relation properties.

    WHY:
    - Caching is the key to the hybrid strategy's efficiency: each LLM
      result is stored as a graph edge so future queries for the same
      clause pair are sub-millisecond graph lookups instead of costly
      LLM API calls.
    - The relation properties store the original LLM metadata (notes,
      original relation_type) for auditability.

    Args:
        store: KuzuStore instance.
        result: CrossReferenceResult from the LLM fallback to cache.
    """
    # Find source entity: name match in source_society
    source_candidates = await store.query_entities_by_society(
        result.source_society, limit=200
    )
    source_entity = next(
        (e for e in source_candidates
         if result.source_clause.lower() in e.name.lower()),
        None,
    )
    if source_entity is None:
        # Source entity not found in graph — cannot cache
        return

    # Find target entity: name match in target_society
    target_candidates = await store.query_entities_by_society(
        result.target_society, limit=200
    )
    target_entity = next(
        (e for e in target_candidates
         if result.target_clause.lower() in e.name.lower()),
        None,
    )
    if target_entity is None:
        # Target entity not found in graph — cannot cache
        return

    # Create a similar_to relation from source to target with the LLM
    # confidence and metadata stored in relation properties.
    relation = Relation(
        relation_id=str(uuid.uuid4()),
        source_entity_id=source_entity.entity_id,
        target_entity_id=target_entity.entity_id,
        relation_type="similar_to",
        properties={
            "original_relation_type": result.relation_type,
            "source_society": result.source_society,
            "target_society": result.target_society,
            "llm_notes": result.notes,
        },
        confidence=result.confidence,
    )

    await store.insert_relations([relation])
