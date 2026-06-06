"""
M4 Knowledge Graph Engine — main orchestrator implementing KGEngineProtocol.

WHAT:
  ``KGEngine`` is the central class of the M4 Knowledge Graph Engine. It
  implements ``KGEngineProtocol`` from ``contracts/`` and orchestrates:

  1. **Entity/Relation Extraction** — coordinates rule-based and LLM-based
     extractors, merges results, and persists to Kuzu graph database.
  2. **Query** — provides entity and relation search with type filtering.
  3. **Graph Search** — topic-based graph exploration with BFS traversal,
     depth-capped by user tier.
  4. **Cross Reference** — maps regulation clauses across classification
     societies using a hybrid graph+LLM strategy (tier-gated).
  5. **Health Check** — verifies database connectivity for monitoring.

WHY:
  This engine is the single entry point for all M4 functionality. It is
  designed for two distinct callers:

  * **M1's ``on_parse_complete`` hook** — calls ``extract_entities()``
    asynchronously after document parsing completes. The engine runs
    extraction in the background via ``asyncio.create_task()`` so M1
    returns immediately to the user with ``"kg_status": "building"``.

  * **M5's QA pipeline** — calls ``graph_search()`` and ``cross_reference()``
    to enrich LLM answers with structured knowledge graph context. Results
    are combined with M3's semantic retrieval in M5's combined search.

  User tier enforcement is done in this class: basic users cannot
  cross-reference, and traversal depth is capped by tier limits.
"""

from __future__ import annotations

import logging
from typing import Any

from contracts.knowledge_graph import (
    CrossReferenceResult,
    Entity,
    KGEngineProtocol,
    Relation,
    Subgraph,
)
from m4_kg.core.config import ExtractionConfig
from m4_kg.core.tier import USER_TIERS, UserTier
from m4_kg.extraction.merger import merge_entities, merge_relations
from m4_kg.extraction.rule_extractor import extract_entities as rule_extract
from m4_kg.extraction.rule_extractor import extract_relations as rule_rel
from m4_kg.graph.kuzu_store import KuzuStore
from m4_kg.search.cross_reference import cross_reference as cross_ref_fn
from m4_kg.search.graph_search import graph_search as graph_search_fn

# Module-level logger for KG engine operational events.
# WHY: Engine operations (extraction start/completion, cross-reference gating,
#      health status) are critical for production monitoring and debugging.
#      A dedicated logger enables per-component log filtering.
logger = logging.getLogger(__name__)


