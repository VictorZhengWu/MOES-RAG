# M1 文档解析引擎 — 详细设计规范

> **日期**：2026-05-21 | **状态**：待审批 | **依赖**：contracts/ (00010), M2 (00050)
> **参考**：`.dev/specs/docling-capabilities-reference-2026-05-21.md`

---

## 1. 模块定位

M1 是系统的文档解析引擎，位于 Layer 1 (Data)，将原始文件（PDF、Office、图片等）转换为结构化的 Markdown 文本块和元数据，供 M3/M4/M5 消费。

**核心原则**：

- **准确性第一** —— 复杂内容解析不确定时，阻止自动入库，强制人工审核
- **双模式运行** —— 既可作为系统模块被 M7 调用，也可作为独立 CLI/Web 工具
- **后端可插拔** —— PDF 解析可选 Docling / Marker / MinerU，管理员在 M7 配置

---

## 2. 模块目录结构

```
m1-doc-parsing/
├── m1_parser/
│   ├── __init__.py              # 公开 API 导出
│   ├── core/
│   │   ├── __init__.py
│   │   ├── converter.py         # 主转换器：文件 → DoclingDocument → ParsedDocument
│   │   ├── router.py            # 格式路由：判断文件类型 → 选择正确后端
│   │   ├── config.py            # 配置管理：GPU检测/后端选择/OCR引擎
│   │   └── quality.py           # 复杂度评分 + 质量门禁
│   │
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── docling_backend.py   # Docling 后端（默认，所有格式）
│   │   ├── marker_backend.py    # Marker 后端（PDF/图片备选）
│   │   └── mineru_backend.py    # MinerU 后端（PDF/图片备选）
│   │
│   ├── enrichments/
│   │   ├── __init__.py
│   │   ├── marine_metadata.py   # 船级社元数据自动提取
│   │   ├── table_annotator.py   # 复杂表格 Header-to-Cell 注释
│   │   └── table_merger.py      # 跨页表格合并
│   │
│   ├── output/
│   │   ├── __init__.py
│   │   ├── serializer.py        # ParsedDocument → MD/JSON/HTML
│   │   ├── chunker.py           # Hybrid Chunker 封装
│   │   └── image_manager.py     # 图片提取/存储/元数据侧车
│   │
│   ├── standalone/
│   │   ├── __init__.py
│   │   ├── cli.py               # 独立 CLI：m1-parser
│   │   ├── web_server.py        # FastAPI 服务
│   │   └── web_ui.html          # 单文件上传+预览界面
│   │
│   └── integration/
│       ├── __init__.py
│       ├── m2_bridge.py          # M2 存储写入适配器
│       └── m7_api.py             # M7 审核界面 API
│
├── tests/
│   ├── conftest.py
│   ├── test_converter.py
│   ├── test_router.py
│   ├── test_config.py
│   ├── test_quality.py
│   ├── test_docling_backend.py
│   ├── test_marine_metadata.py
│   ├── test_table_annotator.py
│   ├── test_table_merger.py
│   ├── test_serializer.py
│   ├── test_chunker.py
│   ├── test_image_manager.py
│   ├── test_cli.py
│   └── test_m2_bridge.py
│
├── requirements.txt
└── pyproject.toml
```

---

## 3. 架构设计

### 3.1 双层架构

```
┌──────────────────────────────────────────────────┐
│                  M1 文档解析引擎                    │
│                                                    │
│  ┌─────────────────────┐  ┌────────────────────┐  │
│  │   Standalone 模式     │  │   Module 模式       │  │
│  │                     │  │                    │  │
│  │  CLI: m1-parser     │  │  M7 管理后台调用    │  │
│  │  Web UI: 上传+预览   │  │  审核工作流集成     │  │
│  └──────────┬──────────┘  └─────────┬──────────┘  │
│             │                       │              │
│             └───────────┬───────────┘              │
│                         │                          │
│              ┌──────────▼───────────┐              │
│              │    解析核心 (Core)     │              │
│              │                      │              │
│              │  converter.py       │              │
│              │  router.py          │              │
│              │  quality.py         │              │
│              │  元数据提取          │              │
│              │  表格注释            │              │
│              └──────────┬──────────┘              │
│                         │                          │
│         ┌───────────────┼───────────────┐          │
│         │               │               │          │
│    ┌────▼────┐    ┌─────▼─────┐   ┌────▼────┐     │
│    │ Docling  │    │  Marker   │   │ MinerU  │     │
│    │(所有格式) │    │(PDF备选)  │   │(PDF备选)│     │
│    └─────────┘    └───────────┘   └─────────┘     │
│                                                    │
│  输入: PDF/DOCX/XLSX/PPTX/HTML/图片                 │
│  输出: ParsedDocument (Markdown + 元数据 + 图片)     │
└──────────────────────────────────────────────────┘
```

