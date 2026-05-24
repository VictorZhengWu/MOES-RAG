# -*- coding: utf-8 -*-
"""
M2 Storage Client for the M3 Retrieval Engine.

WHAT: Provides a typed, convenient access layer to M2's StorageManager
backends. The M2Client wraps the StorageManager and exposes its four
backends (vector_store, doc_index, file_store, relational_db) as
properties with clear type annotations.

This class is intentionally thin: it does NOT add any new functionality
beyond what the StorageManager already provides. Its purpose is:
  1. To provide a single import point for M3 code that needs M2 access.
  2. To make the dependency on M2 explicit in the M3 codebase.
  3. To allow future wrapping (e.g. caching, retry logic, circuit
     breakers) without changing every M3 file that uses M2 backends.

WHY: Module isolation is a core architectural principle of this project.
M3 must not import directly from M2's src/ directory. The contracts/
package defines the Protocol interfaces, and the M2Client wraps the
concrete StorageManager implementation. This ensures that:
  - M3 code only depends on contracts/ and this client.
  - M2 backend swap (e.g. ChromaDB -> Qdrant) requires no M3 changes.
  - Mocking M2 for M3 unit tests is straightforward (mock the
    StorageManager, not individual backends).

Usage::

    from m3_retrieval.integration.m2_client import M2Client

    sm = create_storage_manager("deploy.yaml")
    await sm.initialize()
    client = M2Client(sm)

    # Access backends directly
    results = await client.vector_store.search(query_vec, top_k=20)
    bm25 = await client.doc_index.search("hull welding", top_k=10)
"""

from __future__ import annotations

from typing import Any


class M2Client:
    """
    Typed wrapper around M2's StorageManager for M3 consumption.

    WHAT: Holds a reference to the M2 StorageManager and exposes its
    four backend attributes as properties. Provides no new functionality;
    this is purely a convenience and isolation layer.

    The four backends:
      - vector_store: ChromaDB (or Qdrant/Milvus) for dense vector search.
        Used by M3's DenseRetriever.
      - doc_index: Meilisearch (or Elasticsearch/Tantivy) for BM25/full-text
        search. Used by M3's SparseRetriever.
      - file_store: LocalFS (or S3/MinIO) for file/blob storage.
        Used by M3's ContextExpander to read full documents.
      - relational_db: SQLite (or PostgreSQL) for structured metadata.
        Used by M3 for document metadata queries.

    WHY class (not module-level functions): the StorageManager is a
    stateful object with lifecycle methods (initialize, health_check,
    close). Wrapping it in a class keeps the lifecycle management
    clear and prevents accidental global state.
    """

    def __init__(self, storage_manager: Any) -> None:
        """
        Create an M2Client wrapping a StorageManager instance.

        WHAT: Stores the storage manager reference. Does NOT call
        initialize() -- that is the caller's responsibility.

        WHY: The client should not own the lifecycle. The caller
        (typically the RetrievalEngine or application bootstrap)
        controls when backends are initialized and closed.

        Args:
            storage_manager: An initialized (or to-be-initialized)
                M2 StorageManager instance. Must implement the four
                backend protocols defined in contracts/storage.py.
        """
        # WHAT: the M2 StorageManager instance, providing access to
        # all four storage backends through its attributes.
        # WHY stored: all property accessors delegate to this.
        self._sm: Any = storage_manager

    @property
    def vector_store(self) -> Any:
        """
        Access the VectorStore backend (ChromaDB by default).

        WHAT: Returns the storage manager's vector_store attribute,
        which implements VectorStoreProtocol (from contracts/storage.py).

        Used by M3's DenseRetriever for ANN (Approximate Nearest
        Neighbour) search over BGE-M3 embeddings.

        WHY property: provides attribute-style access (client.vector_store)
        that matches the StorageManager's own interface, avoiding
        getter method boilerplate while keeping the internal reference
        encapsulated.
        """
        return self._sm.vector_store

    @property
    def doc_index(self) -> Any:
        """
        Access the DocumentIndex backend (Meilisearch by default).

        WHAT: Returns the storage manager's doc_index attribute,
        which implements DocumentIndexProtocol (from contracts/storage.py).

        Used by M3's SparseRetriever for BM25 full-text keyword search.

        WHY property: same as vector_store -- attribute-style access
        for consistency with the StorageManager interface.
        """
        return self._sm.doc_index

    @property
    def file_store(self) -> Any:
        """
        Access the FileStore backend (LocalFS by default).

        WHAT: Returns the storage manager's file_store attribute,
        which implements FileStoreProtocol (from contracts/storage.py).

        Used by M3's ContextExpander to read full documents for
        chunk context expansion.

        WHY property: same as above.
        """
        return self._sm.file_store

    @property
    def relational_db(self) -> Any:
        """
        Access the RelationalDB backend (SQLite by default).

        WHAT: Returns the storage manager's relational_db attribute,
        which implements RelationalDBProtocol (from contracts/storage.py).

        Used by M3 for document metadata queries (e.g. looking up
        document info by doc_id).

        WHY property: same as above.
        """
        return self._sm.relational_db
