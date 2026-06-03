# M4 — Knowledge Graph Engine 模块记忆

> **Purpose**: Record all development sessions, decisions, gotchas, and lessons learned for M4. Read this file before starting ANY new M4 development session.

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | 🔄 In Development |
| Active Tasks | 00080-02 (rule_extractor) |
| First Dev Date | 2026-06-03 |
| Last Session Date | 2026-06-03 |
| Total Sessions | 1 |

---

## 2. Session History

### Session 1 — 2026-06-03

**Completed**:
- **00080-01**: Project skeleton + configuration (pyproject.toml, config.py, tier.py)
  - 10/10 tests passing
  - LLMBackend dataclass (provider, model, api_key, base_url)
  - ExtractionConfig dataclass (llm, max_chunks_per_doc, max_tokens_per_batch, max_concurrent, fallback_to_rules)
  - UserTier dataclass + USER_TIERS dict (basic, pro, enterprise)
  - TDD workflow: red (fail) → green (pass) → commit

**File inventory**:
- `m4-knowledge-graph/pyproject.toml` — build config, dependencies, pytest settings
- `m4-knowledge-graph/requirements.txt` — pinned dev dependencies
- `m4-knowledge-graph/m4_kg/__init__.py` — package entry
- `m4-knowledge-graph/m4_kg/core/__init__.py` — core subpackage
- `m4-knowledge-graph/m4_kg/core/config.py` — LLMBackend + ExtractionConfig
- `m4-knowledge-graph/m4_kg/core/tier.py` — UserTier + USER_TIERS
- `m4-knowledge-graph/tests/__init__.py` — test package
- `m4-knowledge-graph/tests/test_config.py` — 5 tests
- `m4-knowledge-graph/tests/test_tier.py` — 5 tests

---

## 3. Key Design Decisions (Module-Internal)

1. **Package root is `m4_kg/` (not `src/m4_kg/`)** — follows design spec directory structure exactly.
2. **User tiers are module-level dict** — `USER_TIERS` is a module constant, not a class method, for O(1) lookup and singleton semantics.
3. **`ExtractionConfig.llm` is Optional** — When `None`, only rule-based extraction runs (no LLM dependency). Enables offline/lightweight mode.
4. **`fallback_to_rules` flag** — Controls graceful degradation behavior when LLM calls fail. `True` by default (safe), can be set to `False` for strict LLM-only mode.

---

## 4. Known Pitfalls & Gotchas

> *No pitfalls recorded yet.*

---

## 5. Interface Contract Deviations

> *No deviations recorded yet.*

---

## 6. Performance Notes

> *Graph query latency, cross-reference accuracy, entity extraction recall.*

---

### Session 2 — 2026-06-03 (00080-06)

**Completed**:
- **00080-06**: BFS graph traversal (traversal.py)
  - 3 tests: single_hop, multi_hop_with_depth_limit, empty_seeds
  - Added `query_entities_by_ids()` to KuzuStore for efficient batch ID lookups
  - bfs_traverse: outgoing BFS with depth limit, relation_type filter, max_entities cap
  - TDD workflow: tests written before implementation

**File inventory**:
- `m4-knowledge-graph/m4_kg/graph/traversal.py` — bfs_traverse function
- `m4-knowledge-graph/tests/test_traversal.py` — 3 test cases
- `m4-knowledge-graph/m4_kg/graph/kuzu_store.py` — added query_entities_by_ids method

---

## 3. Key Design Decisions (Module-Internal)

1. **Package root is `m4_kg/` (not `src/m4_kg/`)** — follows design spec directory structure exactly.
2. **User tiers are module-level dict** — `USER_TIERS` is a module constant, not a class method, for O(1) lookup and singleton semantics.
3. **`ExtractionConfig.llm` is Optional** — When `None`, only rule-based extraction runs (no LLM dependency). Enables offline/lightweight mode.
4. **`fallback_to_rules` flag** — Controls graceful degradation behavior when LLM calls fail. `True` by default (safe), can be set to `False` for strict LLM-only mode.
5. **BFS outgoing-only traversal** — `bfs_traverse` only follows outgoing edges (source->target). This matches the natural direction of maritime regulation relationships (clause A references clause B, steel grade X requires parameter Y). Bidirectional traversal would be an enhancement if needed later.
6. **Batch ID lookup via `query_entities_by_ids`** — Added to KuzuStore to avoid O(N) individual entity queries during traversal. Uses Kuzu's native `IN` operator for efficient batch retrieval.

---

## 4. Known Pitfalls & Gotchas

> *No pitfalls recorded yet.*

---

## 5. Interface Contract Deviations

> *No deviations recorded yet.*

---

## 6. Performance Notes

- `bfs_traverse` makes at most `depth + 1` database queries per traversal call (1 for seeds + 1 per hop for relations + 1 per hop for target entities). Each query is O(N) where N = entities in that hop.
- `query_entities_by_ids` uses a single `IN` query regardless of batch size, making it O(1) round trips.

---

## 7. Open Issues

- 00080-05 (KuzuStore) test records not yet written — needs to be created before marking 00080-06 complete.
- Test execution pending — user must run `python -m pytest m4-knowledge-graph/tests/test_traversal.py -v` to verify.