### 3.2 解析管线（6 阶段）

```
输入文件
    │
    ▼
阶段 1: 格式路由 (router.py)
    │  magic bytes 嗅探 + 扩展名确认
    │  分类: PDF/IMAGE → 3后端可选 | DOCX/XLSX/PPTX/HTML → Docling
    │
    ▼
阶段 2: 结构解析 (backends/)
    │  Docling/Marker/MinerU 解析
    │  输出: DoclingDocument (文本 + 表格 + 图片 + 坐标)
    │
    ▼
阶段 3: 元数据提取 (enrichments/marine_metadata.py)
    │  自动提取: classification_society, regulation_name,
    │            version_year, chapter_section, language
    │
    ▼
阶段 4: 表格增强 (enrichments/table_annotator.py + table_merger.py)
    │  跨页表格合并 → Header-to-Cell 注释 → 复杂度评分
    │
    ▼
阶段 5: 质量门禁 (quality.py)
    │  简单 → 自动通过 → 写入 M2 VectorStore
    │  复杂 → 阻止入库 → M7 通知人工审核
    │
    ▼
阶段 6: 输出序列化 (output/)
    │  ParsedDocument → Markdown / JSON / HTML
    │  图片提取 + 元数据侧车
    │  Hybrid Chunker → RAG 分块
```

---

## 4. 文件格式支持

### 4.1 输入格式

| 格式 | 解析引擎 | OCR 需求 | 说明 |
|------|---------|:---:|------|
| PDF（电子版） | Docling Standard / VLM | ❌ | 文字可选，直接提取 |
| PDF（扫描件） | Docling + OCR / VLM | ✅ | 图片型 PDF |
| DOCX | Docling | ❌ | 原生文本 + 样式 |
| XLSX | Docling | ❌ | Sheet → Markdown Table |
| PPTX | Docling | ❌ | 按页 Markdown |
| HTML/HTM | Docling | ❌ | 直接解析 |
| JPG/PNG/TIFF/BMP | Docling + OCR / VLM | ✅ | 纯图像需 OCR |

### 4.2 输出格式

| 格式 | 用途 |
|------|------|
| **Markdown** | 默认输出，人可读，RAG 嵌入 |
| **JSON (ParsedDocument)** | 程序化消费，完整元数据 |
| **HTML** | 富文本预览（含图片内嵌） |
| **DocTags** | Docling 原生标记格式 |

---

## 5. PDF 解析引擎选择

### 5.1 引擎对比

| 引擎 | 类型 | 中文精度 | 速度 | 许可证 | 需 GPU？ |
|------|------|:---:|------|--------|:---:|
| Docling Standard | 传统 Pipeline | ⭐⭐⭐ | 快 | MIT | 可选 |
| Docling VLM (PaddleOCR-VL) | VLM 端到端 | ⭐⭐⭐⭐⭐ | 中 | Apache 2.0 | ✅ |
| Docling VLM (DeepSeek-OCR 2) | VLM 端到端 | ⭐⭐⭐⭐ | 中 | MIT | ✅ |
| Docling VLM (GraniteDocling) | VLM 端到端 | ⭐⭐⭐ | 快 | Apache 2.0 | 可选 |
| Marker | 独立引擎 | ⭐⭐⭐⭐ | 中 | GPL | ✅ |
| MinerU | 独立引擎 | ⭐⭐⭐⭐⭐ | 慢 | Apache 2.0 | ✅ |

### 5.2 用户选择方式

M7 管理后台提供 PDF 引擎下拉选择：

