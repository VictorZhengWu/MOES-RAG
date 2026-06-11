# Module Memory Index — Marine & Offshore Expert System

> **Purpose**: Fast-lookup index for all module memory files. Read this first when starting a new session to understand the overall project state, then dive into the specific module file you need.

> **Last Updated**: 2026-06-09 (end of session)

---

## Module Status Overview

| Module | Name | Status | Sessions | Last Session | Active Task |
|--------|------|--------|----------|-------------|-------------|
| M1 | Document Parsing Engine | ✅ 3 Engines | 9 | 2026-06-07 | Docling + Marker + MinerU backends |
| M2 | Storage Abstraction Layer | ✅ 6 Backends | 3 | 2026-06-09 | PostgreSQL + ES + MinIO/S3 complete |
| M3 | Retrieval Engine | ✅ Enhanced | 2 | 2026-06-07 | Propositions + hierarchical nav |
| M4 | Knowledge Graph Engine | ✅ Complete | 4 | 2026-06-03 | — |
| M5 | RAG QA Engine | 🔄 Enhanced | 8 | 2026-06-11 | Projects 70% (3 integrations pending) |
| M6 | User Web Portal | ✅ Complete | ~10 | 2026-06-11 | 21/21 placeholders resolved |
| M7 | Admin Web Portal | ✅ Complete | 5 | 2026-06-11 | PG/ES/MinIO config + monitoring done |
| M8 | API Gateway | ✅ Enhanced | 4 | 2026-06-09 | Redis rate limit + Test Connection endpoints |
| — | contracts/ | ✅ | 1 | 2026-05-12 | 00010 |
| — | deploy/ | ✅ | 1 | 2026-06-09 | 3 profiles + Redis + PG/ES/MinIO config |

## Phase 3 Complete Tracks (14)

3-A Propositional Indexing · 3-B Hierarchical Navigation · 3-C OAuth+Security · 3-D Placeholder Unlock · 3-E Config Store · 3-F VectorStore Expansion · 3-G Multi-Profile Deploy · 3-H Error Hardening · 3-I E2E Tests · 3-J M1 Alternative Engines · **3-K Redis Rate Limit Persistence** · **3-L PostgreSQL Backend** · **3-M Elasticsearch Backend** · **3-N MinIO/S3 Backend**

## Phase 4: Deep Research + Projects (NEW)

| Task | Name | Status |
|------|------|--------|
| 00104 | Deep Research 引擎 (9 sub-tasks) | ✅ 完成 (146 passed) |
| 00105 | Projects 工作空间 (12 sub-tasks) | 🔄 70% (3 integrations pending) |

## Remaining Work (Post Phase 4)

| Priority | Item | Module |
|----------|------|--------|
| P1 | README / API docs | — |
| P2 | Deep Research (P13) | M6 |
| P2 | K8s deployment | deploy |
| P3 | Help page (P16) | M6 |

## Status Legend

- 🔲 Not Started
- 🔄 In Development
- ✅ Complete
- ❌ Blocked / Broken
- ⏸️ Paused

---

## Quick Reference: Which File To Read

| If you need to... | Read |
|-------------------|------|
| Understand the overall architecture | `.dev/specs/rag-system-design-2026-05-12.md` |
| Know cross-module decisions | `.dev/decisions.md` |
| Walk through Docling examples | `.dev/specs/docling-capabilities-reference-2026-05-21.md` |
| Work on a specific module | `.dev/module-memory/m<X>-<name>.md` |
| See what tasks remain | `.dev/tasks.md` |
| Understand a task's test history | `.dev/test_records/<NNNNN>.md` |
