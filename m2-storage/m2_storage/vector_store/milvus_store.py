"""
Milvus implementation of BaseVectorStore.

WHAT: Enterprise-grade vector store backed by Milvus, the open-source
      vector database. Supports distributed deployment, billions of vectors,
      and advanced indexing (IVF_FLAT, HNSW).

WHY: ChromaDB is sufficient for Personal mode (<10K chunks) but cannot
     scale to enterprise document volumes (millions of chunks across
     hundreds of documents). Milvus provides:
     - Horizontal scaling (multiple nodes)
     - GPU-accelerated indexing
     - Advanced ANN algorithms (HNSW, IVF_PQ, DiskANN)
     - Multi-tenancy via partitions

Architecture:
  Milvus runs as a separate service (unlike embedded ChromaDB).
  Minimum deployment: Milvus Standalone (single Docker container).
  Production deployment: Milvus Cluster (coordinator + proxy + data nodes).

Dependencies: pip install pymilvus
"""

from __future__ import annotations

import json
import logging
from typing import Any

from contracts.document import Chunk

from .base import BaseVectorStore

logger = logging.getLogger(__name__)

# Milvus imports are deferred — the module can be imported without pymilvus
# installed, but initialize() will raise if it's missing.

# Collection schema constants
_COLLECTION_NAME: str = "marine_rag"
_VECTOR_DIM: int = 1024  # Default BGE-M3 dimension
_INDEX_TYPE: str = "IVF_FLAT"
_METRIC_TYPE: str = "COSINE"
_NLIST: int = 128  # IVF cluster count


