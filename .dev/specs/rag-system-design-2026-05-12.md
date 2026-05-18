# Marine & Offshore Expert System — Design Specification

> **Document Version**: v1.1 | **Date**: 2026-05-12 | **Status**: Approved

---

## 1. Project Summary

A professional Retrieval-Augmented Generation (RAG) system for the ship and offshore engineering industry. It ingests classification society rules (CCS/DNV/ABS/LR/BV et al.), IMO regulations, multi-discipline engineering knowledge (structural/mechanical/piping/electrical/communication/automation), vessel-type-specific data, and manufacturer equipment documentation — hundreds of GB in total — and provides precise, citation-backed answers through a web chat interface (DeepSeek-style) and an OpenAI-compatible API.

**Deployment modes**: Personal (single-user, local), Enterprise (on-premise, multi-user), SaaS (multi-tenant cloud).

---

## 2. Key Design Decisions (Rationale)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Deployment flexibility** | Personal / Enterprise / SaaS | Commercial viability requires all three; personal mode lowers adoption barrier |
| **LLM runtime** | Pluggable — API (DeepSeek/Claude/GPT) + Local (Ollama/vLLM/LM Studio) | Data sovereignty for enterprises, convenience for individuals |
| **Frontend stack** | Full separation — FastAPI + Next.js/Vue | API-first architecture; single codebase for user + admin portals; API naturally supports third-party access |
| **Storage** | Abstracted via Protocols — ChromaDB/Qdrant/Milvus + SQLite/PostgreSQL/MariaDB + Local/MinIO/S3 | Deploy-time selection; zero code changes when switching backends |
| **Module communication** | Shared `contracts/` package (Python Protocols + Pydantic schemas) | No direct inter-module imports; Mocks enable independent development |
| **Repo structure** | Monorepo with per-module packages | Simplifies early development; modules can be extracted to separate repos later |
| **i18n** | 5 languages (EN/ZH/KO/JA/NO), default EN, real-time switching, zero hardcoded strings | Global user base across shipbuilding nations; Norway for offshore, Korea/Japan/China for shipyards |
| **Code comments** | Detailed English comments — WHAT the code does + WHY it exists | Maintainability for a multi-year commercial project; new developers must understand intent, not just mechanics |

---

## 3. System Architecture

### 3.1 Module Overview — 8 Modules, 5 Layers

```
Layer 5 (Gateway):   M8 — API Gateway
Layer 4 (UI):        M6 — User Portal    M7 — Admin Portal
Layer 3 (Brain):     M5 — RAG QA Engine
Layer 2 (Knowledge): M3 — Retrieval      M4 — Knowledge Graph
Layer 1 (Data):      M1 — Doc Parsing    M2 — Storage Abstraction
```

### 3.2 Module Descriptions

#### M1 — Document Parsing Engine
**Responsibility**: Convert raw files (PDF/DOCX/DWG/TIFF/PNG) into structured, metadata-rich text chunks with vector embeddings.

**Capabilities**:
- PDF/DOCX parsing with layout and hierarchy preservation (Docling/Marker)
- Engineering drawing & schematic understanding via Vision-Language Models
- OCR for scanned documents (PaddleOCR/Surya)
- Semantic chunking: by regulation clause, manual section, drawing view
- Multi-level metadata extraction: classification society, domain, vessel type, system, manufacturer, version year
- Multi-vector embedding: summary embedding + paragraph embedding + clause embedding (BGE-M3/GTE-Qwen2)

**Interfaces**:
- `POST /api/v1/admin/documents/upload` — upload files with metadata
- `GET /api/v1/admin/documents/{task_id}/status` — query parsing status
- Output format: `ParsedDocument` (see `contracts/document.py`)

**Independence**: Other modules consume parsed results from M2 Storage; M1 itself is replaceable without affecting downstream.

---

#### M2 — Storage Abstraction Layer
**Responsibility**: Provide a unified storage interface with multiple backend implementations, selected at deploy time via `deploy.yaml`.

**Four sub-interfaces** (see `contracts/storage.py`):

| Interface | Purpose | Backend Options |
|-----------|---------|-----------------|
| `VectorStoreProtocol` | Dense/sparse vector search | ChromaDB / Qdrant / Milvus / FAISS |
| `DocumentIndexProtocol` | Full-text BM25/SPLADE search | Meilisearch / Elasticsearch |
| `RelationalDBProtocol` | Users, sessions, metadata, config | SQLite / PostgreSQL / MariaDB |
| `FileStoreProtocol` | Raw files, parsed cache | Local FS / MinIO / S3 |

**Key design**: Upper modules depend on Protocols, never on concrete implementations. Factory reads `deploy.yaml` at startup and injects the correct backend instances.

---

