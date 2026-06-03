"""
Kuzu graph database wrapper for the Marine & Offshore knowledge graph.

WHAT:
- ``KuzuStore`` is the persistence layer for entities and relations extracted
  from maritime/offshore engineering documents.
- Wraps Kuzu (embedded graph database) behind an async-compatible interface
  with lazy connection initialization, batch insert, typed queries, and
  cascade document-level deletion.

WHY:
- Kuzu provides zero-service, single-file graph storage (MIT license) ideal
  for personal mode deployment. Its embedded nature eliminates the need for
  a separate graph database server.
- The async interface ensures future compatibility with M5's async QA engine
  without requiring changes to callers when Kuzu eventually supports async.
- Five indexes on the most common query columns make graph_search (~50ms)
  and cross_reference queries fast regardless of graph size.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import kuzu

from m4_kg.graph.schema import create_schema, create_indexes

if TYPE_CHECKING:
    from contracts.knowledge_graph import Entity, Relation


class KuzuStore:
    """
    Kuzu graph database wrapper for marine knowledge graph CRUD operations.

    WHAT:
    - Manages a Kuzu embedded graph database for storing entities (nodes)
      and relations (edges) extracted from classification society documents.
    - Provides typed query methods (by name, type, society) and cascade
      deletion by source document ID.

    WHY:
    - Centralises all graph persistence concerns in one class so the
      extraction pipeline (rule_extractor, llm_extractor, merger) and the
      search layer (graph_search, cross_reference, traversal) only need
      to depend on this single interface.
    - Lazy connection init avoids creating database connections at import
      time, which would fail if the data directory does not yet exist.

    Usage::

        store = KuzuStore(db_path="./data/graph/marine_rag.db")
        await store.insert_entities(my_entities, doc_society="DNV")
        results = await store.query_entities_by_name("EH36")
        await store.close()
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, db_path: str = "./data/graph/marine_rag.db") -> None:
        """
        Initialise the KuzuStore with a path to the database file.

        WHAT:
        - Stores the database path. No connection is created until the first
          operation (lazy init pattern).

        WHY:
        - Lazy init prevents connection failures at import time and allows
          the caller to control when resources are allocated. The database
          file is created automatically by Kuzu on first connection.

        Args:
            db_path: Filesystem path to the Kuzu database directory.
                     Defaults to ``./data/graph/marine_rag.db``.
        """
        self._db_path: str = db_path
        self._db: kuzu.Database | None = None
        self._conn: kuzu.Connection | None = None

    # ------------------------------------------------------------------
    # Internal: connection management
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        """
        Lazy-initialise the Kuzu database and connection on first use.

        WHAT:
        - Creates a ``kuzu.Database`` and ``kuzu.Connection`` if they do
          not already exist.
        - Calls ``_init_schema()`` to create node/rel tables and indexes
          the first time a connection is established.

        WHY:
        - Kuzu opens the database directory on first connection; doing this
          lazily avoids I/O until the store is actually used.
        """
        if self._conn is None:
            self._db = kuzu.Database(self._db_path)
            self._conn = kuzu.Connection(self._db)
            self._init_schema()

    def _init_schema(self) -> None:
        """
        Create the Entity/Rel tables and their indexes.

        WHAT:
        - Delegates to ``create_schema()`` and ``create_indexes()`` from
          ``m4_kg.graph.schema``.
        - Both functions are idempotent: they check for existing tables
          and catch duplicate-index errors.

        WHY:
        - Called automatically on first connection, so callers never need
          to worry about schema initialisation.
        """
        assert self._conn is not None, "Connection must exist before init_schema"
        create_schema(self._conn)
        create_indexes(self._conn)

    # ------------------------------------------------------------------
    # Internal: row-to-dataclass helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_entity(row: list) -> Entity:
        """
        Convert a Kuzu query result row into an ``Entity`` dataclass.

        WHAT:
        - Maps column positions 0-4 from the query result to Entity fields.
        - Parses the ``properties`` column from a JSON string back to a dict.

        WHY:
        - Kuzu stores complex data (dict) as STRING (JSON text). The
          Entity contract expects ``properties: dict[str, Any]``, so
          deserialisation is required on every read.

        Expected row layout (from RETURN clause)::

            [entity_id, name, entity_type, properties_json, source_doc_id]

        Args:
            row: A list of values returned by ``result.get_next()``.

        Returns:
            An ``Entity`` dataclass instance.
        """
        # Lazily import to keep module-level imports clean
        from contracts.knowledge_graph import Entity  # noqa: PLC0415

        properties_raw: str = row[3] if row[3] is not None else "{}"
        try:
            properties: dict = json.loads(properties_raw)
        except (json.JSONDecodeError, TypeError):
            properties = {}

        return Entity(
            entity_id=str(row[0]),
            name=str(row[1]) if row[1] is not None else "",
            entity_type=str(row[2]) if row[2] is not None else "",
            properties=properties,
            source_doc_id=str(row[4]) if row[4] is not None else None,
        )

    @staticmethod
    def _row_to_relation(row: list) -> Relation:
        """
        Convert a Kuzu query result row into a ``Relation`` dataclass.

        WHAT:
        - Maps column positions 0-5 from the query result to Relation fields.
        - Extracts ``_relation_id`` from the properties JSON if present;
          otherwise generates a new UUID.
        - Parses the ``properties`` column from a JSON string back to a dict.

        WHY:
        - Kuzu's Rel table does not have a native ``relation_id`` column.
          The relation_id is stored inside the properties JSON under the
          ``_relation_id`` key so it survives database round-trips.

        Expected row layout (from RETURN clause)::

            [source_id, target_id, relation_type, properties_json, confidence, source_doc_id]

        Args:
            row: A list of values returned by ``result.get_next()``.

        Returns:
            A ``Relation`` dataclass instance.
        """
        from contracts.knowledge_graph import Relation  # noqa: PLC0415

        properties_raw: str = row[3] if row[3] is not None else "{}"
        try:
            properties: dict = json.loads(properties_raw)
        except (json.JSONDecodeError, TypeError):
            properties = {}

        # Extract relation_id from properties if stored there, otherwise
        # generate a new one (for relations created without an explicit ID).
        relation_id: str = properties.pop("_relation_id", str(uuid.uuid4()))

        return Relation(
            relation_id=relation_id,
            source_entity_id=str(row[0]),
            target_entity_id=str(row[1]),
            relation_type=str(row[2]) if row[2] is not None else "",
            properties=properties,
            confidence=float(row[4]) if row[4] is not None else 1.0,
        )

    # ------------------------------------------------------------------
    # Public API: entity CRUD
    # ------------------------------------------------------------------

    async def insert_entities(
        self, entities: list[Entity], doc_society: str = ""
    ) -> None:
        """
        Batch-insert entities into the Entity node table.

        WHAT:
        - Inserts each entity as a node with properties serialised to JSON.
        - Entities are inserted in batches of 100 for organisation (Kuzu
          auto-commits each ``execute()`` individually).
        - The ``doc_society`` and ``ref_count`` fields are Kuzu-internal
          columns not present in the Entity contract; they are set to the
          provided value and 1 respectively.

        WHY:
        - Batch insertion is the primary write path from the extraction
          pipeline (rule_extractor, llm_extractor, merger) into the graph.
        - Serialising ``properties`` to JSON allows Kuzu to store
          arbitrarily complex entity metadata without schema changes.

        Args:
            entities: List of ``Entity`` dataclass instances to insert.
            doc_society: Classification society identifier (e.g., "DNV",
                         "ABS"). Stored on the node for filtering. Defaults
                         to empty string.

        Raises:
            RuntimeError: If the Kuzu connection has not been initialised.
        """
        self._ensure_connected()
        assert self._conn is not None

        batch_size = 100
        for i in range(0, len(entities), batch_size):
            batch = entities[i : i + batch_size]
            for entity in batch:
                properties_json: str = json.dumps(
                    entity.properties, ensure_ascii=False
                )
                # MERGE ensures idempotent insertion:
                #   - If entity_id does NOT exist → CREATE with ref_count=1.
                #   - If entity_id EXISTS → increment ref_count (shared entity
                #     across multiple documents per M4-D09 SHARED_RETAIN strategy).
                self._conn.execute(
                    "MERGE (e:Entity {entity_id: $entity_id}) "
                    "ON CREATE SET "
                    "  e.name = $name, "
                    "  e.entity_type = $entity_type, "
                    "  e.properties = $properties, "
                    "  e.source_doc_id = $source_doc_id, "
                    "  e.doc_society = $doc_society, "
                    "  e.ref_count = 1 "
                    "ON MATCH SET "
                    "  e.ref_count = e.ref_count + 1, "
                    "  e.properties = $properties, "
                    "  e.source_doc_id = $source_doc_id",
                    {
                        "entity_id": entity.entity_id,
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "properties": properties_json,
                        "source_doc_id": entity.source_doc_id or "",
                        "doc_society": doc_society,
                    },
                )

    async def query_entities_by_name(
        self, name: str, limit: int = 20
    ) -> list[Entity]:
        """
        Search for entities whose name contains the given substring.

        WHAT:
        - Runs a CONTAINS query against the indexed ``Entity.name`` column.
        - Returns up to ``limit`` matching entities.

        WHY:
        - Name-based CONTAINS search is the primary entry point for
          ``graph_search()``, which uses a user-provided topic string to
          locate seed entities for graph traversal.

        Args:
            name: Substring to search for within entity names.
            limit: Maximum number of results to return (default 20).

        Returns:
            List of matching ``Entity`` instances (may be empty).
        """
        self._ensure_connected()
        assert self._conn is not None

        result = self._conn.execute(
            "MATCH (e:Entity) "
            "WHERE e.name CONTAINS $name "
            "RETURN e.entity_id, e.name, e.entity_type, e.properties, e.source_doc_id "
            "LIMIT $limit",
            {"name": name, "limit": limit},
        )
        entities: list[Entity] = []
        while result.has_next():
            entities.append(self._row_to_entity(result.get_next()))
        return entities

    async def query_entities_by_type(
        self, entity_type: str, limit: int = 20
    ) -> list[Entity]:
        """
        Find all entities of a specific type.

        WHAT:
        - Exact-match query on the indexed ``Entity.entity_type`` column.

        WHY:
        - Type filtering narrows graph_search results to specific categories
          (e.g., only "steel_grade" entities, excluding "regulation_clause").
          The index on entity_type makes this O(log N).

        Args:
            entity_type: The entity type to filter by (e.g., "steel_grade",
                         "regulation_clause", "equipment").
            limit: Maximum number of results (default 20).

        Returns:
            List of matching ``Entity`` instances (may be empty).
        """
        self._ensure_connected()
        assert self._conn is not None

        result = self._conn.execute(
            "MATCH (e:Entity) "
            "WHERE e.entity_type = $type "
            "RETURN e.entity_id, e.name, e.entity_type, e.properties, e.source_doc_id "
            "LIMIT $limit",
            {"type": entity_type, "limit": limit},
        )
        entities: list[Entity] = []
        while result.has_next():
            entities.append(self._row_to_entity(result.get_next()))
        return entities

    async def query_entities_by_society(
        self, society: str, limit: int = 20
    ) -> list[Entity]:
        """
        Find all entities belonging to a specific classification society.

        WHAT:
        - Exact-match query on the indexed ``Entity.doc_society`` column.

        WHY:
        - Society-based filtering is the pre-filter step for
          ``cross_reference()``, which maps clauses between different
          classification societies (e.g., DNV to ABS).

        Args:
            society: Classification society code (e.g., "DNV", "ABS", "CCS").
            limit: Maximum number of results (default 20).

        Returns:
            List of matching ``Entity`` instances (may be empty).
        """
        self._ensure_connected()
        assert self._conn is not None

        result = self._conn.execute(
            "MATCH (e:Entity) "
            "WHERE e.doc_society = $society "
            "RETURN e.entity_id, e.name, e.entity_type, e.properties, e.source_doc_id "
            "LIMIT $limit",
            {"society": society, "limit": limit},
        )
        entities: list[Entity] = []
        while result.has_next():
            entities.append(self._row_to_entity(result.get_next()))
        return entities

    async def query_entities_by_ids(
        self, entity_ids: list[str]
    ) -> list[Entity]:
        """
        Fetch entities by their exact entity_id values.

        WHAT:
        - Runs an IN-clause query against the primary key ``Entity.entity_id``.
        - Returns all matching entities in a single batch query.
        - Returns empty list if ``entity_ids`` is empty (no query executed).

        WHY:
        - ID-based lookup is required by graph traversal (``bfs_traverse``)
          to efficiently fetch newly discovered entities after each BFS hop.
          Without this, each entity would require a separate name-based
          query, making traversal O(N) queries instead of O(depth).

        Args:
            entity_ids: List of entity ID strings to look up.

        Returns:
            List of matching ``Entity`` instances (may be empty or shorter
            than input if some IDs don't exist in the graph).
        """
        if not entity_ids:
            return []

        self._ensure_connected()
        assert self._conn is not None

        result = self._conn.execute(
            "MATCH (e:Entity) "
            "WHERE e.entity_id IN $entity_ids "
            "RETURN e.entity_id, e.name, e.entity_type, e.properties, e.source_doc_id",
            {"entity_ids": entity_ids},
        )
        entities: list[Entity] = []
        while result.has_next():
            entities.append(self._row_to_entity(result.get_next()))
        return entities

    # ------------------------------------------------------------------
    # Public API: relation CRUD
    # ------------------------------------------------------------------

    async def insert_relations(self, relations: list[Relation]) -> None:
        """
        Batch-insert relationships between existing entities.

        WHAT:
        - For each relation, MATCHes the source and target entities,
          then CREATEs a Rel edge between them.
        - Serialises ``properties`` to JSON. Embeds ``relation_id`` inside
          the properties JSON under ``_relation_id`` for round-trip recovery.
        - Inserts in batches of 100 for organisation.

        WHY:
        - Relations are the edges that make the knowledge graph traversable.
          graph_search, cross_reference, and traversal all depend on edges.
        - Storing ``relation_id`` in properties avoids schema changes while
          preserving the identifier across database round-trips.

        Args:
            relations: List of ``Relation`` dataclass instances. Source and
                       target entities must already exist in the graph.

        Raises:
            RuntimeError: If the Kuzu connection has not been initialised.
        """
        self._ensure_connected()
        assert self._conn is not None

        batch_size = 100
        for i in range(0, len(relations), batch_size):
            batch = relations[i : i + batch_size]
            for rel in batch:
                # Embed relation_id in properties so it survives round-trips
                props_copy: dict = dict(rel.properties)
                props_copy["_relation_id"] = rel.relation_id
                properties_json: str = json.dumps(props_copy, ensure_ascii=False)

                self._conn.execute(
                    "MATCH (s:Entity {entity_id: $src_id}),"
                    "      (t:Entity {entity_id: $tgt_id}) "
                    "CREATE (s)-[r:Rel {"
                    "  relation_type: $type,"
                    "  properties: $properties,"
                    "  confidence: $confidence,"
                    "  source_doc_id: $source_doc_id"
                    "}]->(t)",
                    {
                        "src_id": rel.source_entity_id,
                        "tgt_id": rel.target_entity_id,
                        "type": rel.relation_type,
                        "properties": properties_json,
                        "confidence": float(rel.confidence),
                        "source_doc_id": "",
                    },
                )

    async def query_relations(
        self,
        entity_ids: list[str],
        relation_types: list[str] | None = None,
    ) -> list[Relation]:
        """
        Find all relations originating from any of the given entity IDs.

        WHAT:
        - MATCHes (source)-[rel]->(target) patterns where the source
          entity_id is in the provided list.
        - Optionally filters by relation type.
        - Returns full Relation objects with source and target entity IDs.

        WHY:
        - Edge retrieval is essential for graph traversal (BFS expansion)
          and for inspecting connections between specific entities.

        Args:
            entity_ids: List of source entity IDs to find relations for.
            relation_types: Optional list of relation types to filter by
                            (e.g., ["requires", "references"]). If None,
                            all relation types are returned.

        Returns:
            List of ``Relation`` instances (may be empty).
        """
        self._ensure_connected()
        assert self._conn is not None

        if not entity_ids:
            return []

        # Build query with optional relation_type filter
        query = (
            "MATCH (s:Entity)-[r:Rel]->(t:Entity) "
            "WHERE s.entity_id IN $entity_ids"
        )
        params: dict = {"entity_ids": entity_ids}

        if relation_types:
            query += " AND r.relation_type IN $relation_types"
            params["relation_types"] = relation_types

        query += (
            " RETURN s.entity_id, t.entity_id, r.relation_type,"
            "        r.properties, r.confidence, r.source_doc_id"
        )

        result = self._conn.execute(query, params)
        relations: list[Relation] = []
        while result.has_next():
            relations.append(self._row_to_relation(result.get_next()))
        return relations

    # ------------------------------------------------------------------
    # Public API: deletion
    # ------------------------------------------------------------------

    async def delete_by_doc_id(self, doc_id: str) -> int:
        """
        Cascade-delete all entities and relations for a given document.

        WHAT:
        - Counts entities matching the document ID, then deletes all
          associated relationships (both incoming and outgoing), and
          finally deletes the entities themselves.
        - Returns the pre-deletion count of matching entities.

        WHY:
        - Document-level cascade deletion is the core mechanism for
          incremental graph updates: when a document is removed or
          re-parsed, its old entities and relations must be cleaned up
          before new ones are inserted.
        - By counting first and then deleting relationships before
          entities, we avoid (a) DELETE+RETURN compatibility issues in
          Kuzu and (b) orphaned-edge errors when deleting nodes.

        Args:
            doc_id: The source document ID to delete all data for.

        Returns:
            Number of entities that matched the document ID before deletion.
        """
        self._ensure_connected()
        assert self._conn is not None

        # Step 1: Count matching entities before deletion so we can
        # return a meaningful count to the caller.
        count_result = self._conn.execute(
            "MATCH (e:Entity) "
            "WHERE e.source_doc_id = $doc_id "
            "RETURN COUNT(*)",
            {"doc_id": doc_id},
        )
        entity_count = 0
        if count_result.has_next():
            entity_count = int(count_result.get_next()[0])

        # Step 2: Delete outgoing relationships (where source entity
        # belongs to this document).
        self._conn.execute(
            "MATCH (s:Entity)-[r:Rel]->(t:Entity) "
            "WHERE s.source_doc_id = $doc_id "
            "DELETE r",
            {"doc_id": doc_id},
        )

        # Step 3: Delete incoming relationships (where target entity
        # belongs to this document).
        self._conn.execute(
            "MATCH (s:Entity)-[r:Rel]->(t:Entity) "
            "WHERE t.source_doc_id = $doc_id "
            "DELETE r",
            {"doc_id": doc_id},
        )

        # Step 4: Delete or decrement entities based on ref_count.
        #   - ref_count == 1: Entity exists only in this document → DELETE.
        #   - ref_count >= 2: Entity shared across multiple documents →
        #     SET ref_count = ref_count - 1, keep the entity.
        #   WHY: Implements M4-D09 incremental update strategy (SHARED_RETAIN).
        self._conn.execute(
            "MATCH (e:Entity) "
            "WHERE e.source_doc_id = $doc_id AND e.ref_count = 1 "
            "DELETE e",
            {"doc_id": doc_id},
        )
        self._conn.execute(
            "MATCH (e:Entity) "
            "WHERE e.source_doc_id = $doc_id AND e.ref_count >= 2 "
            "SET e.ref_count = e.ref_count - 1",
            {"doc_id": doc_id},
        )

        return entity_count

    # ------------------------------------------------------------------
    # Public API: lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """
        Close the Kuzu database connection and release resources.

        WHAT:
        - Sets ``_conn`` and ``_db`` to None after closing.
        - Safe to call multiple times (no-op if already closed).

        WHY:
        - Kuzu holds file handles and memory buffers that should be
          released when the store is no longer needed. Tests depend on
          this to clean up temporary database directories.
        """
        if self._conn is not None:
            # Kuzu Connection does not have an explicit close() in all
            # versions; setting to None allows garbage collection.
            self._conn = None
        self._db = None
