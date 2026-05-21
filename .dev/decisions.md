# Development Decision Log — Marine & Offshore Expert System

> **Purpose**: Record all cross-module decisions made during development that are NOT captured in the design spec. New sessions MUST read this file to recover context.
> **Last Updated**: 2026-05-12

---

## Decision Index

| ID | Date | Topic | Status |
|----|------|-------|--------|
| D001 | 2026-05-12 | Deployment Mode: Hybrid (Personal + Enterprise + SaaS) | ✅ Decided |
| D002 | 2026-05-12 | LLM Runtime: Pluggable (API + Local) | ✅ Decided |
| D003 | 2026-05-12 | Frontend Stack: Full Separation (FastAPI + Next.js/Vue) | ✅ Decided |
| D004 | 2026-05-12 | Storage: Abstracted via Protocols, Deploy-Time Selection | ✅ Decided |
| D005 | 2026-05-12 | Module Communication: contracts/ Package | ✅ Decided |
| D006 | 2026-05-12 | Repo Structure: Monorepo with Per-Module Packages | ✅ Decided |
| D007 | 2026-05-12 | i18n: 5 Languages (EN/ZH/KO/JA/NO), Default EN, Zero Hardcoded Strings | ✅ Decided |
| D008 | 2026-05-12 | System Name: "Marine & Offshore Expert System" | ✅ Decided |
| D009 | 2026-05-12 | Code Comments: Detailed English, WHAT + WHY Mandatory | ✅ Decided |
| D010 | 2026-05-12 | Development Order: Frontend-First (M6/M7 before Backend) | ✅ Decided |
| D011 | 2026-05-12 | Session Strategy: Per-Module Clean Sessions + Module Memory Files | ✅ Decided |
| D012 | 2026-05-12 | File Naming: Date Suffix at End of Filename | ✅ Decided |

---

## Decision Details

### D001: Deployment Mode — Hybrid (Personal + Enterprise + SaaS)

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: Support three deployment modes with a single codebase:
- Personal: Single-user, local machine, zero external dependencies
- Enterprise: On-premise, multi-user, enterprise auth (LDAP)
- SaaS: Multi-tenant cloud, elastic scaling, billing

**Why**: Commercial viability requires all three. Personal mode lowers adoption barrier for individual engineers. Enterprise mode addresses data sovereignty concerns (shipyards, design institutes). SaaS mode captures smaller clients who don't want self-hosting.

**Impact**: Storage abstraction layer (M2) must support lightweight backends (ChromaDB + SQLite) and cluster-grade backends (Milvus + PostgreSQL). deploy/ directory has three config presets.

---

### D002: LLM Runtime — Pluggable (API + Local)

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: Abstract LLM backend behind a pluggable interface. Support both cloud APIs (DeepSeek, Claude, OpenAI) and local runtimes (Ollama, vLLM, LM Studio). Users/admins configure backends via settings UI. Different domain Agents can use different models.

**Why**: Enterprises with sensitive data (military shipbuilding, proprietary designs) cannot send data to external APIs. Individual users may prefer free local models. Mix-and-match allows cost optimization (simple queries → local model, complex queries → cloud API).

**Impact**: M5 must implement LLM backend abstraction. M7 admin UI must provide LLM configuration page.

---

### D003: Frontend Stack — Full Separation (FastAPI + Next.js/Vue)

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: Frontend and backend fully separated. Backend = FastAPI (REST + WebSocket + SSE). Frontend = Next.js 14+ or Vue 3 + Tailwind CSS + shadcn/ui. Shared component library between M6 (user) and M7 (admin).

**Why**: API-first architecture naturally supports third-party API access (M8). Single frontend codebase for user + admin portals reduces long-term maintenance cost. Commercial-grade UX requires a proper frontend framework, not Python full-stack frameworks.

**Impact**: M6 and M7 share a component library. Mock Server needed for Phase 1 frontend development without backend.

---

### D004: Storage — Abstracted via Protocols, Deploy-Time Selection

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: Four storage interfaces (VectorStore, DocumentIndex, RelationalDB, FileStore) defined as Python Protocols. Concrete backends selected at deploy time via deploy.yaml. No code changes needed to switch backends.

**Backend options**:
- Vector: ChromaDB (personal) / Qdrant (enterprise) / Milvus (SaaS) / FAISS (lightweight)
- Relational: SQLite (personal) / PostgreSQL (enterprise/SaaS) / MariaDB (enterprise alternative)
- Document Index: Meilisearch (personal/enterprise) / Elasticsearch (SaaS)
- File: Local FS (personal) / MinIO (enterprise) / S3/OSS (SaaS)

**Why**: Different deployment scenarios have vastly different scale and infrastructure requirements. A personal user cannot be expected to install Milvus + PostgreSQL + Elasticsearch. A SaaS deployment cannot use SQLite.

**Impact**: M2 is purely an abstraction layer. Upper modules depend on Protocols, never on concrete implementations.

---

