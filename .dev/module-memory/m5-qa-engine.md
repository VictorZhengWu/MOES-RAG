# M5 — RAG QA Engine 模块记忆

> **Purpose**: Record all development sessions, decisions, gotchas, and lessons learned for M5. Read this file before starting ANY new M5 development session.

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | 🔄 In Development |
| Active Tasks | 00090-02, 00090-04, 00090-05 |
| First Dev Date | 2026-06-03 |
| Last Session Date | 2026-06-03 |
| Total Sessions | 3 |

---

## 2. Session History

### Session 3 — 2026-06-03: Task 00090-04 (Citation Builder + Token Budget)

**Tasks completed**: 00090-04
**Key decisions**:
- `allocate_budget()` skips dynamic adjustment when query is empty (empty query → factor=0.5 would incorrectly halve retrieval budget)
- `estimate_tokens()` uses len(text) // 4 heuristic (min 1)
- Citations deduplicate by (source_filename, regulation_name) key
- `attach_citations()` filters to only citations referenced in answer text via [N] markers

**Gotchas**:
- setuptools editable install for `contracts/` package only maps sub-packages (like `tests`) via the finder; the top-level `contracts` package itself was NOT mapped. Workaround: run tests from workspace root where `contracts/` is a visible directory

### Session 2 — 2026-06-03: Task 00090-03 (Prompt Manager)

**Tasks completed**: 00090-03

### Session 1 — 2026-06-03: Task 00090-01 + 00090-02 (Skeleton + LLM Client)

**Tasks completed**: 00090-01, 00090-02

---

## 3. Key Design Decisions (Module-Internal)

> *No decisions recorded yet.*

---

## 4. Known Pitfalls & Gotchas

> *No pitfalls recorded yet.*

---

## 5. Interface Contract Deviations

> *Record any cases where the actual implementation differs from contracts/qa_engine.py specifications.*

---

## 6. Performance Notes

> *End-to-end answer latency, Self-RAG iteration counts, token usage per query.*

---

## 7. Open Issues

> *Unresolved problems.*
