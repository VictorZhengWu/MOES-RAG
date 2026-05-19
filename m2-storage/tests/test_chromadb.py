"""
Tests for ChromaDBStore -- the Personal-mode vector store backend.

WHY: ChromaDB is the primary vector store for all Personal deployments.
It must correctly implement insert, search with metadata filtering,
delete by doc_id, and count -- these are the operations that M3 (Retrieval)
and M5 (QA Engine) depend on for every user query.
"""

import uuid

import pytest
import pytest_asyncio

from contracts.document import Chunk, DocumentMetadata, Domain
from contracts.storage import VectorStoreProtocol

from m2_storage.config import ChromaDBConfig
from m2_storage.vector_store.chromadb_store import ChromaDBStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(text: str, doc_id: str = "doc-1", domain: str = "structure",
                chunk_index: int = 0) -> Chunk:
    """Create a minimal Chunk for testing."""
    return Chunk(
        chunk_id=f"{doc_id}-chunk-{chunk_index}",
        text=text,
        metadata=DocumentMetadata(
            source_filename=f"{doc_id}.pdf",
            domain=Domain(domain),
        ),
        chunk_type="clause",
        position_in_document=chunk_index,
    )


def _make_embedding(dim: int = 8, seed: int = 0) -> list[float]:
    """Return a deterministic embedding vector that varies with seed.

    WHY seed-based: we need embeddings that are distinct across chunks
    so that vector search can distinguish them. Without distinct embeddings,
    all chunks are equally distant and ordering is arbitrary.
    """
    return [(0.5 + i * 0.1 + seed * 0.05) % 1.0 for i in range(dim)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def chroma_config(tmp_path):
    """Create a ChromaDBConfig pointing at a temp directory."""
    persist_dir = tmp_path / "chromadb"
    persist_dir.mkdir()
    return ChromaDBConfig(
        persist_dir=str(persist_dir),
        collection_name=f"test_{uuid.uuid4().hex[:8]}",
    )


@pytest_asyncio.fixture
async def chroma_store(chroma_config):
    """Return an initialized ChromaDBStore, cleaned up after test."""
    store = ChromaDBStore(chroma_config)
    await store.initialize()
    yield store
    await store.close()


# ---------------------------------------------------------------------------
# Test 1: Protocol compliance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_protocol_compliance(chroma_store):
    """ChromaDBStore must satisfy VectorStoreProtocol."""
    assert isinstance(chroma_store, VectorStoreProtocol)


# ---------------------------------------------------------------------------
# Test 2: insert and search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_and_search(chroma_store):
    """Insert chunks then search -- must return correct chunks ranked by score."""
    c1 = _make_chunk("Welding procedure for bulkheads", chunk_index=0)
    c2 = _make_chunk("Painting requirements for hull", chunk_index=1)
    c3 = _make_chunk("Corrosion protection coating", chunk_index=2)

    # Use distinct seeds so embeddings are distinguishable.
    # emb1 (seed=0) is the query anchor -- c1 should be top result.
    emb1 = _make_embedding(seed=0)
    emb2 = _make_embedding(seed=7)
    emb3 = _make_embedding(seed=9)

    ids = await chroma_store.insert([c1, c2, c3], [emb1, emb2, emb3])
    assert len(ids) == 3

    # Search with emb1 -- c1 (inserted with emb1) should be top result
    results = await chroma_store.search(emb1, top_k=2)
    assert len(results) == 2
    assert isinstance(results[0][0], Chunk)
    assert isinstance(results[0][1], float)
    assert results[0][0].text == "Welding procedure for bulkheads"


# ---------------------------------------------------------------------------
# Test 3: search with metadata filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_with_filter(chroma_store):
    """Search with a domain filter must return only matching chunks."""
    c1 = _make_chunk("Structural steel grades", domain="structure", chunk_index=0)
    c2 = _make_chunk("Pump specifications", domain="machinery", chunk_index=1)
    emb = _make_embedding()

    await chroma_store.insert([c1, c2], [emb, emb])

    results = await chroma_store.search(
        emb, top_k=5, filters={"domain": "machinery"}
    )
    assert len(results) == 1
    assert results[0][0].text == "Pump specifications"


# ---------------------------------------------------------------------------
# Test 4: delete by doc_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete(chroma_store):
    """Deleting by doc_id must remove all chunks for that document."""
    c1 = _make_chunk("Doc A content", doc_id="doc-a", chunk_index=0)
    c2 = _make_chunk("Doc B content", doc_id="doc-b", chunk_index=0)
    emb = _make_embedding()

    await chroma_store.insert([c1, c2], [emb, emb])
    assert await chroma_store.count() == 2

    deleted = await chroma_store.delete("doc-a")
    assert deleted >= 1
    assert await chroma_store.count() == 1


# ---------------------------------------------------------------------------
# Test 5: search empty collection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_empty(chroma_store):
    """Searching an empty collection must return empty list, not error."""
    results = await chroma_store.search(_make_embedding(), top_k=10)
    assert results == []


# ---------------------------------------------------------------------------
# Test 6: health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check(chroma_store):
    """Initialized store must report healthy."""
    assert await chroma_store.health_check() is True
