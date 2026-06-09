# M2 — Storage Abstraction Layer 模块记忆

> **Purpose**: Record all development sessions, decisions, gotchas, and lessons learned for M2. Read this file before starting ANY new M2 development session.

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | ✅ Complete — 6 backends across 4 interfaces |
| Active Tasks | — |
| First Dev Date | 2026-05-18 |
| Last Session Date | 2026-06-09 |
| Total Sessions | 3 |

---

## 2. Session History

### Session 3 — 2026-06-09: Enterprise/SaaS Backends (PostgreSQL + Elasticsearch + MinIO/S3)

**Outcome**: 3 new backends implemented. 58 passed, 25 skipped.

**New Backends**:
- PostgreSQL RelationalDB (asyncpg driver, pool_pre_ping, pool_recycle, SSL)
- Elasticsearch DocumentIndex (AsyncElasticsearch 8.x, bulk API, term filters, explicit mapping)
- MinIO/S3 FileStore (minio-py, presigned URLs, bucket auto-creation, retry with exponential backoff, timeout control, metadata validation)

**M7 UI Integration**:
- PostgreSQL: 8 config fields (host/port/database/user/password/ssl/pool_size/max_overflow) + Test Connection
- Elasticsearch: 6 config fields (host/index/user/password/shards/replicas) + Test Connection
- MinIO/S3: 6 config fields (endpoint/bucket/access_key/secret_key/secure) + Test Connection

**M8 Test Connection Endpoints**:
- `POST /admin/config/storage/test-postgresql` (TCP + asyncpg SELECT 1)
- `POST /admin/config/storage/test-elasticsearch` (socket + ES cluster health API)
- `POST /admin/config/storage/test-minio` (socket + bucket_exists)

**Commits**: 3 (9f0ca8c, 942f201, 10f98ec, 5b43247)

### Session 2 — 2026-06-07: VectorStore Backend Expansion

**Outcome**: 3 new VectorStore backends (FAISS, Qdrant, Milvus) added.

**Implemented**:
- FAISSStore (embedded, IVF_FLAT/IVF_PQ/HNSW index types)
- QdrantStore (standalone, single Docker container)
- MilvusStore (standalone, gRPC connection)
- Config extensions (FAISSConfig, QdrantConfig, MilvusConfig)

### Session 1 — 2026-05-18/19: Initial Implementation (Personal Mode)

**Outcome**: All 9 sub-tasks completed. 42 tests passing, 0 failures.

**Implemented**:
- Config parser (9 dataclass types, deploy.yaml)
- Factory (4 dispatch functions with type annotations)
- StorageManager (async lifecycle with asyncio.gather + graceful degradation)
- ChromaDB VectorStore (embedded, PersistentClient, cosine distance)
- Meilisearch DocumentIndex (BM25, filter expression builder)
- SQLite RelationalDB (async SQLAlchemy + aiosqlite, WAL mode, no ORM models)
- LocalFS FileStore (async I/O, metadata sidecar, path traversal protection)
- Integration tests (conftest.py, shared fixtures, cross-backend scenarios)

**Commits**: 12 (6bf9fcb through 45754d1)

---

## 3. Key Design Decisions (Module-Internal)