#### M3 — Retrieval Engine
**Responsibility**: Given a query, find the most relevant document chunks through a multi-stage retrieval pipeline.

**Pipeline stages**:
1. **Query Enhancement** — Rewriting, HyDE (Hypothetical Document Embeddings), Decomposition
2. **Multi-path Retrieval** — Dense vector (BGE-M3), Sparse vector (SPLADE), BM25 full-text, metadata filtering
3. **Fusion** — Reciprocal Rank Fusion / Weighted Score Fusion
4. **Re-ranking** — ColBERT token-level interaction / Cross-Encoder (BGE-Reranker)
5. **Context Compression** — LongLLMLingua (remove irrelevant content from retrieved chunks)

**Interfaces** (see `contracts/retrieval.py`):
- `RetrievalEngineProtocol.retrieve(request) → RetrievedContext`

**Independence**: Any stage can be upgraded independently. As long as `RetrievedContext` format is stable, M5 is unaffected.

---

#### M4 — Knowledge Graph Engine
**Responsibility**: Extract entities and relations from documents, build and maintain a domain knowledge graph, support cross-regulation mapping and relational reasoning.

**Capabilities**:
- **Entity extraction**: regulation clauses, vessel types, systems, equipment, manufacturers, formulas, parameter thresholds
- **Relation extraction**: references, applies_to, equivalent_to, replaces, requires, prohibits
- **Version tracking**: track regulation changes across years (2023 → 2024 → 2025)
- **Cross-society mapping**: "DNV Pt.4 Ch.3 §5 ↔ ABS Pt.5B §3-2" — equivalence discovery
- **Graph backends**: Neo4j (enterprise/SaaS), KuzuDB (embedded, personal mode)

**Interfaces** (see `contracts/knowledge_graph.py`):
- `KGEngineProtocol.query_entities()`, `query_relations()`, `graph_search()`, `cross_reference()`

---

#### M5 — RAG QA Engine
**Responsibility**: The "brain" of the system. Orchestrates query routing, retrieval, evaluation, and generation to produce final answers with citations.

**Capabilities**:
- **Query Router**: classify query type → route to domain-specific Agent (structure/mechanical/electrical/...)
- **Multi-Agent orchestration**: each domain Agent independently retrieves from its specialized vector store + KG subgraph
- **Self-RAG loop**: retrieve → evaluate relevance → (insufficient? → re-retrieve) → generate → (citations weak? → backtrack) → final output
- **Pluggable LLM backend**: user/admin configure multiple LLM backends via settings UI; different Agents can use different models
- **Streaming generation**: SSE streaming, token-by-token
- **Citation provenance**: every answer includes source citations (society → section → clause → excerpt)
- **Multi-turn conversation**: context tracking + coreference resolution + follow-up intent understanding

**Interfaces** (OpenAI-compatible, see `contracts/qa_engine.py`):
- `POST /api/v1/chat/completions` (streaming + non-streaming)
- `GET /api/v1/conversations`, `GET /api/v1/conversations/{id}`
- `GET /api/v1/models`

---

#### M6 — User Web Portal
**Responsibility**: End-user chat interface, DeepSeek/ChatGPT-style.

**Tech stack**: Next.js 14+ / Vue 3 + Tailwind CSS + shadcn/ui + Zustand/Pinia

**Pages/Features**: Chat dialog, conversation management, knowledge base browser, personal settings, API key management, language switcher (EN/ZH/KO/JA/NO).

**i18n**: All UI strings externalized into per-language resource files. Language preference persisted per user. Real-time switching without page reload. Default language: English. See Section 8.

**Independence**: Pure frontend. Develops against Mock Server in Phase 1; switches to real M5 API in Phase 2 — zero backend changes needed.

---

#### M7 — Admin Web Portal
**Responsibility**: Complete admin operations via Web UI.

**Tech stack**: Same as M6 (shared component library, shared i18n infrastructure).

**Pages/Features**: Document upload & parsing management, knowledge base management, KG visualization & manual correction, LLM multi-backend configuration, user & quota management, system monitoring dashboard, language switcher.

**i18n**: Shares the same i18n resource framework as M6. All admin UI strings externalized identically.

**Independence**: Pure frontend, same mock-to-real transition as M6.

---

#### M8 — API Gateway
**Responsibility**: Expose OpenAI-compatible API for third-party integration.

**Capabilities**:
- Endpoints: `/v1/chat/completions`, `/v1/models`
- Authentication: API Key generation/validation/revocation
- Rate limiting, quota management
- Usage metering & billing (SaaS)
- Full OpenAI SDK / LangChain compatibility — drop-in `base_url` replacement

**Independence**: Thin proxy layer. Zero business logic — transparently forwards to M5.

---

### 3.3 Module Dependency Graph

