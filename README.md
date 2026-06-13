# Marine & Offshore Expert System

Professional Retrieval-Augmented Generation (RAG) intelligent Q&A system for the ship and offshore engineering industry.

**Languages**: English | 中文 | 한국어 | 日本語 | Norsk

---

## Overview

This system integrates global classification society rules (DNV, ABS, CCS, LR, BV, RINA, NK, KR), IMO regulations (SOLAS, MARPOL, IGC/IGF Codes), multi-discipline engineering knowledge, and vessel-type-specific data to provide precise, citation-backed answers.

**Key Features**:

- **Multi-Society Cross-Referencing**: Compare requirements across DNV/ABS/CCS/LR with conflict detection
- **Deep Research**: Multi-step AI agent that decomposes complex queries, retrieves from multiple sources in parallel, cross-references regulations, and generates 7-section structured reports
- **Project Workspaces**: Organize conversations, documents, and compliance tracking by marine engineering project phase (design/construction/delivery/operation)
- **Compliance Tracking**: Per-clause regulation verification matrix with deviation management and audit readiness
- **Citation Traceability**: Every answer includes numbered citations linked to specific society clauses (e.g., DNV Pt.3 Ch.3 §6.2, 2025 edition)
- **Team Collaboration**: @mentions, discussion threads, notification center, role-based permissions (Owner/Editor/Viewer)
- **OpenAI-Compatible API**: Drop-in replacement — swap API key and base URL in any OpenAI SDK client

## Architecture

8 independent modules across 5 layers:

```
Layer 5 — Gateway
  M8: API Gateway (FastAPI, port 8000)
       — Auth (API keys), rate limiting (in-memory/Redis), routing
       — OpenAI-compatible /v1/chat/completions, /v1/models

Layer 4 — Intelligence
  M5: RAG QA Engine
       — 3 pipeline modes (simple/pipeline/self_rag)
       — Deep Research multi-step agent
       — Project workspaces with 10 tables
       — Pluggable LLM backend (DeepSeek, OpenAI, Claude, Ollama)

Layer 3 — Retrieval
  M3: Retrieval Engine       M4: Knowledge Graph Engine
       — Dense + sparse dual        — Rule + LLM entity extraction
         path retrieval              — Kuzu embedded graph database
       — RRF fusion + reranking     — BFS traversal + cross-references
       — Propositional indexing      — 30+ entity types

Layer 2 — Storage
  M2: Storage Abstraction Layer
       — 6 backends: ChromaDB/FAISS/Qdrant/Milvus (vector)
                     Meilisearch/Elasticsearch (full-text)
                     SQLite/PostgreSQL (relational)
                     LocalFS/MinIO/S3 (file)
       — Deploy-time backend selection via deploy.yaml

Layer 1 — Ingest
  M1: Document Parsing Engine
       — 3 backends: Docling, Marker, MinerU
       — GPU auto-detection + backend recommendation
       — Table merging + complexity quality gates

Frontend
  M6: User Web Portal (Next.js, port 3000)
  M7: Admin Web Portal (Next.js, port 3001)
```

## Deployment Modes

| Mode | Backends | Target User |
|------|----------|-------------|
| **Personal** | ChromaDB + SQLite + LocalFS | Single user, local machine |
| **Enterprise** | Optional: Qdrant/PostgreSQL/MinIO | Internal team, on-premise |
| **SaaS** | Qdrant + PostgreSQL + MinIO/S3 + Redis | Multi-tenant cloud |

## Quick Start (Personal Edition)

