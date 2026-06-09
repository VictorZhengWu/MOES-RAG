"""
Tests for ElasticsearchIndex -- the SaaS distributed search backend.

WHAT: Verifies ElasticsearchIndex satisfies DocumentIndexProtocol,
      provides working index/search/delete operations, and reports
      health correctly.

REQUIREMENTS:
    - Elasticsearch 8.x server (local, Docker, or remote)
    - Defaults: http://localhost:9200, no auth
    - Override via: ES_HOST env var

    # Docker (quickest):
    docker run -d --name es-test -p 9200:9200 \
      -e "discovery.type=single-node" \
      -e "xpack.security.enabled=false" \
      elasticsearch:8.15.3

    # No ES available: tests auto-skip
"""

import asyncio
import os
import uuid

import pytest
import pytest_asyncio

from contracts.document import Chunk, DocumentMetadata, Domain
from contracts.storage import DocumentIndexProtocol

from m2_storage.config import ElasticsearchConfig
from m2_storage.document_index.elasticsearch_index import ElasticsearchIndex


# ---------------------------------------------------------------------------
# Auto-detect Elasticsearch availability
# ---------------------------------------------------------------------------

def _es_is_available() -> bool:
    """Fast TCP check to see if Elasticsearch is reachable.

    WHY: Tests auto-skip if no ES is available — no need to install
         Elasticsearch just to run M2 tests locally.
    """
    import socket
    host = os.environ.get("ES_HOST", "http://localhost:9200")
    # Parse host:port from URL
    url = host.replace("http://", "").replace("https://", "")
    if ":" in url:
        h, p = url.split(":")
        port = int(p)
    else:
        h, port = url, 9200
    try:
        sock = socket.create_connection((h, port), timeout=1.5)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


ES_AVAILABLE = _es_is_available()

requires_es = pytest.mark.skipif(
    not ES_AVAILABLE,
    reason="Elasticsearch not available. Start with: "
           "docker run -d --name es-test -p 9200:9200 "
           "-e 'discovery.type=single-node' "
           "-e 'xpack.security.enabled=false' "
           "elasticsearch:8.15.3"
)


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


def _es_config() -> ElasticsearchConfig:
    """Build config from environment or defaults."""
    return ElasticsearchConfig(
        host=os.environ.get("ES_HOST", "http://localhost:9200"),
        index_name=f"test_m2_{uuid.uuid4().hex[:8]}",
        user=os.environ.get("ES_USER", ""),
        password=os.environ.get("ES_PASSWORD", ""),
        num_shards=1,
        num_replicas=0,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def es_index():
    """Return an initialized ElasticsearchIndex, cleaned up after test.

    WHY: Each test gets its own unique index name to prevent cross-test
         contamination. Index is deleted after the test completes.
    """
    if not ES_AVAILABLE:
        pytest.skip("Elasticsearch not available")
    config = _es_config()
    idx = ElasticsearchIndex(config)
    await idx.initialize()
    yield idx
    # Cleanup: delete the test index
    try:
        if idx._client:
            await idx._client.indices.delete(index=config.index_name)
            await idx.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test 1: Protocol compliance
# ---------------------------------------------------------------------------

@requires_es
def test_protocol_compliance(es_index):
    """ElasticsearchIndex must satisfy DocumentIndexProtocol.

    WHY: Upper modules depend on the Protocol, not the concrete class.
         This test catches accidental signature drift between
         MeilisearchIndex and ElasticsearchIndex.
    """
    assert isinstance(es_index, DocumentIndexProtocol), (
        "ElasticsearchIndex must satisfy DocumentIndexProtocol"
    )


# ---------------------------------------------------------------------------
# Test 2: Index and search
# ---------------------------------------------------------------------------

@requires_es
@pytest.mark.asyncio
async def test_index_and_search(es_index):
    """Index chunks then search — must return relevant results.

    WHY: This is the primary use case. M3 indexes chunks and then
         searches them. The core contract is that search returns
         the chunks that were indexed.
    """
    c1 = _make_chunk("DNV Pt.4 Ch.3 welding procedure specification",
                      doc_id="doc-1", chunk_index=0)
    c2 = _make_chunk("ABS Pt.5B hull structural requirements",
                      doc_id="doc-2", chunk_index=0)

    await es_index.index([c1, c2])
    # ES is near-real-time: refresh makes docs immediately searchable
    if es_index._client:
        await es_index._client.indices.refresh(index=es_index._config.index_name)

    results = await es_index.search("welding procedure", top_k=5)
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"
    assert isinstance(results[0][0], Chunk)
    assert "welding" in results[0][0].text.lower()


# ---------------------------------------------------------------------------
# Test 3: Search with filter
# ---------------------------------------------------------------------------

@requires_es
@pytest.mark.asyncio
async def test_search_with_filter(es_index):
    """Search with a metadata filter must only return matching chunks.

    WHY: M3 filters search results by domain. The filter conversion
         (flat dict -> ES term query) must be correct.
    """
    c1 = _make_chunk("welding requirements", doc_id="doc-a", domain="structure")
    c2 = _make_chunk("welding inspection", doc_id="doc-b", domain="machinery")

    await es_index.index([c1, c2])
    if es_index._client:
        await es_index._client.indices.refresh(index=es_index._config.index_name)

    results = await es_index.search(
        "welding", top_k=5, filters={"domain": "machinery"}
    )
    assert len(results) == 1
    assert results[0][0].metadata.source_filename == "doc-b.pdf"


# ---------------------------------------------------------------------------
# Test 4: Delete
# ---------------------------------------------------------------------------

@requires_es
@pytest.mark.asyncio
async def test_delete(es_index):
    """Deleting by doc_id must remove that document's chunks.

    WHY: M1 re-parses and re-indexes documents. Old chunks must be
         deleted first to avoid stale results.
    """
    c1 = _make_chunk("content A", doc_id="keep")
    c2 = _make_chunk("content B", doc_id="remove")

    await es_index.index([c1, c2])
    if es_index._client:
        await es_index._client.indices.refresh(index=es_index._config.index_name)

    await es_index.delete("remove")

    results = await es_index.search("content", top_k=10)
    assert len(results) == 1
    assert results[0][0].text == "content A"


# ---------------------------------------------------------------------------
# Test 5: Search empty index
# ---------------------------------------------------------------------------

@requires_es
@pytest.mark.asyncio
async def test_search_empty(es_index):
    """Searching an empty index must return an empty list, not raise.

    WHY: M3 must handle the case where no documents have been indexed
         yet. An exception here would break the query pipeline.
    """
    results = await es_index.search("anything", top_k=10)
    assert results == []


# ---------------------------------------------------------------------------
# Test 6: Health check
# ---------------------------------------------------------------------------

@requires_es
@pytest.mark.asyncio
async def test_health_check(es_index):
    """Initialized index must report healthy.

    WHY: M2 aggregates health checks from all 4 backends. Each
         backend's health_check() must work correctly.
    """
    assert await es_index.health_check() is True


# ---------------------------------------------------------------------------
# Test 7: Connection failure (no ES needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connection_failure_graceful():
    """Connecting to an unreachable host must raise during initialize().

    WHY: Silent failures at startup lead to runtime errors much later.
         Fast-fail at initialize() gives operators clear feedback about
         misconfiguration.
    """
    config = ElasticsearchConfig(
        host="http://255.255.255.255:9200",  # Unreachable
        index_name="test",
        request_timeout=2,
    )
    idx = ElasticsearchIndex(config)

    with pytest.raises(Exception):
        async with asyncio.timeout(8):
            await idx.initialize()
