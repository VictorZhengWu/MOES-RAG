# Module Memory Index — Marine & Offshore Expert System

> **Purpose**: Fast-lookup index for all module memory files. Read this first when starting a new session to understand the overall project state, then dive into the specific module file you need.

> **Last Updated**: 2026-05-17

---

## Module Status Overview

| Module | Name | Status | Sessions | Last Session | Active Task |
|--------|------|--------|----------|-------------|-------------|
| M1 | Document Parsing Engine | ✅ Complete | 8 | 2026-05-24 | — |
| M2 | Storage Abstraction Layer | ✅ Complete | 1 | 2026-05-19 | — |
| M3 | Retrieval Engine | ✅ Complete | 1 | 2026-05-24 | — |
| M4 | Knowledge Graph Engine | 🔲 Not Started | 0 | — | — |
| M5 | RAG QA Engine | 🔲 Not Started | 0 | — | — |
| M6 | User Web Portal | 🔄 In Development | ~8 | 2026-05-16 | 00030 + 18 placeholders |
| M7 | Admin Web Portal | ✅ Core Pages Complete | 2 | 2026-05-17 | 00040 + 7 placeholders |
| M8 | API Gateway | 🔲 Not Started | 0 | — | — |
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
