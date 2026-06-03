"""
Graph schema and index definitions for the Marine & Offshore knowledge graph.

WHAT:
- Defines Cypher DDL statements for creating the Entity node table and Rel
  relationship table in Kuzu embedded graph database.
- Provides functions to execute schema creation and index creation on a
  Kuzu connection.

WHY:
- Entity and Rel are the two core graph primitives needed for knowledge
  graph queries (graph_search, cross_reference, traversal).
- Five indexes accelerate the most common query patterns: name search,
  type filtering, classification society filtering, relation type
  filtering, and document-level cascade deletes.
- Separating schema.py from kuzu_store.py keeps DDL concerns isolated
  and makes the schema easy to evolve independently of the store logic.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Cypher DDL: Entity Node Table
# ---------------------------------------------------------------------------

CREATE_NODE_TABLE_SQL = """
CREATE NODE TABLE Entity(
    entity_id STRING,
    name STRING,
    entity_type STRING,
    properties STRING,
    source_doc_id STRING,
    doc_society STRING,
    ref_count INT64 DEFAULT 1,
    created_at TIMESTAMP DEFAULT current_timestamp(),
    PRIMARY KEY (entity_id)
)
""".strip()

# ---------------------------------------------------------------------------
# Cypher DDL: Rel (Relationship) Table
# ---------------------------------------------------------------------------

CREATE_REL_TABLE_SQL = """
CREATE REL TABLE Rel(
    FROM Entity TO Entity,
    relation_type STRING,
    properties STRING,
    confidence DOUBLE,
    source_doc_id STRING,
    created_at TIMESTAMP DEFAULT current_timestamp()
)
""".strip()

# ---------------------------------------------------------------------------
# Index definitions (for query performance)
# ---------------------------------------------------------------------------

CREATE_INDEXES_SQL: list[str] = [
    "CREATE INDEX ON Entity(name)",
    "CREATE INDEX ON Entity(entity_type)",
    "CREATE INDEX ON Entity(doc_society)",
    "CREATE INDEX ON Rel(relation_type)",
    "CREATE INDEX ON Rel(source_doc_id)",
]


# ---------------------------------------------------------------------------
# Schema creation functions
# ---------------------------------------------------------------------------

def create_schema(conn) -> None:
    """
    Create the Entity node table and Rel relationship table in Kuzu.

    WHAT:
    - Executes CREATE_NODE_TABLE_SQL and CREATE_REL_TABLE_SQL against
      the provided Kuzu connection.
    - Uses ``SHOW_TABLES()`` to check if tables already exist before
      creating (idempotent on repeated calls).

    WHY:
    - Schema creation must be idempotent because KuzuStore._init_schema()
      is called on every lazy connection initialization. Repeated calls
      must not fail if tables already exist.

    Args:
        conn: An active ``kuzu.Connection`` instance.
    """
    # Check which tables already exist to make schema init idempotent
    tables_result = conn.execute("CALL show_tables() RETURN name")
    existing_tables: set[str] = set()
    while tables_result.has_next():
        row = tables_result.get_next()
        existing_tables.add(str(row[0]))

    # Create Entity node table if it does not exist
    if "Entity" not in existing_tables:
        conn.execute(CREATE_NODE_TABLE_SQL)

    # Create Rel relationship table if it does not exist
    if "Rel" not in existing_tables:
        conn.execute(CREATE_REL_TABLE_SQL)


def create_indexes(conn) -> None:
    """
    Create performance-critical indexes on the Entity and Rel tables.

    WHAT:
    - Executes all 5 index creation statements defined in CREATE_INDEXES_SQL
      against the provided Kuzu connection.
    - Uses try/except to silently skip any index that already exists,
      making this function idempotent.

    WHY:
    - Five indexes target the most frequent query patterns:
      * Entity(name)      — name-based search (graph_search primary entry point)
      * Entity(entity_type) — type filtering to narrow results
      * Entity(doc_society) — society filtering (cross_reference pre-filter)
      * Rel(relation_type)  — relation type filtering during traversal
      * Rel(source_doc_id)  — document-level cascade delete (incremental update)
    - Idempotent creation allows safe repeated calls during store initialization
      without disrupting an already-running database.

    Args:
        conn: An active ``kuzu.Connection`` instance.
    """
    for index_sql in CREATE_INDEXES_SQL:
        try:
            conn.execute(index_sql)
        except Exception:
            # Index already exists or unsupported in this Kuzu version;
            # silently skip and continue with remaining indexes.
            pass