```
PDF 解析引擎: [Docling Standard ▾]
  · Docling Standard (默认，通用)
  · Docling VLM — PaddleOCR-VL-1.5 (中文最优)
  · Docling VLM — DeepSeek-OCR 2 (高效率)
  · Docling VLM — GraniteDocling-258M (轻量)
  · Marker (独立引擎)
  · MinerU (独立引擎)
```

### 5.3 GPU 自动检测与配置推荐

```python
# config.py — 启动时执行
def detect_hardware() -> HardwareProfile:
    gpu_available = torch.cuda.is_available()
    if gpu_available:
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        return HardwareProfile(
            gpu=True, vram_gb=vram_gb,
            recommended_backend=(
                "paddleocr_vl" if vram_gb >= 8 else "granite_docling"
            ),
            recommended_ocr="paddleocr",
            can_use_vllm=(platform.system() == "Linux"),
        )
    else:
        return HardwareProfile(
            gpu=False, vram_gb=0,
            recommended_backend="docling_standard",
            recommended_ocr="easyocr",
            can_use_vllm=False,
        )
```

**分层推荐逻辑**：

```
检测 GPU?
  ├─ 是 → VRAM ≥ 8GB?
  │       ├─ 是 + Linux → vLLM + PaddleOCR-VL-1.5（最快）
  │       ├─ 是 + Windows → Transformers + GraniteDocling-258M
  │       └─ 否 (6GB) → INT8 量化 PaddleOCR-VL 或 Standard Pipeline
  └─ 否 → Docling Standard + EasyOCR / Tesseract
```

---

## 6. OCR 引擎配置

### 6.1 引擎对比

| 引擎 | 印刷体 | 手写体 | 中文 | 速度 | 许可证 |
|------|:---:|:---:|:---:|------|--------|
| PaddleOCR PP-OCRv4 | 97.1% | 82.5% | ⭐⭐⭐⭐⭐ | 85-140 ppm | Apache 2.0 |
| SuryaOCR | 97.5% | 85.3% | ⭐⭐⭐⭐ | 42-72 ppm | GPL 3.0 |
| EasyOCR | 94.8% | 76.5% | ⭐⭐⭐ | 55-92 ppm | Apache 2.0 |
| Tesseract | 92-95% | 42-59% | ⭐⭐ | CPU 2-3s/页 | Apache 2.0 |

### 6.2 推荐配置

```
默认: PaddleOCR ← 中文最好，船级社规范大量中文
备选: SuryaOCR  ← 复杂表格/扫描质量差时用（注意 GPL 许可）
兜底: EasyOCR   ← 前两者安装失败时的保底方案
特殊: Tesseract ← 纯英文、纯 CPU 环境
```

---

## 7. 海洋工程领域元数据提取

### 7.1 自动提取字段

| 字段 | 提取方式 | 人工可修改 |
|------|---------|:---:|
| `classification_society` | 正则: `DNV\|ABS\|CCS\|LR\|BV\|NK\|RINA\|KR` | ✅ |
| `regulation_name` | 文件名 + 文档标题匹配 | ✅ |
| `version_year` | 正则: `(20\d{2}\|19\d{2})` | ✅ |
| `chapter_section` | 正则: `Pt\.?\s*\d+\|Ch\.?\s*\d+\|§\s*[\d.]+` | ✅ |
| `language` | langdetect 语言检测 | ✅ |

剩余字段（`domain`, `vessel_types`, `system_type`, `manufacturer`, `equipment_model`）由管理员在 M7 手动标注。

### 7.2 Docling Enrichment 集成

创建自定义 `MarineMetadataEnricher(BaseItemAndImageEnrichmentModel)`：

```python
class MarineMetadataEnricher:
    def is_processable(self, doc, element):
        return isinstance(element, TextItem)
    
    def __call__(self, doc, element_batch):
        for element in element_batch:
            element.meta.classification_society = detect_society(element.text)
            element.meta.version_year = detect_year(element.text)
            # ... 其他字段
```

---

## 8. 复杂表格处理

### 8.1 四层处理管线

```
Layer 1: TableFormer 结构检测   → 行列、合并单元格、跨页
Layer 2: Cell Text 内容提取     → 每个单元格文本
Layer 3: Header-to-Cell 注释    → 规则引擎关联表头
Layer 4: LLM 语义理解（可选）   → 脚注引用展开、跨表格理解
```

