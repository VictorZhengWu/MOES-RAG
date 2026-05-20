# Docling v2.94 功能参考手册

> **日期**：2026-05-21 | **来源**：Docling 官方文档 + 46 个示例
> **版本**：v2.94 (2026-05-18 release)
> **许可证**：MIT | **开发方**：IBM Research Zurich, LF AI & Data Foundation

---

## 一、概述

Docling 是一个开源文档处理工具，将多种格式的文档解析为统一的 `DoclingDocument` 表示，支持导出 Markdown、HTML、JSON、DocTags 等格式。本地运行，无云依赖。

**核心流程**：`输入文件 → Backend(格式解析) → Pipeline(处理阶段) → DoclingDocument → Serialization/Chunking → 输出`

---

## 二、输入格式支持

### 文档格式

| 格式 | 说明 |
|------|------|
| PDF | 主要格式，支持多种解析后端 |
| DOCX | Office 格式 |
| PPTX | 演示文稿，按页解析 |
| XLSX | 电子表格，保留 Sheet/行列 |
| HTML / XHTML | 网页格式 |
| Markdown | 及 .qmd / .Rmd 变体 |
| AsciiDoc | 结构化技术文档 |
| LaTeX | 科学文档 |
| CSV | 逗号分隔表格 |

### 图像格式（内置 OCR）

| 格式 | 说明 |
|------|------|
| PNG, JPEG, TIFF, BMP, WEBP | 图像格式，6 种 OCR 引擎可选 |

### 音视频格式（需 `asr` 扩展）

| 格式 | 说明 |
|------|------|
| WAV, MP3, M4A, AAC, OGG, FLAC | 音频转录（Whisper） |
| MP4, AVI, MOV | 视频（提取音轨 + 转录） |
| WebVTT | 定时文本 |

### 专业格式

| 格式 | 说明 |
|------|------|
| USPTO XML | 美国专利 |
| JATS XML | 学术文章 |
| XBRL XML | 商业报告 |

---

## 三、输出格式

| 格式 | 方法/类型 | 说明 |
|------|---------|------|
| **Markdown** | `export_to_markdown()` | 含标题、表格、图片占位符 |
| **HTML** | `export_to_html()` / `HTMLDocSerializer` | 完整 HTML 结构 |
| **JSON** | `export_to_dict()` | DoclingDocument 无损序列化 |
| **纯文本** | `export_to_text()` | 去掉 Markdown 标记 |
| **DocTags** | `export_to_doctags()` | 布局特征标记格式 |
| **WebVTT** | 定时文本格式 | 用于音频/视频转录输出 |

---

## 四、文档转换核心 API

### 4.1 最小示例

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("path/to/file.pdf")
print(result.document.export_to_markdown())
```

### 4.2 自定义转换参数

```python
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True
pipeline_options.do_table_structure = True
pipeline_options.images_scale = 2.0
pipeline_options.generate_page_images = True
pipeline_options.generate_picture_images = True

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)
```

### 4.3 批量转换

```python
conv_results = converter.convert_all(
    input_doc_paths,
    raises_on_error=False,  # 失败不中断
)
for result in conv_results:
    if result.status == ConversionStatus.SUCCESS:
        result.document.save_as_markdown(f"output/{name}.md")
        result.document.save_as_json(f"output/{name}.json")
```

### 4.4 多格式混合处理

```python
converter = DocumentConverter(
    allowed_formats=[
        InputFormat.PDF, InputFormat.DOCX, InputFormat.IMAGE,
        InputFormat.HTML, InputFormat.PPTX, InputFormat.CSV, InputFormat.MD,
    ],
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        InputFormat.DOCX: WordFormatOption(pipeline_cls=SimplePipeline),
    }
)
```

---

## 五、OCR 引擎配置

### 5.1 6 种 OCR 引擎

```python
# EasyOCR (默认)
pipeline_options.ocr_options = EasyOcrOptions(lang=["en", "zh"])

# Tesseract CLI
pipeline_options.ocr_options = TesseractCliOcrOptions(lang=["auto"])

