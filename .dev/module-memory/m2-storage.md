# M2 — Storage Abstraction Layer 模块记忆

> **Purpose**: Record all development sessions, decisions, gotchas, and lessons learned for M2. Read this file before starting ANY new M2 development session.

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | ✅ PostgreSQL backend added |
| Active Tasks | — |
| First Dev Date | 2026-05-18 |
| Last Session Date | 2026-06-09 |
| Total Sessions | 2 |

---

## 2. Session History

### Session 1 — 2026-05-18/19: Initial Implementation

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

**Spec file**: `.dev/specs/m2-storage-design-2026-05-18.md`
**Plan file**: `.dev/plans/plan-d-m2-storage-2026-05-18.md`

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

---

## 4. Known Pitfalls & Gotchas

1. **ChromaDB metadata field truncation**: ChromaDB only supports flat scalar metadata. `insert()` flattens `DocumentMetadata` fields; `_reconstruct_metadata()` only restores `source_filename`, `domain`, `language`, and `vessel_types`. Other fields (`classification_society`, `regulation_name`, `version_year`, etc.) are lost in the round-trip. Upper modules writing queries that filter on those fields will get incorrect results. **Fix in Phase 3**: extend the metadata serialization to encode all fields.

2. **Meilisearch filter expression injection**: `_build_meili_filter()` directly interpolates string values into Meilisearch filter expressions. Double-quote characters in filenames or metadata could break the filter syntax. **Task 5 review (MEDIUM)** flagged this for fix before production deployment.

3. **SQLite foreign keys disabled by default**: SQLite requires `PRAGMA foreign_keys = ON` per connection. The current implementation does not set this. Upper modules (M5) defining FK constraints would have silent no-op. **Task 6 review** recommended adding this.

4. **Meilisearch requires separate process**: Unlike ChromaDB/SQLite/LocalFS which are embedded, Meilisearch must be running externally. Tests automatically skip if `MEILISEARCH_URL` is unreachable. In production, Meilisearch should be started alongside the main app via Docker Compose or supervisor.

5. **`doc_id` derivation from filename is fragile**: `source_filename.replace(".pdf", "")` only strips lowercase `.pdf`. Files with `.PDF`, `.docx`, or no extension would produce inconsistent doc_ids.

---

## 5. Interface Contract Deviations

> None. All 4 backends satisfy their respective `contracts/storage.py` Protocols (`issubclass` verified).

---

## 6. Performance Notes

| Backend | Operation | Notes |
|---------|-----------|-------|
| ChromaDB | insert/search | HNSW index built incrementally; first search after insert may be slow for large collections |
| Meilisearch | index | `add_documents` is async (fire-and-forget); tests use `asyncio.sleep(0.5)` to wait for indexing |
| SQLite | get_session | WAL mode enables concurrent readers; single writer at a time |
| LocalFS | put/get | Sequential I/O only; no concurrent write optimization needed for Personal mode |

---

## 7. Open Issues

1. **ChromaDB metadata field loss** (see Pitfall #1) — extend serialization in Phase 3
2. **Meilisearch filter injection** (see Pitfall #2) — add value escaping
3. **Missing edge case tests** for Tasks 5 and 6 (reviewer flagged 4 gaps each)
4. **Enterprise/SaaS backends** deferred to Phase 3 per D013 (Qdrant, Milvus, PostgreSQL, MariaDB, MinIO, S3, Elasticsearch)
5. **Deploy config integration** — M2's `deploy.yaml` structure needs to be integrated with the project-level `deploy/` config system in Phase 3