**Prerequisites**: [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### One-Click Start

```
Windows:  double-click deploy/personal/start.bat
Mac/Linux: cd deploy/personal && ./start.sh
```

First run downloads Docker images (5-10 min). Subsequent starts take ~30 seconds.

### Manual Start

```bash
cd deploy/personal
docker compose up -d
```

### Access

| URL | Purpose |
|-----|---------|
| `http://localhost:3000` | User Portal |
| `http://localhost:8000/docs` | API Documentation |
| `http://localhost:3000/help` | Online Help & Troubleshooting |

**Offline help**: see `deploy/personal/HELP.md`

### Stop

```bash
cd deploy/personal
docker compose down
# Or double-click stop.bat (Windows)
```

The Personal edition uses embedded backends (ChromaDB, SQLite, LocalFS) with no external services required. Features include file parsing (optional, via `--profile parsing`) and local LLM (optional, via `--profile llm`).

## API Access

OpenAI-compatible endpoint:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-m8-your-api-key"
)

response = client.chat.completions.create(
    model="m5-qa",
    messages=[{
        "role": "user",
        "content": "DNV Pt.4 Ch.3 welding procedure requirements for EH36 steel?"
    }]
)

print(response.choices[0].message.content)
# Response includes citations with clause references
```

Generate API keys from Admin Portal → API Keys.

## Features

### Core Q&A
- Citation-backed answers with society/clause traceability
- 5-language i18n (EN/ZH/KO/JA/NO), instant switching
- Streaming SSE responses
- Web search integration (DuckDuckGo, Tavily, Brave, Google)
- File upload with drag-and-drop (PDF, DOCX, XLSX, PPTX, images)

### Deep Research
- Multi-step research agent with real-time progress
- Parallel retrieval: regulations (M3+M4) + web search
- Cross-society conflict detection
- 7-section structured report (executive summary, comparison matrix, recommendations, inspection checklist, risk matrix, reference trace, limitations)

### Projects
- Template-based project creation by vessel type + society
- Folder tree: phase → discipline → sub-folder
- Kanban issue tracking with drag-and-drop
- Compliance matrix per regulation clause
- Case study archival with structured details (challenge/solution/lessons)
- Cross-project conclusion linking

### Administration (M7)
- System configuration (LLM, retrieval, features, storage, deploy mode, OAuth, SMTP)
- Storage backend test connections (PostgreSQL, Elasticsearch, MinIO)
- Health monitoring with auto-refresh
- API key management

## Backend Matrix

| Interface | Personal | Enterprise | SaaS |
|-----------|----------|-----------|------|
| Vector Store | ChromaDB / FAISS | Qdrant / Milvus | Qdrant / Milvus |
| Document Index | Meilisearch | Meilisearch / Elasticsearch | Elasticsearch |
| Relational DB | SQLite | SQLite / PostgreSQL | PostgreSQL |
| File Store | Local FS | Local FS / MinIO | MinIO / S3 |
| Rate Limiter | In-Memory | In-Memory / Redis | Redis |

## Development

```bash
# Install
pip install -e contracts/
pip install -e m1-doc-parsing/
pip install -e m2-storage/
pip install -e m3-retrieval/
pip install -e m4-knowledge-graph/
pip install -e m5-qa-engine/
pip install -e m8-api-gateway/

# Frontend
cd m6-user-portal && npm install
cd m7-admin-portal && npm install

# Run tests
python -m pytest m1-doc-parsing/tests/ -q
python -m pytest m2-storage/tests/ -q
python -m pytest m3-retrieval/tests/ -q
python -m pytest m4-knowledge-graph/tests/ -q
python -m pytest m5-qa-engine/tests/ -q
python -m pytest m8-api-gateway/tests/ -q
```

**Test Suite**: 536 tests passing across 6 modules.

## Documentation

| Document | Purpose |
|----------|---------|
| `.dev/specs/rag-system-design-2026-05-12.md` | System architecture |
| `.dev/planning.md` | Development plan |
| `.dev/decisions.md` | Cross-module design decisions |
| `.dev/tasks.md` | Task list (all complete) |
| `.dev/specs/phase-4a-deep-research-design-2026-06-09.md` | Deep Research PRD |
| `.dev/specs/phase-4b-projects-design-2026-06-09.md` | Projects PRD |

## License

Proprietary. All rights reserved.
