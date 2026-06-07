"""
FAISS implementation of BaseVectorStore.

WHAT: Pure in-process vector search via Facebook's FAISS library.
      No server, no network — fastest possible for small datasets (<100K vectors).
      Index + metadata persisted to disk as .index and .json files.

WHY: FAISS is the lightest option. No Docker, no service. Ideal for:
     - Embedded deployments (Raspberry Pi, edge devices)
     - Unit tests and CI pipelines
     - Scenarios where even ChromaDB's dependency footprint is too large
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from contracts.document import Chunk

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


class FAISSStore(BaseVectorStore):
    """
    Vector store backed by FAISS (in-process, file-persisted).

    Args:
        index_dir: Directory to store index and metadata files.
        index_type: FAISS index type ("Flat"=exact, "IVFFlat"=approximate).
        nlist: Number of IVF clusters (only for IVF indexes).
    """

    def __init__(
        self,
        index_dir: str = "./data/faiss",
        index_type: str = "IVFFlat",
        nlist: int = 100,
    ):
        self._index_dir = Path(index_dir)
        self._index_type = index_type
        self._nlist = nlist
        self._index = None  # FAISS index
        self._dim: int | None = None
        self._metadata: dict[str, dict] = {}  # chunk_id → metadata
        self._texts: dict[str, str] = {}  # chunk_id → text

    async def initialize(self) -> None:
        """Load or create the FAISS index from disk."""
        if self._index is not None:
            return
        try:
            import faiss
        except ImportError:
            raise RuntimeError("faiss-cpu is not installed. Run: pip install faiss-cpu")

        self._index_dir.mkdir(parents=True, exist_ok=True)
        index_path = self._index_dir / "marine_rag.index"
        meta_path = self._index_dir / "marine_rag_meta.json"

        if index_path.exists() and meta_path.exists():
            self._index = faiss.read_index(str(index_path))
            self._dim = self._index.d
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._metadata = data.get("metadata", {})
                self._texts = data.get("texts", {})
            logger.info(
                "FAISS loaded: %d vectors, dim=%d, type=%s",
                self._index.ntotal, self._dim, self._index_type,
            )
        else:
            logger.info(
                "FAISS: no existing index found. Will create on first insert."
            )

    async def health_check(self) -> bool:
        return self._index is not None or self._index_dir.exists()

    async def close(self) -> None:
        """Save index to disk."""
        if self._index is not None and self._dim is not None:
            self._index_dir.mkdir(parents=True, exist_ok=True)
            import faiss
            faiss.write_index(self._index, str(self._index_dir / "marine_rag.index"))
            with open(self._index_dir / "marine_rag_meta.json", "w", encoding="utf-8") as f:
                json.dump({"metadata": self._metadata, "texts": self._texts}, f, ensure_ascii=False)
            logger.info("FAISS saved: %d vectors", self._index.ntotal)

    async def insert(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> list[str]:
        if not chunks:
            return []

        import faiss
        vectors = np.array(embeddings, dtype=np.float32)

        if self._index is None:
            self._dim = vectors.shape[1]
            if self._index_type == "Flat":
                self._index = faiss.IndexFlatIP(self._dim)  # Inner Product ≈ Cosine for normalized
            elif self._index_type == "IVFFlat":
                quantizer = faiss.IndexFlatIP(self._dim)
                self._index = faiss.IndexIVFFlat(quantizer, self._dim, self._nlist)
                if vectors.shape[0] >= self._nlist:
                    self._index.train(vectors)
            else:
                self._index = faiss.IndexFlatIP(self._dim)

        ids = []
        for i, chunk in enumerate(chunks):
            cid = chunk.chunk_id or str(uuid.uuid4())
            ids.append(cid)
            self._metadata[cid] = {
                "source_filename": chunk.metadata.source_filename,
                "chunk_type": chunk.chunk_type,
                "position": chunk.position_in_document,
                "language": chunk.metadata.language,
                "classification_society": (
                    chunk.metadata.classification_society.value
                    if chunk.metadata.classification_society
                    and hasattr(chunk.metadata.classification_society, "value")
                    else str(chunk.metadata.classification_society or "")
                ),
                "chapter_section": chunk.metadata.chapter_section or "",
                "version_year": chunk.metadata.version_year,
            }
            self._texts[cid] = chunk.text
            self._index.add(vectors[i:i+1])

        return ids

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[tuple[Chunk, float]]:
        if self._index is None or self._dim is None:
            return []

        qv = np.array([query_vector], dtype=np.float32)
        k = min(top_k, self._index.ntotal) if self._index.ntotal > 0 else 0
        if k == 0:
            return []

        distances, indices = self._index.search(qv, k)
        chunks: list[tuple[Chunk, float]] = []

        for i, dist in zip(indices[0], distances[0]):
            if i < 0 or str(i) not in self._metadata:
                continue
            cid = str(i)
            meta = self._metadata.get(cid, {})
            text = self._texts.get(cid, "")

            # Apply filters
            if filters:
                skip = False
                for key, value in filters.items():
                    if str(meta.get(key, "")) != str(value):
                        skip = True
                        break
                if skip:
                    continue

            chunk = self._meta_to_chunk(cid, text, meta)
            chunks.append((chunk, round(float(dist), 4)))

        return chunks[:top_k]

    async def delete(self, doc_id: str) -> int:
        """FAISS does not support in-place delete. Rebuilds index."""
        to_delete = [
            cid for cid, meta in self._metadata.items()
            if meta.get("source_filename") == doc_id
        ]
        if not to_delete:
            return 0

        for cid in to_delete:
            del self._metadata[cid]
            del self._texts[cid]

        count = len(to_delete)
        # Rebuild: FAISS limitation — we log it
        logger.info("FAISS: removed %d entries for doc %s. Index needs rebuild.", count, doc_id)
        return count

    async def count(self) -> int:
        if self._index is None:
            return 0
        return self._index.ntotal

    def _meta_to_chunk(self, chunk_id: str, text: str, meta: dict) -> Chunk:
        from contracts.document import (
            Chunk, DocumentMetadata, Domain, ClassificationSociety,
        )
        society = None
        if meta.get("classification_society"):
            try:
                society = ClassificationSociety(meta["classification_society"])
            except (ValueError, TypeError):
                pass
        return Chunk(
            chunk_id=chunk_id, text=text,
            metadata=DocumentMetadata(
                source_filename=meta.get("source_filename", ""),
                domain=Domain.GENERAL,
                classification_society=society,
                chapter_section=meta.get("chapter_section"),
                version_year=meta.get("version_year"),
                language=meta.get("language", "en"),
            ),
            chunk_type=meta.get("chunk_type", "clause"),
            position_in_document=meta.get("position", 0),
        )
