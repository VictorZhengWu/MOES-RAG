"""
Qdrant implementation of BaseVectorStore.

WHAT: Lightweight enterprise vector store backed by Qdrant, a Rust-based
      vector database. Single binary deployment — simpler than Milvus
      (no etcd/minio dependencies).

WHY: Qdrant is the sweet spot between embedded ChromaDB and heavyweight
     Milvus. One Docker container, REST + gRPC APIs, production-ready
     without the operational complexity of distributed systems.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from contracts.document import Chunk

from .base import BaseVectorStore

logger = logging.getLogger(__name__)

_COLLECTION_NAME: str = "marine_rag"
_VECTOR_DIM: int = 1024


class QdrantStore(BaseVectorStore):
    """
    Vector store backed by Qdrant.

    Args:
        host: Qdrant server hostname.
        port: Qdrant REST API port (default 6333).
        collection_name: Name of the Qdrant collection.
        vector_dim: Dimension of embedding vectors.
        api_key: Optional API key for Qdrant Cloud.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = _COLLECTION_NAME,
        vector_dim: int = _VECTOR_DIM,
        api_key: str = "",
    ):
        self._host = host
        self._port = port
        self._collection_name = collection_name
        self._vector_dim = vector_dim
        self._api_key = api_key
        self._client = None  # Lazy init

    async def initialize(self) -> None:
        """Connect to Qdrant and ensure collection exists."""
        if self._client is not None:
            return
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import (
                Distance, VectorParams, OptimizersConfigDiff,
            )

            self._client = QdrantClient(
                host=self._host, port=self._port, api_key=self._api_key or None,
            )

            # Check if collection exists, create if not
            collections = self._client.get_collections()
            names = [c.name for c in collections.collections]
            if self._collection_name not in names:
                self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=VectorParams(
                        size=self._vector_dim, distance=Distance.COSINE,
                    ),
                    optimizers_config=OptimizersConfigDiff(
                        default_segment_number=2,
                    ),
                )
                logger.info(
                    "Created Qdrant collection: %s (dim=%d, distance=COSINE)",
                    self._collection_name, self._vector_dim,
                )

            collection_info = self._client.get_collection(self._collection_name)
            logger.info(
                "Qdrant connected: %s:%d, collection=%s, vectors=%d",
                self._host, self._port, self._collection_name,
                collection_info.vectors_count,
            )
        except ImportError:
            raise RuntimeError("qdrant-client is not installed. Run: pip install qdrant-client")
        except Exception as exc:
            logger.error("Qdrant init failed: %s", exc)
            raise RuntimeError(f"Qdrant initialization failed: {exc}") from exc

    async def health_check(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.get_collection(self._collection_name)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    async def insert(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> list[str]:
        if self._client is None:
            raise RuntimeError("Qdrant not initialized.")
        if not chunks:
            return []

        from qdrant_client.models import PointStruct

        points = []
        for chunk, emb in zip(chunks, embeddings):
            payload = {
                "text": chunk.text,
                "source_filename": chunk.metadata.source_filename,
                "chunk_type": chunk.chunk_type,
                "position": chunk.position_in_document,
                "language": chunk.metadata.language,
            }
            if chunk.metadata.classification_society:
                payload["classification_society"] = chunk.metadata.classification_society.value if hasattr(chunk.metadata.classification_society, "value") else str(chunk.metadata.classification_society)
            if chunk.metadata.chapter_section:
                payload["chapter_section"] = chunk.metadata.chapter_section
            if chunk.metadata.version_year:
                payload["version_year"] = chunk.metadata.version_year

            points.append(PointStruct(
                id=chunk.chunk_id or str(uuid.uuid4()),
                vector=emb,
                payload=payload,
            ))

        self._client.upsert(
            collection_name=self._collection_name,
            points=points,
        )
        return [p.id for p in points]

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        if self._client is None:
            raise RuntimeError("Qdrant not initialized.")

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(FieldCondition(
                    key=key, match=MatchValue(value=value),
                ))
            if conditions:
                qdrant_filter = Filter(must=conditions)

        results = self._client.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )

        chunks: list[tuple[Chunk, float]] = []
        for hit in results:
            payload = hit.payload or {}
            chunk = self._payload_to_chunk(hit.id, payload)
            chunks.append((chunk, round(hit.score, 4)))

        return chunks

    async def delete(self, doc_id: str) -> int:
        if self._client is None:
            return 0
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        self._client.delete(
            collection_name=self._collection_name,
            points_selector=Filter(
                must=[FieldCondition(
                    key="source_filename", match=MatchValue(value=doc_id),
                )],
            ),
        )
        return 0  # Qdrant doesn't return delete count easily

    async def count(self) -> int:
        if self._client is None:
            return 0
        info = self._client.get_collection(self._collection_name)
        return info.vectors_count

    def _payload_to_chunk(self, chunk_id: str | int, payload: dict) -> Chunk:
        from contracts.document import (
            Chunk, DocumentMetadata, Domain, ClassificationSociety,
        )
        society = None
        if payload.get("classification_society"):
            try:
                society = ClassificationSociety(payload["classification_society"])
            except (ValueError, TypeError):
                pass
        domain = Domain.GENERAL
        if payload.get("domain"):
            try:
                domain = Domain(payload["domain"])
            except (ValueError, TypeError):
                pass
        return Chunk(
            chunk_id=str(chunk_id),
            text=payload.get("text", ""),
            metadata=DocumentMetadata(
                source_filename=payload.get("source_filename", ""),
                domain=domain,
                classification_society=society,
                chapter_section=payload.get("chapter_section"),
                version_year=payload.get("version_year"),
                language=payload.get("language", "en"),
            ),
            chunk_type=payload.get("chunk_type", "clause"),
            position_in_document=payload.get("position", 0),
        )