### D005: Module Communication — contracts/ Package

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: All inter-module communication goes through `contracts/` — a shared package containing Python Protocols, Pydantic models, and shared data structures. Modules never import directly from other modules.

**Why**: Enables independent module development. A module can be completely rewritten as long as it fulfills the same contract. Mock implementations allow frontend development without backend.

**Impact**: contracts/ is the most critical package in the system. Changes to contracts/ require full regression testing across all modules.

---

### D006: Repo Structure — Monorepo with Per-Module Packages

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: Single Git repository with each module as an independent subdirectory. Each module has its own src/, tests/, requirements.txt (or package.json).

**Why**: Simplifies early development for a small team. contracts/ can be directly referenced. CI/CD can be triggered per module directory. Modules can be extracted to separate repos later when the team grows.

**Impact**: Root-level pyproject.toml and requirements.txt for shared dependencies. Per-module requirements.txt for module-specific dependencies.

---

### D007: i18n — 5 Languages, Default EN, Zero Hardcoded Strings

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: Web UI (M6 + M7) supports English, Chinese (简体中文), Korean (한국어), Japanese (日本語), and Norwegian (Norsk). Default language is English. All UI strings externalized into per-language JSON resource files. Real-time language switching without page reload.

**Why**: Global user base across shipbuilding nations: Norway (offshore, DNV), Korea/Japan/China (major shipyards). English is the international maritime lingua franca. Zero hardcoded strings is non-negotiable for a commercial product.

**Impact**: M6 and M7 share i18n infrastructure (next-intl or vue-i18n). All UI components reference i18n keys. Language preference persisted in localStorage + server-side user profile.

---

### D008: System Name — "Marine & Offshore Expert System"

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: The system is officially named "Marine & Offshore Expert System".

**Why**: "Expert System" conveys the professional, knowledge-driven nature. "Marine & Offshore" precisely covers the two major industry segments.

**Impact**: All documentation, README, UI titles, and API branding use this name.

---

### D009: Code Comments — Detailed English, WHAT + WHY Mandatory

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: All source code (Python and TypeScript) must include detailed English comments. Every function, class, and non-trivial code block must explain: (1) WHAT the code does — purpose, inputs, outputs, side effects; (2) WHY the code exists — rationale for this specific approach over alternatives.

**Why**: This is a multi-year commercial project. Future developers (including the original author) must be able to understand the intent behind code, not just its mechanics. The WHY prevents accidental removal or breaking of essential logic whose purpose is not obvious.

**Impact**: CI linting enforces docstring completeness on public functions. PR reviews must check comment quality. The WHY is non-negotiable for business logic.

---

### D010: Development Order — Frontend-First (M6/M7 before Backend)

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: Phase 1 develops contracts/ → Mock Server → M6 (User Portal) → M7 (Admin Portal) before any backend modules. Phase 2 develops M2 → M1 → M3 → M4 → M5. Phase 3 develops M8 → deploy/.

**Why**: Frontend-first allows visual validation of system functionality early. Stakeholders can discover missing features by clicking through the UI. UI design can feed back into API contract refinements before expensive backend implementation begins.

**Impact**: Mock Server is critical infrastructure. Phase 1 ends with a fully clickable system (fake data, real UI).

---

### D011: Session Strategy — Per-Module Clean Sessions + Module Memory Files

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: Each module is developed in a clean Claude Code session. A three-tier memory file system preserves context across sessions:
- L1 (.dev/decisions.md): Cross-module global decisions
- L2 (.dev/module-memory/m<X>-<name>.md): Per-module development history
- L3 (.dev/test_records/<NNNNN>.md): Per-task test records

New sessions recover context by reading L1 → L2 → L3 files in order.

**Why**: Context window limits cannot hold 8 modules worth of development history. Clean sessions prevent context pollution across modules. File-based memory forces good documentation discipline.

**Impact**: `.claude/CLAUDE.md` must mandate the session-start file reading checklist. Session-end must commit all decisions to memory files before closing.

---

### D012: File Naming — Date Suffix at End of Filename

**Date**: 2026-05-12 | **Status**: ✅ Decided

**Decision**: When filenames include dates, the date goes at the END (e.g., `rag-system-design-2026-05-12.md`), not the beginning. Update the date when the file content is updated.

**Why**: Date-first filenames scatter related files across a directory listing. Date-last filenames group by topic, with the date serving as a version suffix. This makes directory listings more navigable.

**Impact**: Applied to design spec files. Per-session memory entries use ISO dates within the file content, not in filenames.

---

### D013: M2 Backend Delivery Strategy — Personal First, Enterprise/SaaS in Phase 3

**Date**: 2026-05-18 | **Status**: ✅ Decided

**Decision**: M2 (Storage Abstraction Layer) first implements Personal mode backends only — ChromaDB (VectorStore), Meilisearch (DocumentIndex), SQLite (RelationalDB), Local FS (FileStore). Qdrant/Milvus/PostgreSQL/MariaDB/MinIO/S3 are deferred to Phase 3 alongside `deploy/` configuration.