# Tesseract 库
pipeline_options.ocr_options = TesseractOcrOptions(lang=["eng+chi_sim"])

# RapidOCR — 可指定自定义 ONNX 模型
pipeline_options.ocr_options = RapidOcrOptions(
    det_model_path="/path/to/det.onnx",
    rec_model_path="/path/to/rec.onnx",
    cls_model_path="/path/to/cls.onnx",
)

# SuryaOCR — 需安装 docling-surya，GPL 许可证
pipeline_options.ocr_options = SuryaOcrOptions(lang=["en"])

# macOS Vision
pipeline_options.ocr_options = OcrMacOptions()
```

### 5.2 全页面 OCR（扫描件模式）

```python
pipeline_options.do_ocr = True
pipeline_options.force_full_page_ocr = True  # 每页纯 OCR，不用布局检测
```

### 5.3 自动语言检测（Tesseract）

```python
TesseractCliOcrOptions(lang=["auto"])
```

---

## 六、VLM Pipeline（视觉大模型）

### 6.1 本地模型

```python
from docling.pipeline.vlm_pipeline import VlmPipeline
from docling.datamodel.pipeline_options import VlmPipelineOptions, VlmConvertOptions

# 方式 1：默认（自动选 GraniteDocling）
converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_cls=VlmPipeline)
    }
)

# 方式 2：使用预设 + 运行时引擎
vlm_options = VlmConvertOptions.from_preset("granite_docling")
pipeline_options = VlmPipelineOptions(vlm_options=vlm_options)
```

### 6.2 远程 API 模型

```python
from docling.datamodel.pipeline_options import ApiVlmEngineOptions, VlmEngineType

# Ollama（本地推理服务器）
vlm_options = VlmConvertOptions.from_preset(
    "granite_docling",
    engine_options=ApiVlmEngineOptions(
        runtime_type=VlmEngineType.API_OLLAMA,
        timeout=90,
    ),
)

# OpenAI
vlm_options = VlmConvertOptions.from_preset(
    "got_ocr",
    engine_options=ApiVlmEngineOptions(
        runtime_type=VlmEngineType.API_OPENAI,
    ),
)
```

### 6.3 VLM Presets 列表

**输出 DocTags 格式：** `granite_docling`, `smoldocling`
**输出 Markdown 格式：** `deepseek_ocr`, `granite_vision`, `pixtral`, `got_ocr`, `phi4`, `qwen`, `nanonets_ocr2`, `gemma_12b`, `gemma_27b`, `dolphin`

---

## 七、Layout / 表格 / 图片处理

### 7.1 布局模型选择

```python
pipeline_options.layout_model = "docling-layout-heron"  # 默认（快）
# 备选：docling-layout-egret-medium/large/xlarge（更准但更慢）
```

### 7.2 表格识别

```python
pipeline_options.do_table_structure = True
pipeline_options.table_structure_options.do_cell_matching = True  # 单元格匹配
# TableFormer 模式
pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE  # 精确
# 或 TableFormerMode.FAST  # 快速
```

### 7.3 导出表格为 DataFrame / CSV / HTML

```python
import pandas as pd

for idx, table in enumerate(result.document.tables):
    df = table.export_to_dataframe(doc=result.document)
    df.to_csv(f"table-{idx+1}.csv")
    with open(f"table-{idx+1}.html", "w") as f:
        f.write(table.export_to_html(doc=result.document))
```

### 7.4 导出图片

```python
for element, _level in result.document.iterate_items():
    if isinstance(element, PictureItem):
        with open(f"pic-{counter}.png", "wb") as fp:
            element.get_image(result.document).save(fp, "PNG")
```

### 7.5 多模态导出（文本 + 图片 + 坐标 → Parquet）

```python
from docling.utils.export import generate_multimodal_pages

pipeline_options.generate_page_images = True
for content_text, content_md, df, cells, segments, page in \
    generate_multimodal_pages(result.document):
    # 每页含有：文本、Markdown、DataFrame、单元格、片段、页面图片