```
M8 ──────────→ M5
M6 ──→ M5
M7 ──→ M5, M1 (upload trigger)
M5 ──→ M3, M4
M3 ──→ M2
M4 ──→ M2
M1 ──→ M2
```

Strict layered dependency. No upward references. No horizontal dependencies between M3 and M4.

---

### 3.4 Interface Contract Philosophy

All inter-module communication goes through `contracts/`:

- **Python Protocols** for in-process calls (M5 → M3, M5 → M4, all → M2)
- **Pydantic models** for HTTP API schemas (M6/M7/M8 → M5)
- **Data models** (`contracts/document.py`) for shared data structures

Module independence is verified by: **given the same contract version, any module can be replaced with a new implementation without changing any other module's code.**

---

## 4. Development Roadmap (3 Phases)

### Phase 1 — Skeleton & UI (Frontend-First)

| Order | Module | Deliverable |
|-------|--------|-------------|
| 1 | `contracts/` | All Protocols + Schemas defined |
| 2 | Mock Server | Fake API that returns correctly-formatted responses |
| 3 | M6 User Portal | Full UI, all pages functional with mock data |
| 4 | M7 Admin Portal | Full admin UI, all operations simulated |

**Goal**: A fully clickable, testable system in the browser. No real backend yet, but all functionality is visible and UX can be validated.

### Phase 2 — Backend Core

| Order | Module | Deliverable |
|-------|--------|-------------|
| 5 | M2 Storage | All backend implementations, contract tests passed |
| 6 | M1 Doc Parsing | PDF/drawing parsing pipeline operational |
| 7 | M3 Retrieval | Multi-path retrieval with real vector DB |
| 8 | M4 Knowledge Graph | Entity extraction + graph construction + cross-referencing |
| 9 | M5 QA Engine | Real Agent routing + Self-RAG + streaming → system goes live |

### Phase 3 — API & Deployment

| Order | Module | Deliverable |
|-------|--------|-------------|
| 10 | M8 API Gateway | OpenAI-compatible API with auth + rate limiting |
| 11 | `deploy/` | Docker Compose (personal/enterprise), K8s (SaaS) |

---

## 5. Directory Structure

```
E:\myCode\RAG\
├── contracts/            # Shared interface contracts (ALL modules depend on this)
├── m1-doc-parsing/       # Document Parsing Engine
├── m2-storage/           # Storage Abstraction Layer
├── m3-retrieval/         # Retrieval Engine
├── m4-knowledge-graph/   # Knowledge Graph Engine
├── m5-qa-engine/         # RAG QA Engine
├── m6-user-portal/       # User Web Portal (Next.js/Vue)
├── m7-admin-portal/      # Admin Web Portal (Next.js/Vue)
├── m8-api-gateway/       # API Gateway
├── deploy/               # Deployment configs (personal/enterprise/saas)
├── .dev/                 # All development artifacts (specs, plans, tasks, decisions, test records)
├── .claude/              # Claude Code project settings
├── pyproject.toml        # Python project metadata
├── requirements.txt      # Root-level shared dependencies
├── docker-compose.personal.yml
├── docker-compose.enterprise.yml
├── README.md
└── README-cn.md
```

---

## 6. Technology Stack Summary

| Layer | Technology |
|-------|-----------|
| **Backend framework** | Python 3.12+ / FastAPI |
| **Frontend** | Next.js 14+ or Vue 3 + Tailwind CSS + shadcn/ui |
| **Vector DB** | ChromaDB (personal) / Qdrant (enterprise) / Milvus (SaaS) |
| **Relational DB** | SQLite (personal) / PostgreSQL (enterprise/SaaS) / MariaDB (alternative) |
| **Full-text index** | Meilisearch (personal/enterprise) / Elasticsearch (SaaS) |
| **File storage** | Local FS (personal) / MinIO (enterprise) / S3/OSS (SaaS) |
| **Graph DB** | KuzuDB (embedded, personal) / Neo4j (enterprise/SaaS) |
| **LLM** | Pluggable: DeepSeek API / Claude API / OpenAI API / Ollama / vLLM / LM Studio |
| **Embedding models** | BGE-M3 / GTE-Qwen2 (multilingual, multi-vector) |
| **Document parsing** | Docling / Marker / PaddleOCR / Surya |
| **Containerization** | Docker / Docker Compose / Kubernetes |

---

## 7. Code Comment Standard

**All source code (Python and TypeScript) MUST use detailed English comments.**

Every function, class, and non-trivial code block must include:

1. **WHAT**: A clear description of what the code does — its purpose, inputs, outputs, side effects.
2. **WHY**: The rationale for why this code exists and why this specific approach was chosen over alternatives. This is the critical part that prevents future developers (including the original author 6 months later) from removing or breaking essential logic whose purpose is not obvious from the code alone.

