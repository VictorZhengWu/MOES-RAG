# Module Memory Index — Marine & Offshore Expert System

> **Purpose**: Fast-lookup index for all module memory files. Read this first when starting a new session to understand the overall project state, then dive into the specific module file you need.

> **Last Updated**: 2026-06-07 (end of session)

---

## Module Status Overview

| Module | Name | Status | Sessions | Last Session | Active Task |
|--------|------|--------|----------|-------------|-------------|
| M1 | Document Parsing Engine | ✅ 3 Engines | 9 | 2026-06-07 | Docling + Marker + MinerU backends |
| M2 | Storage Abstraction Layer | ✅ 4 VectorStores | 2 | 2026-06-07 | ChromaDB/FAISS/Qdrant/Milvus |
| M3 | Retrieval Engine | ✅ Enhanced | 2 | 2026-06-07 | Propositions + hierarchical nav |
| M4 | Knowledge Graph Engine | ✅ Complete | 4 | 2026-06-03 | — |
| M5 | RAG QA Engine | ✅ Enhanced | 4 | 2026-06-07 | OAuth + hardening + web search |
| M6 | User Web Portal | 🔄 17/28 unlocked | ~10 | 2026-06-07 | Backend integrated |
| M7 | Admin Web Portal | 🔄 Config UI done | 5 | 2026-06-07 | All settings via UI |
| M8 | API Gateway | ✅ Enhanced | 4 | 2026-06-09 | Redis rate limit persistence complete |
| — | contracts/ | ✅ | 1 | 2026-05-12 | 00010 |
| — | deploy/ | ✅ | 1 | 2026-06-07 | 3 profiles + Docker Compose |

## Phase 3 Complete Tracks (10)

3-A Propositional Indexing · 3-B Hierarchical Navigation · 3-C OAuth+Security · 3-D Placeholder Unlock · 3-E Config Store · 3-F VectorStore Expansion · 3-G Multi-Profile Deploy · 3-H Error Hardening · 3-I E2E Tests · 3-J M1 Alternative Engines

## Remaining Work (Phase 3+)

| Priority | Item | Module |
|----------|------|--------|
| P1 | Redis rate limit persistence | M8 |
| P1 | PostgreSQL backend | M2 |
| P1 | README / API docs | — |
| P2 | Elasticsearch backend | M2 |
| P2 | MinIO/S3 file store | M2 |
| P2 | Deep Research (P13) | M6 |
| P3 | K8s deployment | deploy |
| P3 | Help page (P16) | M6 |
| — | contracts/ | ✅ Complete | 1 | 2026-05-12 | 00010 |
| — | Mock Server (独立) | ✅ Complete | 1 | 2026-05-13 | 00020 |

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