```

---

## 八、Chunking（文本分块）

### 8.1 Hybrid Chunker（推荐）

```python
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

tokenizer = HuggingFaceTokenizer(
    tokenizer=AutoTokenizer.from_pretrained("BAAI/bge-small-en-v1.5"),
    max_tokens=512,
)

chunker = HybridChunker(
    tokenizer=tokenizer,
    merge_peers=True,          # 合并过小的相邻块
    repeat_table_header=True,  # 表格跨块重复表头
)

chunks = list(chunker.chunk(dl_doc=result.document))
for chunk in chunks:
    contextualized = chunker.contextualize(chunk=chunk)
    # contextualized = 标题层级前缀 + 分块内容（适合 RAG 嵌入）
```

### 8.2 Line-Based Token Chunker

```python
from docling_core.transforms.chunker.line_chunker import LineBasedTokenChunker

chunker = LineBasedTokenChunker(
    tokenizer=tokenizer,
    prefix="| Name | Age |\n|------|-----|\n",
    omit_prefix_on_overflow=False,
)
chunks = chunker.chunk_text(lines)
```

### 8.3 OpenAI Tokenizer

```python
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
import tiktoken

tokenizer = OpenAITokenizer(
    tokenizer=tiktoken.encoding_for_model("gpt-4o"),
    max_tokens=8192,
)
```

---

## 九、Enrichments（增强功能）

### 9.1 图片分类

```python
pipeline_options.do_picture_classification = True
# 自动识别：图表类型、流程图、Logo、签名等
```

### 9.2 图片描述（本地模型）

```python
pipeline_options.do_picture_description = True
pipeline_options.picture_description_options = granite_picture_description
pipeline_options.picture_description_options.prompt = \
    "Describe this image in three sentences."
```

### 9.3 图片描述（API 模型）

```python
picture_desc_options = PictureDescriptionVlmEngineOptions.from_preset(
    "granite_vision",
    engine_options=ApiVlmEngineOptions(
        runtime_type=VlmEngineType.API_LMSTUDIO,
        timeout=90,
    ),
)
pipeline_options.picture_description_options = picture_desc_options
pipeline_options.enable_remote_services = True
```

### 9.4 代码识别

```python
pipeline_options.do_code_enrichment = True
# 检测代码块并标记编程语言
```

### 9.5 公式提取

```python
pipeline_options.do_formula_enrichment = True
# 识别数学公式并导出 LaTeX
```

### 9.6 图表理解（v2.94 新功能）

自动识别柱状图/饼图/折线图 → 转换为表格数据/代码/文字描述。

### 9.7 自定义 Enrichment 模型

```python
class MyCustomModel(BaseItemAndImageEnrichmentModel):
    def is_processable(self, doc, element):
        return isinstance(element, PictureItem)
    
    def __call__(self, doc, element_batch):
        # 处理批次并写回 element.meta
        pass
```

---

## 十、GPU 加速

### 10.1 Standard Pipeline GPU

```python
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions

pipeline_options = PdfPipelineOptions()
pipeline_options.accelerator_options = AcceleratorOptions(
    device=AcceleratorDevice.CUDA,  # 或 CPU / MPS / AUTO
    num_threads=8,
)
pipeline_options.layout_batch_size = 64  # GPU 批处理
pipeline_options.ocr_batch_size = 4
```

**性能参考**：RTX 5090 → 7.9 pages/sec (Standard), RTX 5070 → ~3.5 pages/sec (VLM)

### 10.2 VLM Pipeline GPU（vLLM）

```bash
# 启动 vLLM 模型服务器
vllm serve ibm-granite/granite-docling-258M \
  --host 127.0.0.1 --port 8000 \
  --max-num-seqs 512 --gpu-memory-utilization 0.9
```

```python
# Docling 客户端配置
vlm_options = VlmConvertOptions.from_preset(
    "granite_docling",
    engine_options=ApiVlmEngineOptions(
        runtime_type=VlmEngineType.API,
        url="http://localhost:8000/v1/chat/completions",
        concurrency=64,
    ),
)
```

---

## 十一、信息提取（Structured Extraction）

```python
from docling_core.transforms.extraction import DocumentExtractor

