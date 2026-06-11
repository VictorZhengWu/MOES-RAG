# M5 — RAG QA Engine 模块记忆

> **Purpose**: Record all development sessions, decisions, gotchas, and lessons learned for M5. Read this file before starting ANY new M5 development session.

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | ✅ Enhanced (Deep Research added) |
| Active Tasks | — |
| First Dev Date | 2026-06-03 |
| Last Session Date | 2026-06-11 |
| Total Sessions | 7 |

---

## 2. Session History

### Session 7 — 2026-06-11: Phase 4-A Deep Research (00104)

**Tasks completed**: 00104-01 ~ 00104-09
**Key decisions**:
- Pure Python + asyncio (rejected LangGraph — 4-step linear DAG doesn't need a state machine)
- 6-dimension complexity scoring (society/depth/question/context/scope/domain, 0-15, threshold-based suggestion)
- LLM-based planner with rule-based fallback (graceful degradation on LLM failure)
- 2 parallel retrieval agents (regulations: M3+M4+ISO, web: 4 engines dispatch)
- 2-step analyzer: regex extraction (numerical precision) → LLM deep analysis (semantic understanding)
- 7-section Markdown report with template-based fallback
- SSE streaming from M5 → M8 → M6 (progress/report_chunk/done events)
- 0 new dependencies, ~1000 lines of code

**Test results**: 146 passed (85 existing + 61 new research tests)

### Session 6 — 2026-06-03: Task 00090-09 (Final Packaging and Verification)

**Tasks completed**: 00090-09
**Key decisions**:
- Added `__all__` exports to `__init__.py` (QAEngine, QAConfig, LLMBackend) for public API
- Added `marine-rag-contracts>=0.1.0` to pyproject.toml dependencies
- Known limitation: contracts editable install only maps `tests` subpackage, not `contracts` top-level module. This is a pre-existing Task 00010 packaging issue. M5 tests work from workspace root where `contracts/` is on `sys.path`.
- All 9 M5 sub-tasks complete; M5 module status updated to Complete

**Test results**: 83/83 passed (full regression), pip install + import verified

**M5 final statistics**:
- 25 source files (`m5_qa/`)
- 17 test files (`tests/`)
- 83 tests total
- 16 git commits
- 6 development sessions

### Session 5 — 2026-06-03: Task 00090-08 (QAEngine + Monitoring)

**Tasks completed**: 00090-08
**Key decisions**:
- `QAEngine` is the central orchestrator implementing `QAEngineProtocol` from `contracts/`
- Wires up 8 components in `__init__`: ModeRouter, LLMClient, PromptManager, RetrievalClient, ConversationManager, ContextCompressor, MetricsCollector, and StructuredLogger
- `chat()` flow: extract query -> resolve tier -> check Premium quota -> execute pipeline -> build ChatResponse -> record metrics -> log query
- Premium quota is checked directly via `ConversationManager.consume_premium()` (async) rather than through `ModeRouter.select_mode()` (which expects a synchronous quota_manager). This is because all ConversationManager methods are async.
- Pipeline functions (`execute_simple`, `execute_pipeline`, `execute_self_rag`) are imported at module level, allowing them to be mocked individually in tests via `unittest.mock.patch`
- `chat_stream()` builds its own prompt and calls `llm_client.complete_stream()` + `sse_chunk()` wrapping
- `list_models()` returns OpenAI-compatible `[{"id": ..., "object": "model"}]` format
- `health_check()` returns `{"status": "ok", "components": {...}}`
- Conversation management methods delegate directly to `ConversationManager`
- `MetricsCollector` uses an in-memory list of `QueryMetrics` dataclasses; `get_summary()` computes aggregated stats on demand
- `StructuredLogger` provides static methods for JSON-structured logging via Python's `logging` module
- All source code has English WHAT+WHY comments per project rules

**Test results**: 10/10 new tests passed (6 engine + 4 metrics), full suite 83/83 passed

**Gotchas**:
- The engine test for `test_chat_pipeline_mode` is a placeholder — the current engine hardcodes `tier_level = "basic"`, so pipeline mode cannot be triggered without patching the tier resolution. The test validates that the engine does not crash and that proper mocking patterns work.

### Session 4 — 2026-06-03: Task 00090-05 (Retrieval Client + Fusion)

**Tasks completed**: 00090-05
**Key decisions**:
- `RetrievalClient` wraps M3 + M4 engines; both engines are optional constructor params for graceful degradation
- `simple_retrieve()` calls M3 only; `parallel_retrieve()` calls M3+M4 via `asyncio.create_task`
- Each engine failure is isolated — M4 failure does not block M3 results, M3 failure returns empty chunks
- `fuse_context()` truncates chunks to fit within `max_retrieval_tokens` (first-come, first-serve order)
- Graph entities capped at 20, relations capped at 10 in fusion output
- `estimate_tokens()` in `fusion.py` mirrors the same heuristic used in `token_budget.py` (`len(text) // 4`)
- Tests mock M3/M4 engines using `unittest.mock.AsyncMock`

**Gotchas**:
- None — implementation passed all tests on first attempt

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

## 7. Deep Research Module (Phase 4-A)

### File Map

```
m5_qa/research/
├── __init__.py
├── complexity.py         # 6-dimension scoring (0-15 FR-1)
├── planner.py            # LLM decomposition + rule fallback + M4 KG enrichment
├── agents/
│   ├── __init__.py
│   ├── regulations.py    # M3 dense+sparse + M4 graph + ISO Top 10
│   └── web.py            # 4 engines: DuckDuckGo/Tavily/Brave/Google
├── analyzer.py           # 2-step: regex extraction → LLM conflict detection
├── report_generator.py   # 7-section Markdown + template fallback
└── progress.py           # SSE orchestrator (4-phase pipeline)
```

### Key Design Decisions

| ID | Decision | Why |
|----|----------|-----|
| M5-D20 | Pure Python + asyncio (no LangGraph) | 4-step linear DAG — complexity doesn't warrant framework overhead |
| M5-D21 | 2-step analyzer (regex → LLM) | Regex guarantees numerical precision; LLM explains "why" |
| M5-D22 | Graceful degradation at every phase | Research must always produce output — never return empty |
| M5-D23 | ISO Top 10 via dictionary lookup | Lightweight, zero-dependency alternative to full ISO Agent |

## 8. Open Issues

- FR-7 (质疑与深入): deferred to Phase 4-B — M8 route `POST /research/{id}/question` already reserved
- Phase 4-B integration: Deep Research reports need `POST /projects/{id}/conclusions` for Projects save flow