class MilvusStore(BaseVectorStore):
    """
    Vector store backed by Milvus.

    WHAT: Wraps pymilvus for insert, search, delete, and lifecycle.
          Automatically creates the collection and index on first use.

    Args:
        host: Milvus server hostname (default: localhost).
        port: Milvus gRPC port (default: 19530).
        collection_name: Name of the Milvus collection (default: marine_rag).
        vector_dim: Dimension of embedding vectors (default: 1024).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = _COLLECTION_NAME,
        vector_dim: int = _VECTOR_DIM,
    ):
        self._host = host
        self._port = port
        self._collection_name = collection_name
        self._vector_dim = vector_dim
        self._collection = None  # Lazy: created in initialize()
        self._connected = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Connect to Milvus and ensure the collection exists.

        WHAT: Opens a connection to the Milvus server, checks if the
              collection exists, creates it if not, and loads it into
              memory for search operations.

        WHY: Milvus collections must be explicitly loaded before they
             can be searched. This is a one-time operation at startup.
        """
        if self._connected:
            return

        try:
            from pymilvus import (
                Collection, CollectionSchema, DataType, FieldSchema,
                IndexType, Utility, connections,
            )

            # Connect to Milvus server
            connections.connect(
                alias="default",
                host=self._host,
                port=str(self._port),
            )

            # Check if collection exists, create if not
            if not Utility.has_collection(self._collection_name):
                logger.info(
                    "Creating Milvus collection: %s (dim=%d)",
                    self._collection_name, self._vector_dim,
                )
                fields = [
                    FieldSchema(
                        name="chunk_id", dtype=DataType.VARCHAR,
                        max_length=128, is_primary=True,
                    ),
                    FieldSchema(
                        name="text", dtype=DataType.VARCHAR,
                        max_length=65535,
                    ),
                    FieldSchema(
                        name="embedding", dtype=DataType.FLOAT_VECTOR,
                        dim=self._vector_dim,
                    ),
                    FieldSchema(
                        name="metadata_json", dtype=DataType.VARCHAR,
                        max_length=4096,
                    ),
                ]
                schema = CollectionSchema(
                    fields=fields,
                    description="Marine & Offshore Expert System chunks",
                )
                collection = Collection(name=self._collection_name, schema=schema)

                # Create IVF_FLAT index (good balance of speed vs recall)
                index_params = {
                    "metric_type": _METRIC_TYPE,
                    "index_type": _INDEX_TYPE,
                    "params": {"nlist": _NLIST},
                }
                collection.create_index(
                    field_name="embedding", index_params=index_params,
                )
                logger.info(
                    "Created Milvus index: %s on %s collection",
                    _INDEX_TYPE, self._collection_name,
                )
                collection.load()
            else:
                collection = Collection(name=self._collection_name)
                collection.load()

            self._collection = collection
            self._connected = True
            logger.info(
                "Milvus connected: %s:%d, collection=%s, entities=%d",
                self._host, self._port, self._collection_name,
                collection.num_entities,
            )

        except ImportError:
            raise RuntimeError(
                "pymilvus is not installed. Run: pip install pymilvus"
            )
        except Exception as exc:
            logger.error("Failed to initialize Milvus: %s", exc)
            raise RuntimeError(f"Milvus initialization failed: {exc}") from exc

    async def health_check(self) -> bool:
        """Verify Milvus connection is alive."""
        if not self._connected or self._collection is None:
            return False
        try:
            from pymilvus import Utility
            return Utility.has_collection(self._collection_name)
        except Exception:
            return False

    async def close(self) -> None:
        """Release Milvus connection."""
        if self._connected:
            try:
                from pymilvus import connections
                connections.disconnect("default")
            except Exception:
                pass
            self._connected = False
            self._collection = None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def insert(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> list[str]:
        """
        Insert chunks with pre-computed embeddings into Milvus.

        WHAT: Batch-inserts chunks and their embedding vectors. Each chunk
              gets a unique ID, its text content, the embedding vector,
              and serialized metadata.

        WHY: Milvus requires explicit schema data (unlike ChromaDB which
             auto-serializes). Metadata is stored as a JSON string in a
             VARCHAR field for flexibility.
        """
        if not self._connected or self._collection is None:
            raise RuntimeError("Milvus not initialized. Call initialize() first.")

        if not chunks:
            return []

        # Prepare batch data
        ids: list[str] = []
        texts: list[str] = []
        vectors: list[list[float]] = []
        metadatas: list[str] = []

        for chunk, emb in zip(chunks, embeddings):
            ids.append(chunk.chunk_id)
            texts.append(chunk.text)
            vectors.append(emb)
            # Serialize metadata to JSON string
            meta = {
                "source_filename": chunk.metadata.source_filename,
                "domain": chunk.metadata.domain.value if hasattr(chunk.metadata.domain, "value") else str(chunk.metadata.domain),
                "chunk_type": chunk.chunk_type,
                "position": chunk.position_in_document,
                "language": chunk.metadata.language,
            }
            if chunk.metadata.classification_society:
                meta["classification_society"] = chunk.metadata.classification_society.value if hasattr(chunk.metadata.classification_society, "value") else str(chunk.metadata.classification_society)
            if chunk.metadata.chapter_section:
                meta["chapter_section"] = chunk.metadata.chapter_section
            if chunk.metadata.version_year:
                meta["version_year"] = chunk.metadata.version_year
            metadatas.append(json.dumps(meta, ensure_ascii=False))

        # Batch insert (Milvus auto-batches by default)
        self._collection.insert([ids, texts, vectors, metadatas])
        self._collection.flush()
        return ids

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """
        Search Milvus by vector similarity.

        WHAT: Executes ANN search on the embedding field, returns top_k
              results with distance scores. Optional metadata filter via
              boolean expression (Milvus expr syntax).

        WHY: Milvus uses a different filter syntax than ChromaDB (boolean
             expressions like 'classification_society == "DNV"' rather
             than ChromaDB's where-dict). We translate simple filters.
        """
        if not self._connected or self._collection is None:
            raise RuntimeError("Milvus not initialized.")

        # Build search expression
        expr: str | None = None
        if filters:
            conditions = []
            if "classification_society" in filters:
                conditions.append(
                    f"classification_society == '{filters['classification_society']}'"
                )
            if "chapter_section" in filters:
                conditions.append(
                    f"chapter_section == '{filters['chapter_section']}'"
                )
            if "version_year" in filters:
                conditions.append(f"version_year == {filters['version_year']}")
            if conditions:
                expr = " && ".join(conditions) if len(conditions) > 1 else conditions[0]

        search_params = {"metric_type": _METRIC_TYPE, "params": {"nprobe": 16}}

        results = self._collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["chunk_id", "text", "metadata_json"],
        )

        # Convert Milvus results to (Chunk, score) tuples
        chunks: list[tuple[Chunk, float]] = []
        if results and len(results) > 0:
            for hit in results[0]:
                metadata_dict = json.loads(
                    hit.entity.get("metadata_json", "{}")
                )
                chunk = self._hit_to_chunk(
                    hit.entity.get("chunk_id", ""),
                    hit.entity.get("text", ""),
                    metadata_dict,
                )
                # Milvus returns distance (lower=better for COSINE).
                # Convert to similarity score: 1.0 - distance
                score = 1.0 - hit.distance if hit.distance else 0.0
                chunks.append((chunk, round(float(score), 4)))

        return chunks

    async def delete(self, doc_id: str) -> int:
        """
        Delete all chunks for a document.

        WHAT: Deletes entities where source_filename == doc_id.
              Returns count of deleted entities.

        NOTE: Milvus delete by expression requires collection to be loaded.
        """
        if not self._connected or self._collection is None:
            return 0

        expr = f"source_filename == '{doc_id}'"
        try:
            before = self._collection.num_entities
            self._collection.delete(expr)
            self._collection.flush()
            after = self._collection.num_entities
            return before - after
        except Exception as exc:
            logger.error("Milvus delete failed: %s", exc)
            return 0

    async def count(self) -> int:
        """Return the total number of entities in the collection."""
        if not self._connected or self._collection is None:
            return 0
        return self._collection.num_entities

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _hit_to_chunk(
        self, chunk_id: str, text: str, metadata_dict: dict
    ) -> Chunk:
        """Convert a Milvus search hit to a contracts Chunk object."""
        from contracts.document import (
            Chunk, DocumentMetadata, Domain, ClassificationSociety,
        )

        society = None
        if metadata_dict.get("classification_society"):
            try:
                society = ClassificationSociety(metadata_dict["classification_society"])
            except (ValueError, TypeError):
                pass

        domain = Domain.GENERAL
        if metadata_dict.get("domain"):
            try:
                domain = Domain(metadata_dict["domain"])
            except (ValueError, TypeError):
                pass

        return Chunk(
            chunk_id=chunk_id,
            text=text,
            metadata=DocumentMetadata(
                source_filename=metadata_dict.get("source_filename", ""),
                domain=domain,
                classification_society=society,
                regulation_name=metadata_dict.get("regulation_name"),
                chapter_section=metadata_dict.get("chapter_section"),
                version_year=metadata_dict.get("version_year"),
                language=metadata_dict.get("language", "en"),
            ),
            chunk_type=metadata_dict.get("chunk_type", "clause"),
            position_in_document=metadata_dict.get("position", 0),
        )
