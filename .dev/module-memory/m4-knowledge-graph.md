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

## 7. Open Issues

> *No open issues yet.*
