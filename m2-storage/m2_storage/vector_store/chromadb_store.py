"""
ChromaDB implementation of BaseVectorStore.

WHY: ChromaDB is the Personal-mode default vector store. It runs embedded
(no separate server process), uses SQLite for persistence, supports
metadata filtering via 'where' clauses, and is the most popular
lightweight vector DB in the Python ecosystem.

We use PersistentClient (not EphemeralClient) because Personal-mode
users expect their data to survive restarts.
"""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from contracts.document import Chunk, DocumentMetadata, Domain, VesselType

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


class ChromaDBStore(BaseVectorStore):
    """Vector store backed by ChromaDB (embedded, persistent).

    Chunk-to-ChromaDB mapping:
    - chunk_id   -> ChromaDB document ID (primary key)
    - text       -> ChromaDB document (searchable content)
    - metadata   -> ChromaDB metadata (filterable via 'where')
    - embedding  -> ChromaDB embedding vector
    """

    def __init__(self, config):
        """
        Args:
            config: ChromaDBConfig with persist_dir and collection_name.
        """
        self._config = config
        self._client: chromadb.PersistentClient | None = None
        self._collection: chromadb.Collection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Create or open the ChromaDB persistent client and collection.

        WHY PersistentClient: data must survive process restarts in
        Personal mode. EphemeralClient would lose all vectors on exit.
        Cosine distance is used because it's the standard for
        normalized embeddings (BGE-M3, GTE-Qwen2 produce unit vectors).
        """
        self._client = chromadb.PersistentClient(
            path=self._config.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._config.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDB initialized: %s (collection: %s, count: %d)",
            self._config.persist_dir,
            self._config.collection_name,
            self._collection.count(),
        )

    async def health_check(self) -> bool:
        """Verify the collection is accessible by probing its count."""
        try:
            if self._collection is None:
                return False
            self._collection.count()
            return True
        except Exception:
            logger.exception("ChromaDB health check failed")
            return False

    async def close(self) -> None:
        """Release ChromaDB references to allow GC."""
        self._collection = None
        self._client = None

    # ------------------------------------------------------------------
    # VectorStoreProtocol -- data operations
    # ------------------------------------------------------------------

    async def insert(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> list[str]:
        """
        Insert chunks with their pre-computed embeddings.

        WHY embeddings are passed in, not computed here: M1 (Doc Parsing)
        owns embedding generation. M2 is storage-only. This separation
        means we can swap embedding models without touching M2.

        Args:
            chunks: Parsed document chunks with metadata.
            embeddings: Pre-computed vectors in same order as chunks.

        Returns:
            List of chunk_id strings for the inserted records.
        """
        if not chunks:
            return []
        if self._collection is None:
            return []  # Safe no-op when not initialized

        ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks]

        # Flatten metadata for ChromaDB compatibility.
        # WHY flat dict: ChromaDB 'where' filters require top-level
        # string/number/boolean values, not nested objects.
        metadatas = [
            {
                "doc_id": c.metadata.source_filename.replace(".pdf", ""),
                "source_filename": c.metadata.source_filename,
                "domain": c.metadata.domain.value,
                "chunk_type": c.chunk_type,
                "language": c.metadata.language,
                "position": c.position_in_document,
                "vessel_types": ",".join(vt.value for vt in c.metadata.vessel_types)
                if c.metadata.vessel_types
                else "",
            }
            for c in chunks
        ]

        self._collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.debug("Inserted %d chunks into ChromaDB", len(chunks))
        return ids

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """
        Search for chunks by vector similarity.

        WHY we convert distance to similarity: ChromaDB returns cosine
        distances (0=identical, 2=opposite), but callers expect similarity
        scores (1=identical, 0=opposite). Formula: score = 1.0 - distance/2.0.

        Args:
            query_vector: The query embedding (from M3's query encoder).
            top_k: Maximum number of results to return.
            filters: Optional metadata key-value pairs for filtering.

        Returns:
            List of (Chunk, score) tuples ordered by descending similarity.
        """
        if self._collection is None:
            return []

        where = _build_chromadb_where(filters) if filters else None

        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[tuple[Chunk, float]] = []
        if not results["ids"] or not results["ids"][0]:
            return chunks

        for i, chunk_id in enumerate(results["ids"][0]):
            text = results["documents"][0][i]
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            score = 1.0 - (distance / 2.0)

            chunk = Chunk(
                chunk_id=chunk_id,
                text=text,
                metadata=_reconstruct_metadata(meta),
                chunk_type=meta.get("chunk_type", "general"),
                position_in_document=meta.get("position", 0),
            )
            chunks.append((chunk, score))

        return chunks

    async def delete(self, doc_id: str) -> int:
        """
        Delete all chunks belonging to a document.

        WHY delete by doc_id metadata filter, not by chunk ID: a document
        may have hundreds of chunks. Deleting by metadata filter removes
        all of them in one operation.
        """
        if self._collection is None:
            return 0
        before = self._collection.count()
        self._collection.delete(where={"doc_id": doc_id})
        after = self._collection.count()
        deleted = before - after
        logger.info("Deleted %d chunks for doc_id=%s", deleted, doc_id)
        return deleted

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Return total number of chunks, optionally filtered."""
        if self._collection is None:
            return 0
        if filters:
            where = _build_chromadb_where(filters)
            result = self._collection.get(where=where)
            return len(result["ids"]) if result["ids"] else 0
        return self._collection.count()


# ===========================================================================
# Internal helpers
# ===========================================================================


def _build_chromadb_where(filters: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a flat filter dict into a ChromaDB 'where' clause.

    WHY: ChromaDB's where clause uses a specific nested format. Our
    callers pass simple flat dicts. This adapter encapsulates ChromaDB's
    query syntax so callers don't need to know it.

    Single filter: {"domain": "structure"} -> {"domain": "structure"}
    Multi filter:  {"domain": "s", "lang": "en"} -> {"$and": [...]}
    """
    if len(filters) == 1:
        return dict(filters)
    return {"$and": [{k: v} for k, v in filters.items()]}


def _reconstruct_metadata(meta: dict) -> DocumentMetadata:
    """
    Rebuild a DocumentMetadata from the flat dict stored in ChromaDB.

    WHY: ChromaDB stores metadata as flat key-value pairs. We reconstruct
    the typed dataclass so upper modules get consistent DocumentMetadata
    objects regardless of which backend is in use.

    Preserved fields (stored as flat scalars in ChromaDB):
        source_filename, domain, language, vessel_types (comma-separated)

    Intentionally discarded fields (complex types ChromaDB cannot store
    as 'where'-filterable flat scalars):
        classification_society, regulation_name, version_year,
        chapter_section, system_type, manufacturer, equipment_model,
        page_range, custom_tags
    """
    domain_str = meta.get("domain", "general")
    try:
        domain = Domain(domain_str)
    except ValueError:
        domain = Domain.GENERAL

    # Parse vessel_types from comma-separated string back to VesselType list
    vessel_types_str = meta.get("vessel_types", "")
    vessel_types = (
        [VesselType(vt) for vt in vessel_types_str.split(",") if vt]
        if vessel_types_str
        else []
    )

    return DocumentMetadata(
        source_filename=meta.get("source_filename", "unknown"),
        domain=domain,
        language=meta.get("language", "en"),
        vessel_types=vessel_types,
    )
