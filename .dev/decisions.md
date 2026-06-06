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

### D019: M1 Standalone Web UI — Single-File HTML + FastAPI

**Date**: 2026-05-21 | **Status**: ✅ Decided

**Decision**: M1's Web UI is a single-file HTML served by FastAPI. All controls (format selection, OCR engine, VLM model) are in one page. No React build step, no separate frontend project.

**Why**: M1 is a developer/administrator tool, not end-user-facing. A single-file HTML page is easier to maintain, deploy, and modify than a full Next.js project.

**Impact**: `m1_parser/standalone/web_server.py` has an inline HTML template.

---

### D020: M1 Chunking Strategy — HybridChunker with BGE-small-EN

**Date**: 2026-05-22 | **Status**: ✅ Decided

**Decision**: M1 uses docling's HybridChunker with HuggingFaceTokenizer wrapping BAAI/bge-small-en-v1.5 model. Three-level graceful degradation: docling → transformers → tokenizer.

**Why**: HybridChunker provides semantic boundary detection superior to fixed-length splitting. bge-small-en balances speed vs quality for marine domain text.

**Impact**: `m1_parser/output/chunker.py` with try/except chain for graceful fallback.

---

### D021: M3 Retrieval Engine — 7-Stage Pipeline with Adaptive Paths

**Date**: 2026-05-24 | **Status**: ✅ Decided

**Decision**: M3 implements a 7-stage pipeline with 3 adaptive paths based on query type: exact match (BM25 only, ~50ms), keyword query (dense+sparse+fusion, ~200ms), natural language (all 7 stages including reranker, ~1-2s).

**Why**: Not all queries need the full pipeline. Exact match queries (regulation identifiers) skip embedding entirely. Keyword queries skip the expensive cross-encoder reranker.

**Impact**: pipeline.py has `_bm25_only()`, `_hybrid_no_rerank()`, and `_full_pipeline()` methods. Query analysis determines path selection.

---

### D022: M3 RAG Enhancements — HyDE + Time-Aware + Hierarchical

**Date**: 2026-05-24 | **Status**: ✅ Decided

**Decision**: Phase 2 implements 3 RAG enhancements:
- HyDE: Generate hypothetical answer → embed that → search vectors (bridges query-document semantic gap)
- Time-Aware: Default filter to last 3 years of regulations (prevents citing outdated norms)
- Hierarchical Navigation: Chapter/section filter narrows search space (M1 already extracts chapter_section)

**Why**: These are the 3 highest-ROI RAG enhancements for marine domain. HyDE bridges short technical queries. Time-aware prevents compliance risk from citing obsolete regulations. Hierarchical leverages the natural tree structure of classification society documents.

**Impact**: M3 pipeline has `_generate_hyde_hypothesis()`, `_build_filters` with `default_year_range`, and chapter_section filtering.

---

### D023: M4 Knowledge Graph — Kuzu Embedded Graph Database

**Date**: 2026-05-24 | **Status**: ✅ Decided

**Decision**: M4 uses Kuzu as its graph database — an embedded, MIT-licensed graph DB with Cypher-compatible query language. One `.db` file, zero services. Neo4j is deferred to Phase 3 Enterprise.

**Why**: Same philosophy as ChromaDB (M2) — embedded, file-based, pip-installable. Personal mode users should not need to install a graph database service. Kuzu's Cypher compatibility makes migration to Neo4j trivial if needed later.

**Impact**: m4_kg/graph/kuzu_store.py with schema, 5 indexes, and full CRUD operations.

---

### D024: M4 Entity Extraction — LLM + Rule Hybrid with Disambiguation

**Date**: 2026-05-24 | **Status**: ✅ Decided

**Decision**: M4 extracts entities using pure LLM prompt-based extraction with rule-based fallback. Entities of type regulation_clause and equipment are disambiguated by prefixing the classification society (e.g., "DNV-§5.2" vs "ABS-§5.2"). Negation detection filters false positives from "except/excluding" phrases.