### Example (Python)

```python
async def rerank_with_threshold(
    self, chunks: list[ScoredChunk], threshold: float = 0.3
) -> list[ScoredChunk]:
    """
    Re-rank chunks using a cross-encoder and filter below a confidence threshold.

    WHY: Dense vector retrieval alone can return semantically "close" but
    factually irrelevant passages (e.g., a general discussion of welding when
    the user asks about a specific welding procedure in DNV Pt.4 Ch.6).
    The cross-encoder reads the full query-chunk pair and provides a
    relevance score. The threshold drops chunks that the cross-encoder
    considers < 30% likely to answer the query, reducing noise for the LLM.

    Args:
        chunks: Initial retrieval results from the fusion stage.
        threshold: Minimum cross-encoder score to retain a chunk.

    Returns:
        Filtered and re-scored chunks, ordered by cross-encoder confidence.
    """
    ...
```

### Example (TypeScript)

```typescript
/**
 * Persist the user's language preference and broadcast the change.
 *
 * WHY: We use a two-layer approach — localStorage for instant UI response
 * (no network round-trip on language switch) AND an API call to persist the
 * preference server-side. The API call is fire-and-forget for UX speed;
 * localStorage is the source of truth for rendering. On next login, the
 * server-side preference overrides localStorage to sync across devices.
 */
async function switchLanguage(lang: SupportedLanguage): Promise<void> { ... }
```

### Enforcement

- All PRs MUST be reviewed for comment completeness.
- CI linting checks for missing docstrings on public functions.
- The `WHY` is non-negotiable for any code that implements business logic, data transformations, or architectural decisions.

---

## 8. Internationalization (i18n)

### 8.1 Supported Languages

| Code | Language | Rationale |
|------|----------|-----------|
| `en` | English | Default language; international lingua franca of maritime industry |
| `zh` | Chinese (简体中文) | Major shipbuilding nation (China) |
| `ko` | Korean (한국어) | Major shipbuilding nation (Korea) |
| `ja` | Japanese (日本語) | Major shipbuilding nation (Japan) |
| `no` | Norwegian (Norsk) | Offshore/maritime hub (Norway); home of DNV |

### 8.2 Architecture

**Frontend (M6 + M7):**

- **Zero hardcoded strings**: Every user-visible string is defined in locale resource files (`locales/en.json`, `locales/zh.json`, etc.). The UI code references keys, never inline text.
- **Real-time switching**: Changing the language selector instantly re-renders all UI text without a page reload. Implemented via reactive i18n framework (`next-intl` for Next.js, `vue-i18n` for Vue).
- **Persistence**: Language preference stored in (a) `localStorage` for instant availability on next visit, (b) server-side user profile for cross-device sync.
- **Fallback chain**: Requested locale → user preference → browser `Accept-Language` → `en` (default).

**Backend i18n considerations:**

- **API error messages**: Include an i18n key + English fallback in every error response, so the frontend can translate if desired.
- **RAG answers**: The system answers in the language the user asks in — the LLM handles this natively. No translation middleware should alter the generated answer.
- **Document metadata**: UI-facing metadata labels (domain names, status strings) are stored as i18n keys, not display text, in the database.

### 8.3 i18n Resource File Structure

```
m6-user-portal/src/locales/
├── en.json      # English (default, canonical)
├── zh.json      # Chinese
├── ko.json      # Korean
├── ja.json      # Japanese
└── no.json      # Norwegian

m7-admin-portal/src/locales/   # Same structure, admin-specific strings
├── en.json
├── zh.json
├── ko.json
├── ja.json
└── no.json
```

### 8.4 i18n Key Naming Convention

Keys follow `section.component.element` hierarchy:
```json
{
  "chat.input.placeholder": "Ask anything about ship & offshore engineering...",
  "chat.input.send": "Send",
  "chat.citation.source": "Source",
  "chat.conversation.new": "New Conversation",
  "settings.language.label": "Interface Language",
  "admin.documents.upload.title": "Upload Documents"
}
```

---

## 9. Open Questions & Future Considerations

1. **Evaluation dataset**: Needs a curated set of ship/offshore engineering Q&A pairs for benchmarking retrieval and generation quality.
2. **Model fine-tuning**: Consider fine-tuning an embedding model on domain-specific terminology for better retrieval.
3. **Real-time updates**: How to handle new regulation versions — full re-index or incremental update?
4. **Access control granularity**: Per-document? Per-society? Per-domain? (Enterprise/SaaS only)
5. **Offline mode**: Personal edition should work completely offline after initial model download.

---

*Design spec completed. Next step: `writing-plans` skill for Phase 1 implementation planning.*
