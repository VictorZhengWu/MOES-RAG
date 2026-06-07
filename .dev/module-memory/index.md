# Module Memory Index — Marine & Offshore Expert System

> **Purpose**: Fast-lookup index for all module memory files. Read this first when starting a new session to understand the overall project state, then dive into the specific module file you need.

> **Last Updated**: 2026-06-07

---

## Module Status Overview

| Module | Name | Status | Sessions | Last Session | Active Task |
|--------|------|--------|----------|-------------|-------------|
| M1 | Document Parsing Engine | ✅ Complete | 8 | 2026-05-24 | — |
| M2 | Storage Abstraction Layer | ✅ Complete | 2 | 2026-06-07 | 4 VectorStore backends |
| M3 | Retrieval Engine | ✅ Phase 3 Enhanced | 2 | 2026-06-07 | Propositional index + hierarchical nav |
| M4 | Knowledge Graph Engine | ✅ Complete | 4 | 2026-06-03 | — |
| M5 | RAG QA Engine | ✅ Phase 3 Enhanced | 4 | 2026-06-07 | OAuth + bcrypt + web search + hardening |
| M6 | User Web Portal | 🔄 Backend Integrated | ~9 | 2026-06-07 | 17 placeholders unlocked |
| M7 | Admin Web Portal | 🔄 Backend Integrated | 4 | 2026-06-07 | Config UI (LLM/Features/Storage/Deploy/OAuth) |
| M8 | API Gateway | ✅ Phase 3 Enhanced | 3 | 2026-06-07 | Unified config store + OAuth + extras |
| — | contracts/ | ✅ Complete | 1 | 2026-05-12 | 00010 |
| — | Mock Server (独立) | ✅ Complete | 1 | 2026-05-13 | 00020 |
| — | deploy/ | ✅ Complete | 1 | 2026-06-07 | 3 profiles + Docker Compose |

## Phase 3 Summary

| Track | Name | Status |
|-------|------|:--:|
| 3-A | Propositional Indexing | ✅ |
| 3-B | Hierarchical Navigation | ✅ |
| 3-C | OAuth + Security (bcrypt, 6 providers) | ✅ |
| 3-D | M6/M7 Placeholder Unlock (17/28) | ✅ |
| 3-E | Unified Config Store (all settings via UI) | ✅ |
| 3-F | VectorStore Expansion (ChromaDB/FAISS/Qdrant/Milvus) | ✅ |
| 3-G | Multi-Profile Deploy (personal/enterprise/saas) | ✅ |
| 3-H | Error Hardening (all modules) | ✅ |
| 3-I | E2E Integration Tests (18 tests) | ✅ |
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