**Why**: LLM extraction offers highest accuracy for the 6 entity types in marine domain. Rule fallback guarantees minimum availability even when LLM is unreachable. Disambiguation prevents cross-document naming collisions.

**Impact**: llm_extractor.py (token-aware batching), rule_extractor.py (negation filter), merger.py (disambiguation).

---

### D025: M4 Incremental Update — CASCADE_DELETE + SHARED_RETAIN

**Date**: 2026-05-24 | **Status**: ✅ Decided

**Decision**: When a document is deleted, entities with ref_count==1 are deleted (CASCADE_DELETE). Entities with ref_count>1 (shared across documents) are retained and ref_count is decremented. The MERGE operation in insert_entities increments ref_count for existing entities.

**Why**: Steel grades (EH36, AH32) and ship types appear in multiple documents. Deleting one document should not remove these shared entities. The ref_count mechanism is a lightweight alternative to full entity linking.

**Impact**: kuzu_store.py uses MERGE with ON MATCH SET ref_count = ref_count + 1. delete_by_doc_id checks ref_count before deletion.

---

### D026: M5 QA Engine — 3-Mode RAG with Tiered Service

**Date**: 2026-06-03 | **Status**: ✅ Decided

**Decision**: M5 implements one engine with three pipeline modes: simple (M3-only, 4K context, Basic), pipeline (M3+M4 parallel, 8K context, Pro), self_rag (iterative retrieval with M3 score check, 16K context, Enterprise). Premium quota allows temporary mode upgrade.

**Why**: Building three separate engines is wasteful when the difference is pipeline depth, not architecture. Tiered service enables cost control while offering premium features to paying users.

**Impact**: engine.py mode routing, three pipeline files (simple/pipeline/self_rag.py), PremiumQuota system.

---

### D027: M5 Dynamic Token Budget — Tier-Ratio + Query-Length Factor

**Date**: 2026-06-03 | **Status**: ✅ Decided

**Decision**: Token budget is allocated by user tier with a query-length adjustment factor (0.5x-1.5x). Longer queries get more retrieval budget. The ratios are: Basic (30/20/50), Pro (40/20/40), Enterprise (50/20/30). No per-query-type classification (avoids circular dependency on a classifier).

**Why**: Long queries (e.g., "Compare DNV and ABS welding preheat requirements for EH36 steel in bulk carriers") need more retrieval context than short ones ("EH36 preheat?"). The simple length heuristic achieves 80% of the benefit of a full classifier without the complexity or LLM cost.

**Impact**: token_budget.py with `allocate_budget(tier, query)` and `query_length_factor`.

---

### D028: M5 Self-RAG — Simplified, M3-Score-Driven

**Date**: 2026-06-03 | **Status**: ✅ Decided

**Decision**: M5's Self-RAG loop uses M3's cosine similarity scores directly as the quality signal (no separate evaluator model). When top score < 0.5, the query is rewritten via synonym expansion and re-retrieved. Maximum 3 iterations. No separate citation verifier in Phase 1.

**Why**: M3 scores are already a reliable relevance signal — more accurate than hand-written keyword-matching rules and free (no extra LLM call). Synonym expansion is a simple, deterministic enhancement. Phase 3 can upgrade to LLM-driven evaluation and query rewriting.

**Impact**: self_rag.py with `_expand_query()`, score threshold gating, and iteration limit.

---

### D029: M5 Prompt Manager — DB-Backed with Language Fallback

**Date**: 2026-06-03 | **Status**: ✅ Decided

**Decision**: Prompt templates are stored in M5's SQLite database (m5_qa.db, m5_prompts table) rather than hardcoded. PromptManager supports bilingual templates (en/cn) with fallback chain: requested language → English → hardcoded default. Phase 3 adds version control and A/B testing.