**Why**: Phase 2's goal is end-to-end system flow (M2 → M1 → M3 → M4 → M5). Personal mode backends are sufficient to validate the full pipeline. Enterprise/SaaS backends are deployment concerns that naturally pair with `deploy.yaml` and Docker Compose/K8s configs in Phase 3.

**Impact**: M2 task list is scoped to 4 backend implementations + factory/config system. Enterprise/SaaS backends will be tracked as Phase 3 tasks.

---

### D014: M1 Document Parser — Docling as Primary Engine

**Date**: 2026-05-21 | **Status**: ✅ Decided

**Decision**: Docling v2.94 is the primary document parsing engine for all file formats (PDF/DOCX/XLSX/PPTX/HTML/Images). Marker and MinerU are PDF-only alternatives. Old Office formats (.doc/.xls/.ppt) are excluded.

**Why**: Docling handles 10+ formats natively (including the Office formats that would otherwise need 4 separate tools), has built-in OCR (6 engines), VLM pipeline for complex documents, and a mature MIT-licensed codebase from IBM Research. One engine covers 90% of formats instead of installing 6 separate tools. Marker/MinerU remain as options when users prefer their specific PDF-to-Markdown quality.

**Impact**: M1 has a simplified architecture — one primary backend + 2 PDF-specific alternatives. Only 3 backend adapters to maintain.

---

### D015: M1 Complex Table Handling — 4-Layer Pipeline + Quality Gate

**Date**: 2026-05-21 | **Status**: ✅ Decided

**Decision**: Complex tables are processed through a 4-layer pipeline (Structure Detection → Cell Text → Header-to-Cell Annotation → Optional LLM Semantic Understanding). A complexity scoring system (7 criteria) gates table content: score 0=auto-approve, 1-2=low confidence, 3+=block embedding and require human review via M7.

**Why**: Classification society documents contain heavily nested tables with merged cells, footnotes, and cross-page spans. Single-pass parsing cannot reliably handle these. The quality gate ensures accuracy-first: no complex content enters the vector database until human-verified.

**Impact**: M1 has three new components: table_annotator.py, table_merger.py, quality.py. M7 needs a review UI for flagged content. ParsedDocument gets new fields: confidence, review_required, review_reasons.

---

### D016: M1 GPU Auto-Detection Tiered Recommendation

**Date**: 2026-05-21 | **Status**: ✅ Decided

**Decision**: M1 auto-detects GPU hardware at startup and recommends configuration tiered by capability: (1) GPU ≥ 8GB + Linux → vLLM + PaddleOCR-VL-1.5, (2) GPU ≥ 8GB + Windows → Transformers + GraniteDocling-258M, (3) GPU < 8GB → INT8 quantization or Standard Pipeline, (4) No GPU → EasyOCR CPU mode. User can override any recommendation.

**Why**: vLLM is Linux-only. PaddleOCR-VL-1.5 needs ~4.2GB VRAM (or 230MB INT8). Different deployment environments require different optimization strategies. Auto-detection eliminates setup guesswork while preserving user choice.

**Impact**: config.py has hardware detection logic. M7 admin UI shows detected hardware + recommendation.

---

### D017: M1 Image Storage — Per-Document Directory with Relative Paths

**Date**: 2026-05-21 | **Status**: ✅ Decided

**Decision**: Each parsed document gets its own output directory with sub-directories for pages/, figures/, and tables/. Markdown files use relative paths (`pages/page_001.png`). Images from the original document are preserved in their original format; rendered images use PNG at 144 DPI. Metadata sidecar files (.meta.json) accompany each figure.

**Why**: Self-contained directories make documents portable and human-browsable. Relative paths ensure the Markdown renders correctly when the directory is moved or shared. Original format preservation avoids quality loss from re-encoding.

**Impact**: image_manager.py handles extraction, storage, and metadata generation. M2 FileStore stores the output directory tree.

---

### D018: M1 Metadata Extraction — Auto-Detect 5 Fields + Manual Verification

**Date**: 2026-05-21 | **Status**: ✅ Decided

**Decision**: M1 auto-extracts 5 metadata fields (classification_society, regulation_name, version_year, chapter_section, language) using regex rules and language detection. Remaining fields (domain, vessel_types, system_type, manufacturer, equipment_model) require manual annotation. All auto-extracted values can be corrected by the admin via M7.

**Why**: The 5 fields have predictable text patterns in marine documents. The other 6 fields require domain expertise to classify correctly. Auto-detection saves time; manual verification ensures accuracy.

**Impact**: marine_metadata.py implements regex-based extraction. M7 document detail page shows extracted metadata with edit capability.

---

## Pending Decisions

> *No pending cross-module decisions at this time.*

---

## Decision Change Log

> *Record any reversals or modifications to previous decisions here.*
> *Format: [Date] D00X — Original decision → New decision. Reason: ...*