| ID | Date | Decision | Why |
|----|------|----------|-----|
| M2-D01 | 2026-05-18 | Personal-mode backends only (ChromaDB, Meilisearch, SQLite, LocalFS) | Phase 2 goal is end-to-end flow; Enterprise/SaaS backends in Phase 3 |
| M2-D02 | 2026-05-18 | stdlib dataclasses for config (not Pydantic) | Minimize M2 dependencies; config is simple enough |
| M2-D03 | 2026-05-18 | Local imports in _create_* dispatch functions | Missing backend dependency shouldn't block module import |
| M2-D04 | 2026-05-18 | M2 does NOT define ORM models | Models belong to upper modules (M5). M2 provides engine + session only |
| M2-D05 | 2026-05-18 | ChromaDB uses cosine distance (hnsw:space: cosine) | Standard for normalized embeddings (BGE-M3, GTE-Qwen2) |
| M2-D06 | 2026-05-18 | SQLite WAL mode + check_same_thread=False | WAL enables concurrent reads during writes; check_same_thread required for async access |
| M2-D07 | 2026-05-18 | doc_id derived from source_filename (strip .pdf) | ChromaDB/Meilisearch need a stable document identifier for bulk delete |
| M2-D08 | 2026-06-09 | PostgreSQL uses asyncpg (not psycopg3) | 2-3x faster, pure Python, no C extensions to compile |
| M2-D09 | 2026-06-09 | PostgreSQL pool_pre_ping=True + pool_recycle=3600 | Detects silently dropped connections by LB/firewall; prevents memory leaks from long-lived connections |
| M2-D10 | 2026-06-09 | PostgreSQL password via ${PG_PASSWORD} env var injection | Passwords never committed to deploy.yaml |
| M2-D11 | 2026-06-09 | Elasticsearch 8.x AsyncElasticsearch (not sync client) | Consistent with M2's async-everything pattern |
| M2-D12 | 2026-06-09 | Elasticsearch explicit mapping (not dynamic) | Guarantees BM25 similarity on text field, keyword type for filterable fields |
| M2-D13 | 2026-06-09 | MinIO/S3 single implementation serving both | Both use identical S3 API; only endpoint/secure differ |
| M2-D14 | 2026-06-09 | MinIO/S3 _retry_sync with exponential backoff (3 attempts) | Network blips common in cloud; semantic errors (NoSuchKey) not retried |
| M2-D15 | 2026-06-09 | MinIO/S3 asyncio.timeout(30s) on all operations | Prevents hung requests from blocking event loop |
| M2-D16 | 2026-06-09 | MinIO/S3 _validate_metadata() — string-only enforcement | S3 object metadata only supports string keys/values; validates at API boundary for clear errors |

---

## 4. Known Pitfalls & Gotchas

1. **ChromaDB metadata field truncation**: ChromaDB only supports flat scalar metadata. `insert()` flattens `DocumentMetadata` fields; `_reconstruct_metadata()` only restores `source_filename`, `domain`, `language`, and `vessel_types`. Other fields (`classification_society`, `regulation_name`, `version_year`, etc.) are lost in the round-trip. Upper modules writing queries that filter on those fields will get incorrect results. **Fix in Phase 3**: extend the metadata serialization to encode all fields.

2. **Meilisearch filter expression injection**: `_build_meili_filter()` directly interpolates string values into Meilisearch filter expressions. Double-quote characters in filenames or metadata could break the filter syntax. **Task 5 review (MEDIUM)** flagged this for fix before production deployment.

3. **SQLite foreign keys disabled by default**: SQLite requires `PRAGMA foreign_keys = ON` per connection. The current implementation does not set this. Upper modules (M5) defining FK constraints would have silent no-op. **Task 6 review** recommended adding this.

4. **Meilisearch requires separate process**: Unlike ChromaDB/SQLite/LocalFS which are embedded, Meilisearch must be running externally. Tests automatically skip if `MEILISEARCH_URL` is unreachable. In production, Meilisearch should be started alongside the main app via Docker Compose or supervisor.

5. **`doc_id` derivation from filename is fragile**: `source_filename.replace(".pdf", "")` only strips lowercase `.pdf`. Files with `.PDF`, `.docx`, or no extension would produce inconsistent doc_ids.

6. **PostgreSQL/Elasticsearch/MinIO tests auto-skip**: All three require external services. Tests auto-detect availability via TCP socket check and skip with clear error messages if unreachable. One fail-fast test per backend validates connection failure behavior without real service.

7. **MinIO/S3 retry excludes semantic errors**: NoSuchKey and NoSuchBucket propagate immediately (no retry) — only network/connection errors are retried with exponential backoff.

---

## 5. Interface Contract Deviations

> None. All 6 backends satisfy their respective `contracts/storage.py` Protocols (`issubclass` verified).

---

## 6. Performance Notes

| Backend | Operation | Notes |
|---------|-----------|-------|
| ChromaDB | insert/search | HNSW index built incrementally; first search after insert may be slow for large collections |
| Meilisearch | index | `add_documents` is async (fire-and-forget); tests use `asyncio.sleep(0.5)` to wait for indexing |
| SQLite | get_session | WAL mode enables concurrent readers; single writer at a time |
| LocalFS | put/get | Sequential I/O only; no concurrent write optimization needed for Personal mode |
| PostgreSQL | get_session | pool_size=10, max_overflow=20; pool_pre_ping catches dead connections; pool_recycle every 1h |
| Elasticsearch | search | BM25 scoring; term filters on keyword fields for exact metadata matching; explicit mapping prevents type guessing |
| MinIO/S3 | put/get | Exponential-backoff retry (3x, 1s→2s→4s); per-operation 30s timeout; presigned URLs avoid proxying through M8 |