# 定义提取模板（Pydantic）
class Invoice(BaseModel):
    bill_no: str
    total: float
    sender: str
    date: str

extractor = DocumentExtractor(allowed_input_formats=[InputFormat.IMAGE, InputFormat.PDF])
results = []
for page in document.pages:
    extracted = extractor.extract(page=page, template=Invoice)
    invoice = Invoice.model_validate(extracted.extracted_data)
    results.append(invoice)
# 支持：string template / dict template / Pydantic model
```

---

## 十二、PII 脱敏

```python
# 使用 GLiNER 引擎检测：人名/邮件/护照/SSN/电话号码/地址/公司
# 生成稳定的类型化占位符：person-1, org-2, email-1
pipeline_options.do_pii_obfuscation = True
```

---

## 十三、翻译

Docling 不内置翻译引擎，但通过元素遍历 + 外部翻译 API 实现：

```python
for element in result.document.iterate_items():
    if isinstance(element, TextItem):
        element.text = translate(element.text)  # 接入任何翻译 API
    if isinstance(element, TableItem):
        for cell in element.table_cells:
            cell.text = translate(cell.text)
result.document.save_as_markdown("translated.md")
```

---

## 十四、Visual Grounding（可视化溯源）

分步实现：
1. 转换时保留页面图片（`generate_page_images=True`）
2. 存储 DoclingDocument JSON（含 bounding boxes）
3. RAG 检索后，在返回的 chunk 中提取 `doc_items` 的坐标
4. 在原页面图片上画框标注引用位置

---

## 十五、Serialization（序列化）

```python
# HTML
from docling_core.transforms.serializer.html import HTMLDocSerializer
html = HTMLDocSerializer(doc=doc).serialize().text

# Markdown（可自定义表格/图片序列化器）
serializer = MarkdownDocSerializer(
    doc=doc,
    table_serializer=MarkdownTableSerializer(),
    picture_serializer=IndexedMarkdownPictureSerializer(),
    params=MarkdownParams(image_placeholder="<!-- image_{index} -->"),
)
md = serializer.serialize().text
```

---

## 十六、RAG 集成

| 框架 | 包名 | 关键组件 |
|------|------|---------|
| **LangChain** | `langchain-docling` | `DoclingLoader` + `HybridChunker` |
| **LlamaIndex** | `llama-index-readers-docling` | `DoclingReader` + `DoclingNodeParser` |
| **Haystack** | `docling-haystack` | `DoclingConverter` |
| **向量数据库** | Qdrant / Milvus / Weaviate / OpenSearch / MongoDB / Azure Search | 直接集成 |

---

## 十七、CLI 独立工具

```bash
# 基础用法
docling input.pdf --output ./output/

# 指定格式
docling input.pdf --from pdf --to md --output ./output/

# 使用 VLM
docling input.pdf --pipeline vlm --output ./output/
```

---

## 十八、对 M1 设计的关键启示

| Docling 功能 | M1 对应需求 | 实现方式 |
|-------------|-----------|---------|
| 多格式输入 | PDF/DOCX/XLSX/PPTX/HTML/图片 | Docling 直接处理 |
| OCR 引擎切换 | 扫描件识别 | 配置可选的 OCR 后端 |
| VLM Pipeline | 高精度 PDF 解析 | 替代 Marker/MinerU 时使用 |
| Enrichment | 船级社元数据提取 | 自定义 Picture Enrichment 模型 |
| Extraction | 表单/表格结构化提取 | Pydantic 模板提取 |
| Chunking | RAG 分块 | Hybrid Chunker + BGE Tokenizer |
| GPU 加速 | RTX 2060 加速 | `AcceleratorDevice.CUDA` |
| MCP Server | AI Agent 接入 | `docling-mcp` |
| CLI | 独立程序 | `docling` 命令 |