**Why**: Database-driven prompts allow the M7 admin to update system behavior without redeploying code. The language fallback ensures prompts work even when translations are missing. Hardcoded defaults guarantee the system works on first install with zero DB seeding.

**Impact**: prompt_manager.py with `get_prompt_by_language()`, `set_prompt()`, and `_get_default_prompt()`.

---

### D030: M5 Conversation — M5-Owned SQLite, Not M2

**Date**: 2026-06-03 | **Status**: ✅ Decided

**Decision**: M5 manages its own SQLite database (m5_qa.db) for conversations, messages, and premium quotas. This data is NOT stored through M2's RelationalDB protocol — M2 is a storage abstraction layer and should not contain M5's business logic schemas.

**Why**: M2 stores infrastructure data (vector embeddings, document indexes). M5's conversation data is application-specific. Mixing them would couple the storage layer to a particular application's schema, violating the abstraction.

**Impact**: conversation/manager.py uses aiosqlite directly. m5_qa.db is separate from M2's relational DB file.

---

### D031: M5 Web Search — Pluggable Engines with Health Checks

**Date**: 2026-06-03 | **Status**: ✅ Decided

**Decision**: Web search supports 5 pluggable engines (DuckDuckGo, SearXNG, Tavily, Brave, Google) via a factory pattern. Each engine has typed error handling (ConfigError, AuthError, QuotaError, NetworkError) and a health_check() method for the admin UI's Test Connection button. Configuration is hot-swappable via M8 admin endpoint.

**Why**: Different regions need different search engines (DuckDuckGo may be blocked in China, SearXNG+Baidu fills the gap). Different deployment tiers have different cost tolerances (free DuckDuckGo for personal, paid Tavily for enterprise). Typed errors give users actionable messages instead of silent failures.

**Impact**: web_search.py with WebSearchEngine protocol, 5 implementations, error hierarchy, and factory function.

---

### D032: M5 Error Hardening — No Silent Failures or User-Facing Tracebacks

**Date**: 2026-06-06 | **Status**: ✅ Decided

**Decision**: All user-facing code paths (chat, chat_stream, retrieve, graph_search, cross_reference) must catch exceptions and return friendly error messages — never tracebacks. Full tracebacks are logged for admin debugging. Retrieval errors are surfaced as warnings in the LLM context so the model can provide helpful responses even during partial failures.

**Why**: Production systems must degrade gracefully, not crash. A user seeing a Python traceback loses trust in the system. The LLM can often provide useful answers even when some subsystems are down ("Document search is temporarily unavailable, but I can answer from my knowledge...").

**Impact**: engine.py wraps all pipeline calls in try/except. retriever.py logs and appends errors to RetrievalContext.errors. M8 has a global exception handler returning JSON 500.

---

### D033: M8 API Gateway — Independent FastAPI with M5 Co-Process

**Date**: 2026-06-03 | **Status**: ✅ Decided

**Decision**: M8 is an independent FastAPI process (port 8000) that imports and runs M5 in the same process via a lazy singleton (`get_qa_engine()`). No cross-process HTTP between M8 and M5 — zero serialization overhead.

**Why**: M8 needs FastAPI for middleware, OpenAPI docs, and proper HTTP handling. M5 is a Python library without HTTP logic. Running them in the same process avoids the latency and complexity of inter-service communication for the core QA path.

**Impact**: M8's app.py imports and instantiates QAEngine on first use. M8 routes call engine methods directly.

---

### D034: M8 API Key System — sha256 Hashed, sk-m8- Prefix

**Date**: 2026-06-03 | **Status**: ✅ Decided

**Decision**: M8 manages its own API keys in format `sk-m8-{16hex}`. Keys are stored as SHA-256 hashes — the raw key is shown only once at creation time. Key validation looks up the hash. This is separate from LLM provider keys (stored in M5 config).

**Why**: The API key system controls external access to the Marine Expert System API. LLM provider keys control M5's access to external LLM services. These are completely different trust domains and must be managed independently.