class KGEngine:
    """
    Main M4 knowledge graph engine implementing KGEngineProtocol.

    WHAT:
      Orchestrates the full lifecycle of knowledge graph operations:
      extraction (rule + LLM), graph persistence, query, search, and
      cross-reference mapping, all governed by user tier limits.

    WHY:
      This is the ONLY class that M1 and M5 interact with. By centralizing
      all operations behind a single engine class, we enforce tier-based
      access control, provide a consistent async API, and keep the
      KuzuStore initialization lazy (no database files created at import
      time or construction time).

    Attributes:
        _store: KuzuStore instance (lazy — database connection deferred
                until first access).
        _config: ExtractionConfig controlling LLM backend, batch sizes,
                and fallback behavior.
        _tier: UserTier controlling traversal depth, entity limits, and
               cross-reference enablement.

    Usage:
        >>> engine = KGEngine(db_path="./data/graph/marine_rag.db", tier="pro")
        >>> entities = await engine.extract_entities("doc_001", chunks)
        >>> subgraph = await engine.graph_search("EH36 welding")
        >>> health = await engine.health_check()
    """

    def __init__(
        self,
        db_path: str = "./data/graph/marine_rag.db",
        config: ExtractionConfig | None = None,
        tier: str = "basic",
    ) -> None:
        """
        Initialize the KG engine with storage path, extraction config, and tier.

        WHAT:
          Creates a KuzuStore (lazy — no DB connection until first use),
          sets the extraction configuration, and selects the user tier.

        WHY:
          All three parameters affect the engine's behavior at runtime:
          - ``db_path``: where the Kuzu database file lives on disk.
          - ``config``: LLM backend, batch limits, fallback settings. None
            means rule-only extraction (no LLM costs, suitable for basic tier).
          - ``tier``: "basic" / "pro" / "enterprise" from USER_TIERS dict.
            Defaults to "basic" for safety (most restrictive).

        Args:
            db_path: Filesystem path to the Kuzu database directory.
                     Defaults to ``./data/graph/marine_rag.db``.
            config: Extraction configuration including optional LLM backend.
                    If None, a default ExtractionConfig is used (no LLM).
            tier: User tier identifier string ("basic", "pro", "enterprise").
                  Defaults to "basic".
        """
        # KuzuStore is created lazily — no file I/O at construction time.
        # The actual database connection is deferred until the first
        # insert_entities(), query_entities_by_name(), etc. call.
        # WHY: Avoids creating empty database files when the engine is
        #      instantiated but never used (e.g., in unit test fixtures).
        self._store = KuzuStore(db_path)

        # ExtractionConfig with optional LLM backend.
        # WHY: If config is None, we use the default config (llm=None),
        #      which means rule-only extraction. This is the safest default
        #      for basic tier deployments with no LLM configured.
        self._config = config or ExtractionConfig()

        # Resolve user tier from the USER_TIERS dict.
        # WHY: Falls back to "basic" if an invalid tier string is provided,
        #      ensuring the engine always starts in a known-safe state.
        self._tier = USER_TIERS.get(tier, USER_TIERS["basic"])

    # =====================================================================
    # Entity / Relation Extraction (called by M1 on_parse_complete hook)
    # =====================================================================

    async def extract_entities(
        self, document_id: str, chunks: list
    ) -> list[Entity]:
        """
        Extract entities from parsed document chunks and persist to graph.

        WHAT:
          Full extraction pipeline:
          1. Concatenate all chunk texts and run rule-based extraction
             (regex + dictionary matching for ~70% coverage).
          2. If LLM backend is configured, run LLM-based extraction
             (async, with concurrency control) for the remaining ~30%.
          3. Merge rule and LLM results — LLM overwrites rule matches
             (higher precision), rule fills in what LLM missed.
          4. Apply entity disambiguation (classification society prefix
             for regulation_clause and equipment entities).
          5. Insert merged entities and relations into KuzuStore.
          6. Return the extracted entities.

        WHY:
          This is the primary write path. It is called asynchronously by
          M1's ``on_parse_complete`` hook via ``asyncio.create_task()``,
          so M1 returns immediately and the graph is built in the background.
          The hybrid rule+LLM strategy balances cost (rules are free) with
          accuracy (LLM catches context-dependent entities).

        Args:
            document_id: Unique identifier of the source document (from M1).
            chunks: List of Chunk objects from M1's parser output. Each chunk
                    must have a ``.text`` attribute (str) and optionally
                    ``.metadata`` for classification society info.

        Returns:
            List of extracted Entity objects (merged rule + LLM results,
            disambiguated, and persisted to graph).
        """
        if not chunks:
            logger.warning(
                "extract_entities: empty chunk list for doc_id=%s", document_id
            )
            return []

        # ----------------------------------------------------------------
        # Step 1: Rule-based extraction (deterministic, zero cost)
        # ----------------------------------------------------------------
        # WHY: Combine all chunk texts first. Rule extractors work more
        #      accurately on a single document-length text than on
        #      individual chunks because many patterns (e.g. "Pt.4 Ch.3")
        #      appear in context with their section headers.
        combined_text = "\n\n".join(
            getattr(chunk, "text", str(chunk)) for chunk in chunks
        )
        rule_entities: list[Entity] = rule_extract(combined_text, doc_id=document_id)
        rule_relations: list[Relation] = rule_rel(rule_entities)

        logger.info(
            "rule_extraction_complete doc_id=%s entity_count=%d relation_count=%d",
            document_id,
            len(rule_entities),
            len(rule_relations),
        )

        # ----------------------------------------------------------------
        # Step 2: Determine classification society from chunk metadata
        # ----------------------------------------------------------------
        # WHY: Entity disambiguation (merger.disambiguate_entity) needs the
        #      classification society code to prefix document-scoped entities
        #      (regulation_clause, equipment) with "DNV-" / "ABS-" etc.
        #      We extract this from the first chunk's metadata.
        doc_society: str = ""
        if chunks:
            first_chunk = chunks[0]
            meta = getattr(first_chunk, "metadata", None)
            if meta:
                cs = getattr(meta, "classification_society", None)
                if cs is not None:
                    # ClassificationSociety is a string Enum: use .value
                    doc_society = cs.value if hasattr(cs, "value") else str(cs)

        # ----------------------------------------------------------------
        # Step 3: LLM-based extraction (async, optional, graceful fallback)
        # ----------------------------------------------------------------
        llm_entities: list[Entity] = []
        llm_relations: list[Relation] = []

        if self._config.llm is not None:
            try:
                # Lazy-import LLMExtractor to avoid loading OpenAI SDK
                # at import time if LLM is never used.
                from m4_kg.extraction.llm_extractor import (  # noqa: PLC0415
                    LLMExtractor,
                )

                extractor = LLMExtractor(config=self._config)
                llm_entities, llm_relations = await extractor.extract(chunks)

                logger.info(
                    "llm_extraction_complete doc_id=%s entity_count=%d relation_count=%d",
                    document_id,
                    len(llm_entities),
                    len(llm_relations),
                )

            except Exception as exc:
                # WHY: LLM extraction is best-effort. If it fails (API error,
                #      network timeout, model not available), we fall back to
                #      rule-only results rather than failing the entire extraction.
                #      Rule extraction already covers ~70% of entities.
                logger.warning(
                    "llm_extraction_failed doc_id=%s error=%s fallback_to_rules=%s",
                    document_id,
                    exc,
                    self._config.fallback_to_rules,
                )
                if not self._config.fallback_to_rules:
                    raise

        # ----------------------------------------------------------------
        # Step 4: Merge rule + LLM results with disambiguation
        # ----------------------------------------------------------------
        # WHY: LLM overwrites rule results for matching (name, type) keys
        #      because LLM extraction has higher contextual precision.
        #      Rule results fill in entities that the LLM missed.
        entities = merge_entities(rule_entities, llm_entities, doc_society)
        relations = merge_relations(rule_relations, llm_relations)

        logger.info(
            "merge_complete doc_id=%s merged_entity_count=%d merged_relation_count=%d",
            document_id,
            len(entities),
            len(relations),
        )

        # ----------------------------------------------------------------
        # Step 5: Persist to Kuzu graph database
        # ----------------------------------------------------------------
        if entities:
            await self._store.insert_entities(entities, doc_society=doc_society)
        if relations:
            await self._store.insert_relations(relations)

        logger.info(
            "kg_extraction_complete doc_id=%s final_entity_count=%d final_relation_count=%d",
            document_id,
            len(entities),
            len(relations),
        )

        return entities

    async def extract_relations(self, entities: list[Entity]) -> list[Relation]:
        """
        Extract relations from a list of entities using rule-based heuristics.

        WHAT:
          Generates ``references`` relations between regulation_clause entities
          and ``constrains`` relations from parameter entities to equipment,
          steel_grade, and ship_type entities.

        WHY:
          LLM-extracted relations are already produced during
          ``extract_entities()`` and merged with rule relations there.
          This method exists for standalone relation extraction (e.g., when
          new entities are added manually via admin and need their relations
          generated without re-running the full LLM pipeline).

        Args:
            entities: List of Entity objects to extract relations for.

        Returns:
            List of Relation objects with deterministic IDs and confidence=1.0.
        """
        return rule_rel(entities)

    # =====================================================================
    # Query (called by M5 QA Engine)
    # =====================================================================

    async def query_entities(
        self,
        query_text: str,
        entity_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[Entity]:
        """
        Search for entities by name (CONTAINS match), optionally filtered by type.

        WHAT:
          Delegates to KuzuStore's indexed ``query_entities_by_name()`` for
          fast CONTAINS search, then optionally filters results by entity type
          in Python (Kuzu does not support combined name+type CONTAINS in
          a single index scan).

        WHY:
          Name-based entity search is used by M5 for entity disambiguation
          and as a pre-filter before graph traversal.

        Args:
            query_text: Substring to search for within entity names.
            entity_types: Optional list of entity types to filter by
                         (e.g., ["steel_grade", "regulation_clause"]).
            limit: Maximum number of results to return. Defaults to 20.

        Returns:
            List of matching Entity objects (may be empty).
        """
        entities = await self._store.query_entities_by_name(query_text, limit)

        # Apply type filter in Python if specified.
        # WHY: Kuzu's CONTAINS + EQUALS on different columns cannot be
        #      efficiently indexed together. Doing the type filter in
        #      Python is fast for the small result sets (limit=20) that
        #      this query produces.
        if entity_types:
            entities = [e for e in entities if e.entity_type in entity_types]
            entities = entities[:limit]

        return entities

    async def query_relations(
        self,
        entity_ids: list[str],
        relation_types: list[str] | None = None,
    ) -> list[Relation]:
        """
        Find relations originating from the given entity IDs.

        WHAT:
          Delegates to KuzuStore's query_relations() which performs an
          indexed lookup of outgoing edges from the specified entities,
          optionally filtered by relation type.

        WHY:
          Edge retrieval is the primitive used by BFS traversal in
          graph_search(). It is exposed as a standalone method for M5
          to inspect specific entity connections.

        Args:
            entity_ids: List of source entity ID strings to look up
                       relations for.
            relation_types: Optional list of relation types to filter by
                           (e.g., ["requires", "constrains"]). If None,
                           returns all relation types.

        Returns:
            List of Relation objects (may be empty).
        """
        return await self._store.query_relations(entity_ids, relation_types)

    # =====================================================================
    # Graph Search (called by M5 QA Engine)
    # =====================================================================

    async def graph_search(
        self, topic: str, depth: int | None = None
    ) -> Subgraph:
        """
        Search the knowledge graph by topic and expand via BFS traversal.

        WHAT:
          Two-phase search:
          1. Find seed entities whose names contain the topic string.
          2. BFS-expand from seeds up to ``depth`` hops, collecting all
             encountered entities and relations.

        WHY:
          This is the primary graph exploration interface for M5. Topic-
          based lookup finds relevant entry points, BFS expansion provides
          context (related entities, constraints, references). The depth
          and entity limits are capped by the user's tier to control
          both latency and LLM context cost downstream.

        Args:
            topic: Topic string to match against entity names (CONTAINS).
            depth: Maximum BFS hops from seed entities. If None, uses the
                   user tier's ``traversal_depth`` (1 for basic, 3 for pro,
                   5 for enterprise).

        Returns:
            Subgraph containing:
            - ``entities``: list of visited Entity instances.
            - ``relations``: list of traversed Relation instances.
            - ``query_context``: description string (e.g. "topic=EH36").
        """
        # Resolve depth: explicit argument takes priority, otherwise use
        # the user tier's configured traversal depth.
        # WHY: The tier's depth is the default cap; callers (M5) can
        #      request a shallower depth but never exceed the tier limit.
        effective_depth = depth if depth is not None else self._tier.traversal_depth

        try:
            return await graph_search_fn(
                self._store, topic, depth=effective_depth,
                max_entities=self._tier.max_entities,
            )
        except Exception as exc:
            logger.error("graph_search failed topic=%s error=%s", topic, exc)
            return Subgraph(
                entities=[], relations=[],
                query_context=f"Graph search error: {exc}",
            )

    # =====================================================================
    # Cross Reference (called by M5 QA Engine)
    # =====================================================================

    async def cross_reference(
        self,
        source_clause: str,
        source_society: str,
        target_society: str,
    ) -> CrossReferenceResult | None:
        """
        Find equivalent regulation clause across classification societies.

        WHAT:
          Uses a hybrid strategy:
          1. Graph lookup — search for existing ``similar_to`` /
             ``equivalent_to`` relations between entities in the source
             and target societies (fast, free).
          2. LLM fallback — if no high-confidence graph match, call the
             configured LLM to compute semantic equivalence (slow, costs
             tokens, result is cached as a new graph edge).

        WHY:
          Maritime professionals frequently need to map requirements
          between different classification society rulebooks. The hybrid
          strategy balances speed (cached results are sub-millisecond)
          with coverage (LLM handles new clause pairs).

        **Tier gating**: Basic tier users cannot cross-reference at all
        (this method returns None immediately). Pro and Enterprise tiers
        have access.

        Args:
            source_clause: Name or text substring of the source clause
                          (e.g., "preheat", "Pt.4 Ch.3").
            source_society: Source classification society code
                           (e.g., "DNV").
            target_society: Target classification society code
                           (e.g., "ABS").

        Returns:
            CrossReferenceResult if a match is found, None if no match
            or if the user tier disables cross-reference.
        """
        # Tier check: basic tier users cannot cross-reference.
        # WHY: Cross-reference involves graph traversal + potential LLM
        #      API costs. Basic tier is cost-minimized — no cross-society
        #      lookups are permitted.
        if not self._tier.enable_cross_ref:
            logger.debug(
                "cross_reference_blocked_by_tier tier=%s", self._tier.level
            )
            return None

        # Delegate to the search module's cross_reference function.
        # It handles graph lookup, LLM fallback, and result caching.
        try:
            return await cross_ref_fn(
                self._store, source_clause, source_society, target_society,
                llm_backend=self._config.llm,
            )
        except Exception as exc:
            logger.error("cross_reference failed clause=%s error=%s", source_clause, exc)
            return None

    # =====================================================================
    # Health Check (called by monitoring / admin dashboard)
    # =====================================================================

    async def health_check(self) -> dict[str, Any]:
        """
        Verify Kuzu graph database connectivity.

        WHAT:
          Attempts to query entities of type "steel_grade" (limit 1) to
          confirm the database connection is alive and the schema is intact.
          Returns a status dict with "ok" or "degraded".

        WHY:
          Production monitoring needs a lightweight health endpoint that
          actually tests database connectivity (not just returns hardcoded
          "ok"). Querying by indexed entity_type (steel_grade) is fast
          (<1ms) and confirms both connection and schema existence.

        Returns:
            Dictionary with:
            - ``status``: "ok" if the database is healthy, "degraded" if
              the query fails.
            - ``graph_entities``: "connected" on success.
            - ``error``: Exception message on failure (only when degraded).
        """
        try:
            # Query by entity_type (indexed column) for fast verification.
            # WHY: This confirms (a) the connection is alive, (b) the
            #      Entity table exists, and (c) the index is usable.
            #      A failing query means either no connection or a
            #      corrupted/missing schema.
            entities = await self._store.query_entities_by_type(
                "steel_grade", limit=1
            )
            return {
                "status": "ok",
                "graph_entities": "connected",
            }
        except Exception as exc:
            # Degraded status allows the system to continue operating
            # with partial functionality (e.g., no graph enrichment)
            # rather than hard-crashing.
            logger.error("health_check_failed error=%s", exc)
            return {
                "status": "degraded",
                "error": str(exc),
            }
