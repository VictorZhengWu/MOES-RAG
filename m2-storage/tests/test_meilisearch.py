# -*- coding: utf-8 -*-
"""
Tests for MeilisearchIndex -- the Personal-mode full-text search backend.

WHY: Meilisearch provides BM25-based keyword search that complements
dense vector retrieval. For regulation clause lookups (e.g. "DNV Pt.4
Ch.3 §5"), keyword search is more precise than embeddings.

NOTE: Tests require a running Meilisearch instance. If MEILISEARCH_URL
is not set or the instance is unreachable, tests are skipped.
"""

import os
import uuid
import urllib.request

import pytest
import pytest_asyncio

from contracts.document import Chunk, DocumentMetadata, Domain
from contracts.storage import DocumentIndexProtocol

from m2_storage.config import MeilisearchConfig
from m2_storage.document_index.meilisearch_index import MeilisearchIndex


# ---------------------------------------------------------------------------
# Meilisearch availability check
# ---------------------------------------------------------------------------

MEILI_HOST = os.environ.get("MEILISEARCH_URL", "http://127.0.0.1:7700")

_meili_available = None


def _check_meilisearch():
    """Check if Meilisearch is reachable. Cache the result.

    WHY cached: multiple fixtures and tests call this -- we don't
    want to hit the health endpoint redundantly on every call.
    """
    global _meili_available
    if _meili_available is not None:
        return _meili_available
    try:
        req = urllib.request.Request(f"{MEILI_HOST}/health")
        urllib.request.urlopen(req, timeout=2)
        _meili_available = True
    except Exception:
        _meili_available = False
    return _meili_available


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(text: str, doc_id: str = "doc-1", domain: str = "structure",
                chunk_index: int = 0) -> Chunk:
    """Create a minimal Chunk for testing.

    WHY: reduces boilerplate in test cases -- each test only specifies
    the fields that matter for that scenario.
    """
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def meili_config():
    """Create a MeilisearchConfig with a unique test index name.

    WHY unique name: prevents test-index collisions when multiple
    test runs execute concurrently or a previous run left stale data.
    """
    return MeilisearchConfig(
        host=MEILI_HOST,
        api_key="",
        index_name=f"test_m2_{uuid.uuid4().hex[:8]}",
    )


@pytest_asyncio.fixture
async def meili_index(meili_config):
    """Return an initialized MeilisearchIndex, skip if unavailable.

    WHY pytest_asyncio.fixture: supports async yield for setup/teardown
    (initialize before test, delete index after test).
    """
    if not _check_meilisearch():
        pytest.skip("Meilisearch not available at " + MEILI_HOST)
    idx = MeilisearchIndex(meili_config)
    await idx.initialize()
    yield idx
    # Cleanup: delete the test index so subsequent runs start fresh
    try:
        idx._client.delete_index(meili_config.index_name)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test 1: Protocol compliance
# ---------------------------------------------------------------------------

def test_protocol_compliance(meili_index):
    """MeilisearchIndex must satisfy DocumentIndexProtocol.

    WHY: type check -- upper modules depend on the Protocol, not the
    concrete class. This test catches accidental signature drift.
    """
    assert isinstance(meili_index, DocumentIndexProtocol)


# ---------------------------------------------------------------------------
# Test 2: index and search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_index_and_search(meili_index):
    """Index chunks then search -- must return relevant results.

    WHY: this is the primary use case -- M3 (Retrieval) indexes chunks
    and then searches them. The core contract is that search returns
    the chunks that were indexed.
    """
    c1 = _make_chunk("DNV Pt.4 Ch.3 welding procedure specification",
                      doc_id="doc-1", chunk_index=0)
    c2 = _make_chunk("ABS Pt.5B hull structural requirements",
                      doc_id="doc-2", chunk_index=0)

    await meili_index.index([c1, c2])
    # Meilisearch indexes are eventually consistent -- brief wait
    import asyncio
    await asyncio.sleep(0.5)

    results = await meili_index.search("welding procedure", top_k=5)
    assert len(results) >= 1
    assert isinstance(results[0][0], Chunk)
    assert "welding" in results[0][0].text.lower()


# ---------------------------------------------------------------------------
# Test 3: search with filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_with_filter(meili_index):
    """Search with a metadata filter must only return matching chunks.

    WHY: M3 (Retrieval) filters search results by domain. The
    filter-syntax conversion (flat dict -> Meilisearch SQL-like
    expression) must be correct.
    """
    c1 = _make_chunk("welding requirements", doc_id="doc-a", domain="structure")
    c2 = _make_chunk("welding inspection", doc_id="doc-b", domain="machinery")

    await meili_index.index([c1, c2])
    import asyncio
    await asyncio.sleep(0.5)

    results = await meili_index.search(
        "welding", top_k=5, filters={"domain": "machinery"}
    )
    assert len(results) == 1
    assert results[0][0].metadata.source_filename == "doc-b.pdf"


# ---------------------------------------------------------------------------
# Test 4: delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete(meili_index):
    """Deleting by doc_id must remove that document's chunks from search.

    WHY: M1 (Doc Parsing) re-parses and re-indexes documents. The old
    chunks must be deleted first to avoid stale results.
    """
    c1 = _make_chunk("content A", doc_id="keep")
    c2 = _make_chunk("content B", doc_id="remove")

    await meili_index.index([c1, c2])
    import asyncio
    await asyncio.sleep(0.5)

    await meili_index.delete("remove")

    results = await meili_index.search("content", top_k=10)
    assert len(results) == 1
    assert results[0][0].text == "content A"


# ---------------------------------------------------------------------------
# Test 5: search empty index
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_empty(meili_index):
    """Searching an empty index must return an empty list.

    WHY: M3 (Retrieval) must handle the case where no documents have
    been indexed yet. An exception here would break the query pipeline.
    """
    results = await meili_index.search("anything", top_k=10)
    assert results == []


# ---------------------------------------------------------------------------
# Test 6: health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check(meili_index):
    """Initialized index must report healthy.

    WHY: M2 (Storage) exposes a single /health endpoint that aggregates
    health checks from all 4 backends. Each backend's health_check()
    must work correctly.
    """
    assert await meili_index.health_check() is True