---

## 7. Open Issues

1. **ChromaDB metadata field loss** (see Pitfall #1) — extend serialization in Phase 3
2. **Meilisearch filter injection** (see Pitfall #2) — add value escaping
3. **Missing edge case tests** for Tasks 5 and 6 (reviewer flagged 4 gaps each)
4. **Deploy config integration** — M2's `deploy.yaml` structure needs to be integrated with the project-level `deploy/` config system in Phase 3
5. **Large file upload support** (MinIO/S3) — multipart upload for >100MB files (P2)
6. **Object lifecycle management** (MinIO/S3) — auto-expiry rules for temp files (P2)

---

## 8. Backend Matrix

| Interface | Personal | Enterprise | SaaS |
|-----------|----------|-----------|------|
| VectorStore | ChromaDB / FAISS | Qdrant / Milvus | Qdrant / Milvus |
| RelationalDB | SQLite | SQLite / PostgreSQL | PostgreSQL |
| DocumentIndex | Meilisearch | Meilisearch / Elasticsearch | Elasticsearch |
| FileStore | Local FS | Local FS / MinIO | MinIO / S3 |

---

## 9. Module File Map

```
m2-storage/
  m2_storage/
    __init__.py              -- module entry, exports StorageManager
    config.py                -- deploy.yaml parsing + 12 config dataclasses
    factory.py               -- 4 dispatch functions (6 backends total)
    manager.py               -- StorageManager lifecycle
    vector_store/
      __init__.py            -- exports
      base.py                -- BaseVectorStore
      chromadb_store.py      -- ChromaDB (Personal)
      faiss_store.py         -- FAISS (Lightweight)
      qdrant_store.py        -- Qdrant (Enterprise)
      milvus_store.py        -- Milvus (Enterprise/SaaS)
    relational_db/
      __init__.py            -- exports
      base.py                -- BaseRelationalDB
      sqlite_db.py           -- SQLite (Personal)
      postgresql_db.py       -- PostgreSQL (Enterprise/SaaS)
    document_index/
      __init__.py            -- exports
      base.py                -- BaseDocumentIndex
      meilisearch_index.py   -- Meilisearch (Personal)
      elasticsearch_index.py -- Elasticsearch (SaaS)
    file_store/
      __init__.py            -- exports
      base.py                -- BaseFileStore
      local_fs.py            -- LocalFS (Personal)
      minio_store.py         -- MinIO/S3 (Enterprise/SaaS)
  tests/
    conftest.py              -- shared fixtures
    test_config.py           -- 11 tests
    test_factory.py          -- 10 tests
    test_manager.py          -- 8 tests
    test_chromadb.py         -- 9 tests
    test_meilisearch.py      -- 6 tests (auto-skip)
    test_sqlite.py           -- 5 tests
    test_local_fs.py         -- 9 tests
    test_postgresql.py       -- 5 tests (auto-skip)
    test_elasticsearch.py    -- 7 tests (auto-skip)
    test_minio.py            -- 13 tests (auto-skip)
  pyproject.toml
  requirements.txt
```

### Tasks Completed

| Task | Description | Tests | Status |
|------|-------------|-------|--------|
| 00050-01~09 | Personal mode: config + factory + 4 backends + integration | 42 | ✅ |
| 00050-10~13 | VectorStore expansion: FAISS + Qdrant + Milvus | — | ✅ |
| 00101 | PostgreSQL backend (asyncpg) + M7 UI + M8 endpoint | +5 | ✅ |
| 00102 | Elasticsearch backend (ES 8.x) + M7 UI + M8 endpoint | +7 | ✅ |
| 00103 | MinIO/S3 backend (minio-py) + M7 UI + M8 endpoint | +13 | ✅ |

**Total**: 58 passed, 25 skipped (Meilisearch/PostgreSQL/ES/MinIO require external services).