### 8.2 跨页表格合并

```python
def merge_split_tables(tables: list[TableItem]) -> list[TableItem]:
    """
    策略:
    1. 检测当前页表格缺少表头行
    2. 向前回溯，找到同名表格的头行
    3. 复用表头注释当前页单元格
    """
```

### 8.3 复杂度评分

| 检测项 | 加分 | 说明 |
|--------|:---:|------|
| 合并单元格 > 3 | +1 | Docling TableFormer 检测 |
| 跨页表格（无表头） | +2 | 需回溯合并 |
| 含 `(see ...)` 引用 | +2 | 外部脚注引用 |
| 含括号注释 | +1 | `(t ≤ 50mm)` 等 |
| 有脚注标记 | +1 | 注释在表格外 |
| 列数 > 8 或行数 > 50 | +1 | 大表格 |
| 无边框表格 | +1 | 最易漏识别 |

**门禁规则**：

```
得分 0   → ✅ 自动通过，直接入库
得分 1-2 → ⚠️ 自动通过，confidence 标记 < 1.0
得分 3+  → 🛑 阻止入库，强制 M7 人工审核
```

### 8.4 ParsedDocument 置信度字段

```python
@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: DocumentMetadata
    chunk_type: str
    confidence: float = 1.0        # 1.0=完全可信, <0.8=需审核
    review_required: bool = False   # True=阻止自动入库
    review_reasons: list[str] = []  # ["跨页表格", "脚注引用"]
```

---

## 9. 图片存储规则

### 9.1 目录结构（每个文档一个独立目录）

```
output/{doc_id}/
├── full.md                    # Markdown 主文件
├── full.json                  # ParsedDocument JSON
├── pages/                     # 页面截图 (144 DPI, PNG)
│   ├── page_001.png
│   └── page_002.png
├── figures/                   # 内嵌图片 (原格式保留)
│   ├── figure_001.png
│   └── figure_001.png.meta.json
└── tables/                    # 表格截图 (144 DPI, PNG)
    └── table_001.png
```

### 9.2 图片分类

| 图片来源 | 保存格式 | 分辨率 | 说明 |
|---------|---------|--------|------|
| 页面渲染 | PNG | 144 DPI (scale=2.0) | 预览+Visual Grounding |
| 内嵌图片 | 原格式 | 原始分辨率 | 避免二次损失 |
| 表格渲染 | PNG | 144 DPI | 线条文字需无损 |

### 9.3 图片元数据侧车

```json
{
  "source_doc": "dnv_pt4_ch3_2024.pdf",
  "page_number": 12,
  "bbox": [120, 340, 580, 720],
  "type": "diagram",
  "classification": { "label": "engineering_drawing", "confidence": 0.93 },
  "description": "Welding procedure qualification flow chart",
  "caption": "Fig. 3.1",
  "extracted_at": "2026-05-21T10:30:00Z"
}
```

### 9.4 Markdown 引用

```markdown
<!-- full.md 内部，使用相对路径 -->
![页面1](pages/page_001.png)
![焊接流程图](figures/figure_001.png)
```

---

## 10. M2 集成

### 10.1 4 个后端的使用分配

