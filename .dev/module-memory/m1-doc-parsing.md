# M1 — Document Parsing Engine 模块记忆

> **Purpose**: Record all development sessions, decisions, gotchas, and lessons learned for M1. Read this file before starting ANY new M1 development session.

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | 🔄 In Development |
| Active Tasks | 00060-03 (Docling backend adapter) |
| First Dev Date | 2026-05-21 |
| Last Session Date | 2026-05-21 |
| Total Sessions | 2 |

---

## 2. Session History

### Session 0 — 2026-05-21: Design & Brainstorming

**Outcome**: Design spec approved. 12 sub-tasks defined. Key decisions documented.

**Spec file**: `.dev/specs/m1-doc-parsing-design-2026-05-21.md`
**Reference**: `.dev/specs/docling-capabilities-reference-2026-05-21.md`

### Session 1 — 2026-05-21: 00060-01 + 00060-02 Implementation

**Outcome**: Project skeleton (config.py + pyproject.toml) and format router (router.py) implemented. 12 tests passing.

**Tasks completed**: 00060-01 (config), 00060-02 (router)
**Files created**:
  - `m1_parser/core/config.py` — GPU detection and OCR backend selection
  - `m1_parser/core/router.py` — Magic bytes detection and backend routing
  - `tests/test_config.py` — 6 tests for config
  - `tests/test_router.py` — 6 tests for router
  - `pyproject.toml` — Package config with grouped dependencies

### Session 2 — 2026-05-21: 00060-08 Implementation

**Outcome**: Output serializer (MD/JSON) and image manager (path creation, metadata sidecars) implemented. 12 tests written (5 serializer + 7 image_manager).

**Tasks completed**: 00060-08 (serializer + image_manager)
**Files created**:
  - `m1_parser/output/__init__.py` — Public API exports
  - `m1_parser/output/serializer.py` — save_markdown, save_json, CustomJSONEncoder
  - `m1_parser/output/image_manager.py` — get_output_paths, save_figure_metadata
  - `tests/test_serializer.py` — 5 tests (MD, JSON, encoder, validation, empty content)
  - `tests/test_image_manager.py` — 7 tests (path creation, idempotent, traversal, validation, sidecar, parent creation, input validation)

---

## 3. Key Design Decisions (Module-Internal)

| ID | Date | Decision | Why |
|----|------|----------|-----|
| M1-D01 | 2026-05-21 | Docling v2.94 as primary engine | Handles 10+ formats, MIT license, VLM pipeline |
| M1-D02 | 2026-05-21 | Exclude old Office formats (.doc/.xls/.ppt) | No reliable pure-Python parser; LibreOffice would add 300MB dep |
| M1-D03 | 2026-05-21 | PDF 3-engine choice: Docling/Marker/MinerU | User preference for PDF quality; Docling + VLM covers rest |
| M1-D04 | 2026-05-21 | OCR: PaddleOCR default > SuryaOCR > EasyOCR > Tesseract | Chinese text is primary; PaddleOCR leads Chinese benchmarks |
| M1-D05 | 2026-05-21 | GPU tiered recommendation (4 levels) | vLLM Linux-only; Windows needs Transformers path |
| M1-D06 | 2026-05-21 | Standalone Web UI = single-file HTML + FastAPI | No React build step; zero-dependency deployment |
| M1-D07 | 2026-05-21 | Table quality gate: 3-level complexity scoring | Accuracy-first principle; complex tables must be human-reviewed |
| M1-D08 | 2026-05-21 | Per-document output directory with relative paths | Portable, self-contained, human-browsable |
| M1-D09 | 2026-05-21 | 5 metadata fields auto-extracted, remainder manual | Regex works for predictable patterns; domain expertise needed for rest |
| M1-D10 | 2026-05-21 | Accuracy-first: no complex content enters VectorStore until reviewed | Non-negotiable quality requirement |
| M1-D11 | 2026-05-21 | FileFormat as str+Enum mixin, magic bytes priority over extension | F-string/JSON friendly; ZIP-based formats (DOCX/XLSX/PPTX) share PK magic and need extension fallback |

---

## 4. Known Pitfalls & Gotchas

1. **Docling editable install on Windows**: Same `src/` → `m1_parser/` layout issue as M2. Use conventional `m1_parser/` directory name.
2. **GBK encoding on Chinese Windows**: Need `# -*- coding: utf-8 -*-` on files with non-ASCII chars.
3. **PaddleOCR-VL-1.5 needs 4.2GB VRAM (native) or 230MB (INT8)**: Must check VRAM before recommending native mode.
4. **vLLM Linux-only**: Cannot test full GPU pipeline on Windows dev machine. Use Transformers engine for local dev, vLLM for production.
5. **TableFormer accuracy drops on borderless tables**: Chinese classification society documents often use borderless layouts.
6. **Meilisearch filter syntax vs ChromaDB where clause**: Metadata filter conversion needed when storing chunks in both backends.

---

## 5. Interface Contract Deviations

> *No deviations yet. Will follow contracts/document.py ParsedDocument format.*

---

## 6. Performance Notes

| Operation | Expected Performance (RTX 2060) | Notes |
|-----------|-------------------------------|-------|
| PDF text-only page | ~5 pages/sec | Standard Pipeline, no OCR |
| PDF scanned page | ~1-2 pages/sec | With EasyOCR GPU |
| PDF VLM (GraniteDocling-258M) | ~0.5 pages/sec | Transformers engine, Windows |
| DOCX conversion | ~10 pages/sec | SimplePipeline, no OCR |

> Production benchmarks TBD when run on target Linux + large GPU machine.

---

## 7. Open Issues

1. **VLM models on Windows**: Need to test which VLM presets work with Transformers engine on Windows. GraniteDocling-258M is the safest bet (small, cross-platform).
2. **SuryaOCR GPL license**: If used as default, imposes GPL obligations on the project. Currently only a backup option.
3. **Table LLM semantic layer**: Which model to use for the optional Layer 4 (footnote expansion, cross-table context)? Local vs API decision pending.
4. **Marker/MinerU installation complexity**: Both require additional Python packages (PyTorch, PDF-Extract-Kit). Need to document install steps clearly.