**Impact**: auth/key_manager.py with generate/validate/revoke/list methods. api_keys table in m8_gateway.db.

---

### D035: M8 Rate Limiting — Tiered Sliding Window with Deployment Mode

**Date**: 2026-06-03 | **Status**: ✅ Decided

**Decision**: Rate limiting uses an in-memory sliding window (60s) with per-tier limits that vary by deployment mode: Personal (Basic 100/min, Pro/Enterprise unlimited), Enterprise/SaaS (Basic 30/min, Pro 120/min, Enterprise unlimited).

**Why**: Personal mode has one user — rate limiting is mainly to prevent runaway scripts. SaaS mode needs strict limits for cost control and fair multi-tenant usage. In-memory suffices for Phase 2; Phase 3 SaaS upgrades to Redis for persistence across restarts.

**Impact**: rate_limit/limiter.py with check() method. GatewayConfig.__post_init__ sets limits by deployment_mode.

---

### D036: M6/M7 Backend Integration — M8 Conversation + Auth + Upload Routes

**Date**: 2026-06-04 | **Status**: ✅ Decided

**Decision**: M6 and M7 frontends connect to M8 on port 8000. M8 exposes conversation CRUD routes (GET/DELETE/PATCH /api/v1/conversations), auth routes (POST /auth/register, /auth/login), and document upload route (POST /api/v1/documents/upload). These replace the Phase 1 Mock Server.

**Why**: M6/M7 were built against Mock Server in Phase 1. Phase 2 provides real backend endpoints. The transition is transparent because M6's HTTP client already targets M8's port.

**Impact**: M8 routes/conversations.py, routes/auth.py, routes/documents.py. M6 chat-input.tsx uploads files before sending messages. M7 users page manages API keys.

---

### D037: Deploy — Docker Compose with Multi-Target Dockerfile

**Date**: 2026-06-06 | **Status**: ✅ Decided

**Decision**: deploy/ provides docker-compose.yml with 4 core services (m8, m1, meilisearch) + 2 optional profiles (searxng for search, ollama for LLM). Dockerfile has two targets: m8 (lightweight, ~2GB without docling) and m1 (heavy, ~8GB with docling+transformers). Feature flags are passed as environment variables.

**Why**: Docker solves the BGE-M3 segfault on Windows Python 3.13 by running in Linux containers. M1 is separated from M8 because docling needs 8GB RAM and should not affect QA latency. Optional profiles keep personal deployments lean.

**Impact**: deploy/docker-compose.yml, deploy/Dockerfile, deploy/.env.example, deploy/start.sh, deploy/start.ps1.

---

### D038: Development Workflow — TDD + Subagent-Driven + Review Gates

**Date**: 2026-06-06 | **Status**: ✅ Decided

**Decision**: Every module follows TDD (test first → fail → implement → pass). Multi-task modules use parallel subagent dispatch for independent tasks. Each module undergoes at least one review cycle before merge. Error hardening is done at module completion, not as an afterthought.

**Why**: TDD catches regressions immediately. Parallel subagents reduce wall-clock development time for independent tasks. Review gates catch architecture issues, security gaps, and missing error handling before they reach production.

**Impact**: All modules have test files. .dev/test_records/ tracks every task. Module-memory files record session history.

---

## Pending Decisions

> *No pending cross-module decisions at this time.*

## Decision Reversal Log

| Date | ID | Original | Reversed To | Reason |
|-----|-----|----------|-------------|--------|
| 2026-06-03 | D010 | Frontend-first: M6/M7 in Phase 1 | Actual: M6/M7 started Phase 1, backend completed Phase 2, integration done end Phase 2 | Development order evolved organically as backend modules became ready for integration |

---

## Decision Change Log

> *Record any reversals or modifications to previous decisions here.*
> *Format: [Date] D00X — Original decision → New decision. Reason: ...*