| M2 后端 | M1 写入内容 | M3/M4/M5 读取方式 |
|---------|-----------|-----------------|
| **RelationalDB** | `m1_documents` 表（文档目录）, `m1_parsing_tasks` 表（任务状态） | SQL 查询文档列表 |
| **VectorStore** | Chunks 向量 + 元数据（自动通过的才写入） | 语义相似搜索 |
| **DocumentIndex** | Chunks 全文索引 | 关键词搜索 |
| **FileStore** | full.md, full.json, pages/*, figures/*, tables/* | 下载预览 |

### 10.2 数据库表结构

```sql
CREATE TABLE m1_documents (
    doc_id          TEXT PRIMARY KEY,
    original_name   TEXT NOT NULL,
    original_size   INTEGER,
    file_type       TEXT,
    output_dir      TEXT,
    markdown_path   TEXT,
    json_path       TEXT,
    status          TEXT DEFAULT 'pending',
    error_message   TEXT,
    page_count      INTEGER,
    chunk_count     INTEGER,
    figure_count    INTEGER,
    table_count     INTEGER,
    classification_society TEXT,
    regulation_name       TEXT,
    version_year          INTEGER,
    chapter_section       TEXT,
    language              TEXT,
    parsed_at       TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE m1_parsing_tasks (
    task_id         TEXT PRIMARY KEY,
    doc_id          TEXT REFERENCES m1_documents(doc_id),
    backend         TEXT,
    ocr_engine      TEXT,
    status          TEXT DEFAULT 'queued',
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP,
    progress        REAL DEFAULT 0.0
);
```

---

## 11. Standalone Web 界面

极简单页工具，FastAPI + 单文件 HTML，零构建步骤。

```
┌─────────────────────────────────────────────┐
│  M1 Document Parser                    [?]  │
├─────────────────────────────────────────────┤
│   ┌───────────────────────────────────┐     │
│   │   拖放文件到这里，或点击选择        │     │
│   │   支持: PDF DOCX XLSX PPTX        │     │
│   │         HTML JPG PNG TIFF BMP     │     │
│   └───────────────────────────────────┘     │
│                                              │
│   解析引擎: [Docling ▾]                      │
│   OCR引擎:  [Auto ▾]                         │
│   输出格式: [☑ Markdown] [☐ JSON]            │
│                                              │
│   [开始解析]                                  │
│                                              │
├─────────────────────────────────────────────┤
│  解析结果预览                                 │
│  ┌─────────────────────────────────────┐    │
│  │ # DNV Rules Pt.4 Ch.3              │    │
│  │ ## Section 1: General Requirements │    │
│  │ ...                                 │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  [下载 Markdown] [下载 JSON]                 │
└─────────────────────────────────────────────┘
```

---

## 12. M7 审核界面

```
┌──────────────────────────────────────────────────┐
│  待审核: DNV Pt.4 Ch.3 — Table 3-1              │
│  复杂度: 5 (跨页 + 合并单元格 + 脚注引用)         │
│                                                   │
│  原始页面截图:            AI 解析结果:             │
│  ┌──────────────────┐   ┌──────────────────────┐  │
│  │ [PDF原文渲染]     │   │ | Grade | Preheat... │  │
│  └──────────────────┘   └──────────────────────┘  │
│                                                   │
│  🔴 2 个单元格被标记为不确定                        │
│                                                   │
│  [修改]  [确认无误]  [跳过]                        │
└──────────────────────────────────────────────────┘
```

---

## 13. 开发决策记录

| ID | 日期 | 决策 |
|----|------|------|
| M1-D01 | 2026-05-21 | Docling v2.94 为主要引擎，Marker/MinerU 为 PDF 备选 |
| M1-D02 | 2026-05-21 | 排除旧 Office 格式（.doc/.xls/.ppt），仅处理新格式 |
| M1-D03 | 2026-05-21 | PDF 可选 Standard Pipeline 或 VLM Pipeline（PaddleOCR-VL/DeepSeek-OCR 2/GraniteDocling） |
| M1-D04 | 2026-05-21 | OCR 引擎：PaddleOCR(默认) > SuryaOCR(备选) > EasyOCR(兜底) > Tesseract(CPU) |
| M1-D05 | 2026-05-21 | GPU 自动检测 + 分层推荐（Linux+vLLM / Windows+Transformers / CPU+EasyOCR） |
| M1-D06 | 2026-05-21 | Standalone Web UI 为极简单页（FastAPI + 单文件 HTML），不依赖 M6/M7 |
| M1-D07 | 2026-05-21 | 复杂表格三级质量门禁（得分 0→通过, 1-2→低置信度, 3+→强制审核） |
| M1-D08 | 2026-05-21 | 图片存储：每文档独立目录，pages/figures/tables 子目录，Markdown 相对路径引用 |
| M1-D09 | 2026-05-21 | 元数据自动提取 5 字段，管理员可在 M7 修改 |
| M1-D10 | 2026-05-21 | 准确性优先——复杂内容未审核通过前不得进入向量数据库 |

---

*设计规范结束。待审批后生成实现计划。*
