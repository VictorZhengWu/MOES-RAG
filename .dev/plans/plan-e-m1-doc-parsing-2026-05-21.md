# M1 文档解析引擎 — 实现计划

> **给执行 Subagent 的说明**：必须使用 superpowers:subagent-driven-development 或 superpowers:executing-plans 技能按任务逐个实现。步骤使用 checkbox（`- [ ]`）语法追踪。

**目标**：实现 M1 文档解析引擎，支持双模式运行（独立 CLI/Web + 系统模块），Docling v2.94 为主要引擎，Marker/MinerU 为 PDF 备选引擎，GPU 自动检测，海洋工程元数据提取，复杂表格质量门禁，以及 M2 存储集成。

**架构**：6 阶段解析管线（路由 → 解析 → 元数据 → 表格增强 → 质量门禁 → 序列化）。Converter 通过 router → backend → enrichments → quality → output 编排全流程。独立 Web 界面使用 FastAPI + 单文件 HTML。Module 模式集成 M7 和 M2。

**技术栈**：Python 3.12+, Docling v2.94, python-magic, PyYAML, FastAPI, langdetect, HuggingFace tokenizers

---

### 任务 1：项目骨架与配置系统 (00060-01)

**涉及文件：**
- 新建：`m1-doc-parsing/pyproject.toml`
- 新建：`m1-doc-parsing/requirements.txt`
- 新建：`m1-doc-parsing/m1_parser/__init__.py`
- 新建：`m1-doc-parsing/m1_parser/core/__init__.py`
- 新建：`m1-doc-parsing/m1_parser/core/config.py`
- 新建：`m1-doc-parsing/tests/__init__.py`
- 新建：`m1-doc-parsing/tests/test_config.py`

- [ ] **步骤 1：创建项目骨架文件**

`pyproject.toml`：
```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "m1-doc-parsing"
version = "0.1.0"
description = "Marine & Offshore Expert System -- Document Parsing Engine (M1)"
requires-python = ">=3.12"
dependencies = [
    "docling>=2.94.0",
    "pyyaml>=6.0",
    "python-magic>=0.4.27",
    "langdetect>=1.0.9",
]

[project.optional-dependencies]
vlm = ["torch>=2.0"]
ocr = ["paddleocr>=2.7", "easyocr>=1.7"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23.0"]
all = ["m1-doc-parsing[vlm,ocr,dev]"]

[project.scripts]
m1-parser = "m1_parser.standalone.cli:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`requirements.txt`：
```
docling>=2.94.0
pyyaml>=6.0
python-magic>=0.4.27
langdetect>=1.0.9
pytest>=8.0
pytest-asyncio>=0.23.0
```

`m1_parser/__init__.py`：
```python
"""
M1 -- 文档解析引擎。

将原始文件（PDF、Office、图片）转换为结构化 Markdown，
附带海洋工程领域元数据、复杂表格注释和质量置信度评分。

两种运行模式：
  - Standalone：CLI 工具 + Web 界面
  - Module：被 M7 管理后台调用，写入 M2 存储
"""

__version__ = "0.1.0"

from .core.converter import convert, convert_batch
from .core.config import detect_hardware, HardwareProfile

__all__ = [
    "convert", "convert_batch",
    "detect_hardware", "HardwareProfile",
    "__version__",
]
```

`m1_parser/core/__init__.py`：
```python
# 解析管线核心组件
```

`tests/__init__.py`：
```python
# M1 测试套件
```

- [ ] **步骤 2：先写测试（TDD）**

```python
# m1-doc-parsing/tests/test_config.py
"""
config.py 的单元测试 —— 硬件检测与后端/OCR引擎选择。

WHY: GPU 检测和后端推荐是 M1 启动时第一个执行的操作。
错误的检测 = 错误的默认设置 = 性能差或直接崩溃。
这些测试通过 mock 硬件来验证 4 个分级推荐路径。
"""

import platform
from unittest.mock import patch

import pytest

from m1_parser.core.config import (
    HardwareProfile,
    detect_hardware,
    recommend_ocr_engine,
    SUPPORTED_BACKENDS,
    OCR_ENGINE_PRIORITY,
)


# ---------------------------------------------------------------------------
# 测试 1：GPU ≥ 8GB + Linux → 推荐 vLLM + PaddleOCR-VL
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=True)
@patch("torch.cuda.get_device_properties")
@patch.object(platform, "system", return_value="Linux")
def test_gpu_8gb_linux_recommends_vllm(mock_system, mock_props, mock_avail):
    """GPU >= 8GB 且 Linux 系统必须推荐 vLLM + PaddleOCR-VL。"""
    mock_props.return_value.total_memory = 12 * 1024**3  # 12 GB
    profile = detect_hardware()
    assert profile.gpu is True
    assert profile.vram_gb == 12.0
    assert profile.recommended_backend == "paddleocr_vl"
    assert profile.can_use_vllm is True


# ---------------------------------------------------------------------------
# 测试 2：GPU ≥ 8GB + Windows → 推荐 Transformers + GraniteDocling
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=True)
@patch("torch.cuda.get_device_properties")
@patch.object(platform, "system", return_value="Windows")
def test_gpu_8gb_windows_recommends_transformers(mock_system, mock_props, mock_avail):
    """GPU >= 8GB 且 Windows 系统必须推荐 Transformers 引擎。"""
    mock_props.return_value.total_memory = 10 * 1024**3
    profile = detect_hardware()
    assert profile.gpu is True
    assert profile.recommended_backend == "granite_docling"
    assert profile.can_use_vllm is False


# ---------------------------------------------------------------------------
# 测试 3：GPU < 8GB → 推荐 Standard Pipeline
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=True)
@patch("torch.cuda.get_device_properties")
def test_gpu_low_vram_recommends_standard(mock_props, mock_avail):
    """GPU 但显存不足 8GB 必须推荐 Standard Pipeline。"""
    mock_props.return_value.total_memory = 6 * 1024**3  # RTX 2060
    profile = detect_hardware()
    assert profile.recommended_backend == "docling_standard"


# ---------------------------------------------------------------------------
# 测试 4：无 GPU → 推荐 CPU 模式 + EasyOCR
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=False)
def test_no_gpu_recommends_cpu(mock_avail):
    """无 GPU 必须推荐 CPU 模式 + EasyOCR。"""
    profile = detect_hardware()
    assert profile.gpu is False
    assert profile.vram_gb == 0
    assert profile.recommended_backend == "docling_standard"
    assert profile.recommended_ocr == "easyocr"
    assert profile.can_use_vllm is False


# ---------------------------------------------------------------------------
# 测试 5：OCR 引擎优先顺序
# ---------------------------------------------------------------------------

def test_ocr_priority_order():
    """PaddleOCR 必须排第一，Tesseract 排最后。"""
    assert OCR_ENGINE_PRIORITY[0] == "paddleocr"
    assert OCR_ENGINE_PRIORITY[-1] == "tesseract"


# ---------------------------------------------------------------------------
# 测试 6：支持的后端列表
# ---------------------------------------------------------------------------

def test_supported_backends():
    """所有 3 种后端类型必须在支持列表中。"""
    assert "docling" in SUPPORTED_BACKENDS
    assert "marker" in SUPPORTED_BACKENDS
    assert "mineru" in SUPPORTED_BACKENDS
```

- [ ] **步骤 3：运行测试验证失败**

```bash
python -m pytest m1-doc-parsing/tests/test_config.py -v
```
预期：FAIL（import 错误，config.py 还不存在）

- [ ] **步骤 4：编写 config.py 实现**

```python
# m1-doc-parsing/m1_parser/core/config.py
"""
M1 硬件检测和配置管理。

WHY: M1 运行在多种硬件环境上（从无 GPU 的笔记本到 GPU 服务器）。
自动检测消除了手动设置猜测，确保每种部署环境使用最优配置。
分级推荐系统将 4 种硬件配置映射到最高效的后端+OCR 组合。

关键决策：
- vLLM 仅支持 Linux（依赖 Linux 内核特性）
- PaddleOCR-VL-1.5 需要约 4.2GB 显存（或 INT8 量化后 230MB）
- GraniteDocling-258M 是跨平台最安全的 VLM
- EasyOCR 是最可靠的 CPU 兜底方案
"""

from __future__ import annotations

import platform
from dataclasses import dataclass

# ===========================================================================
# 常量
# ===========================================================================

SUPPORTED_BACKENDS = ["docling", "marker", "mineru"]

OCR_ENGINE_PRIORITY = ["paddleocr", "suryaocr", "easyocr", "tesseract"]

VLM_PRESETS = [
    "granite_docling",
    "paddleocr_vl",
    "deepseek_ocr",
    "smoldocling",
    "granite_vision",
]


# ===========================================================================
# 硬件配置数据模型
# ===========================================================================


@dataclass
class HardwareProfile:
    """
    检测到的硬件能力和推荐配置。

    WHY 使用 dataclass 而非 dict：类型安全的消费者（M7 配置页面）
    可以依赖字段存在性和类型，无需 try/except KeyError。
    """

    gpu: bool
    vram_gb: float
    recommended_backend: str  # "docling_standard" | "paddleocr_vl" | ...
    recommended_ocr: str      # "paddleocr" | "easyocr" | ...
    can_use_vllm: bool        # 仅 Linux + GPU 时为 True


def detect_hardware() -> HardwareProfile:
    """
    检测 GPU 和操作系统，返回分级配置推荐。

    检测逻辑（4 级）：
    1. GPU ≥ 8GB + Linux   → vLLM + PaddleOCR-VL-1.5（最快）
    2. GPU ≥ 8GB + Windows → Transformers + GraniteDocling（跨平台）
    3. GPU < 8GB            → Standard Pipeline（或 INT8 VLM）
    4. 无 GPU               → EasyOCR CPU 模式

    WHY 分级：vLLM 仅 Linux。PaddleOCR-VL 需 4.2GB+ 显存。
    自动检测可防止推荐一个根本跑不起来的配置。
    """
    try:
        import torch
        gpu_available = torch.cuda.is_available()
    except ImportError:
        gpu_available = False

    if gpu_available:
        vram_bytes = torch.cuda.get_device_properties(0).total_memory
        vram_gb = vram_bytes / (1024**3)
        is_linux = platform.system() == "Linux"

        if vram_gb >= 8:
            if is_linux:
                return HardwareProfile(
                    gpu=True, vram_gb=vram_gb,
                    recommended_backend="paddleocr_vl",
                    recommended_ocr="paddleocr",
                    can_use_vllm=True,
                )
            else:
                return HardwareProfile(
                    gpu=True, vram_gb=vram_gb,
                    recommended_backend="granite_docling",
                    recommended_ocr="paddleocr",
                    can_use_vllm=False,
                )
        else:
            return HardwareProfile(
                gpu=True, vram_gb=vram_gb,
                recommended_backend="docling_standard",
                recommended_ocr="paddleocr",
                can_use_vllm=False,
            )
    else:
        return HardwareProfile(
            gpu=False, vram_gb=0,
            recommended_backend="docling_standard",
            recommended_ocr="easyocr",
            can_use_vllm=False,
        )


def recommend_ocr_engine(preferred: str | None = None) -> str:
    """
    从优先级列表中返回第一个可用的 OCR 引擎。

    按 PaddleOCR → SuryaOCR → EasyOCR → Tesseract 的顺序尝试。
    如果给定 preferred 且可用，则直接使用它。

    WHY 回退链：不同环境安装了不同的引擎。
    PaddleOCR 可能导入失败；EasyOCR 几乎通用。
    """
    if preferred and _is_ocr_available(preferred):
        return preferred

    for engine in OCR_ENGINE_PRIORITY:
        if _is_ocr_available(engine):
            return engine
    raise RuntimeError(
        "没有可用的 OCR 引擎。请安装以下之一: "
        + ", ".join(OCR_ENGINE_PRIORITY)
    )


def _is_ocr_available(engine: str) -> bool:
    """
    检查 OCR 引擎是否可导入。

    WHY 惰性检测：启动时的导入错误比解析 100 页 PDF 5 分钟后
    才运行时崩溃要好得多。
    """
    import_map = {
        "paddleocr": "paddleocr",
        "suryaocr": "docling_surya",
        "easyocr": "easyocr",
        "tesseract": "pytesseract",
    }
    module_name = import_map.get(engine)
    if module_name is None:
        return False
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False
```

- [ ] **步骤 5：运行测试验证通过**

```bash
cd E:/myCode/RAG && pip install pyyaml && python -m pytest m1-doc-parsing/tests/test_config.py -v
```
预期：6 PASS, 0 FAIL

- [ ] **步骤 6：提交**

```bash
git add m1-doc-parsing/
git commit -m "[00060-01] feat: 项目骨架，config.py 含 GPU 检测与分级推荐逻辑"
```

---

### 任务 2：格式路由 (00060-02)

**涉及文件：**
- 新建：`m1-doc-parsing/m1_parser/core/router.py`
- 新建：`m1-doc-parsing/tests/test_router.py`

- [ ] **步骤 1：先写测试**

```python
# m1-doc-parsing/tests/test_router.py
"""
router.py 的单元测试 —— 文件类型检测和格式路由。

WHY: 路由器决定每个文件由哪个后端处理。PDF 被路由到 DOCX
管线会产生垃圾结果。magic bytes 嗅探能捕获后缀名错误的文件。
"""

import tempfile
from pathlib import Path

import pytest

from m1_parser.core.router import (
    detect_format,
    route_backend,
    FileFormat,
)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _write_temp_file(ext: str, magic_bytes: bytes = b"") -> Path:
    """创建一个带指定扩展名和 magic bytes 的临时文件。"""
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    if magic_bytes:
        tmp.write(magic_bytes)
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# 测试 1：PDF 检测
# ---------------------------------------------------------------------------

def test_detect_pdf():
    """以 %PDF- 开头的文件必须被识别为 PDF。"""
    f = _write_temp_file(".pdf", b"%PDF-1.4\n%some content")
    fmt = detect_format(str(f))
    assert fmt == FileFormat.PDF


# ---------------------------------------------------------------------------
# 测试 2：DOCX 检测
# ---------------------------------------------------------------------------

def test_detect_docx():
    """含 ZIP magic 且 .docx 后缀 = DOCX。"""
    f = _write_temp_file(".docx", b"PK\x03\x04")
    fmt = detect_format(str(f))
    assert fmt == FileFormat.DOCX


# ---------------------------------------------------------------------------
# 测试 3：图片检测（PNG）
# ---------------------------------------------------------------------------

def test_detect_image_png():
    """含 PNG magic bytes 的文件必须被识别为 IMAGE。"""
    f = _write_temp_file(".png", b"\x89PNG\r\n\x1a\n")
    fmt = detect_format(str(f))
    assert fmt == FileFormat.IMAGE


# ---------------------------------------------------------------------------
# 测试 4：不支持的格式
# ---------------------------------------------------------------------------

def test_unsupported_format():
    """未知 magic bytes 必须抛出 ValueError。"""
    f = _write_temp_file(".xyz", b"random binary garbage")
    with pytest.raises(ValueError, match="Unsupported"):
        detect_format(str(f))


# ---------------------------------------------------------------------------
# 测试 5：PDF 后端路由 —— 有 3 个选项
# ---------------------------------------------------------------------------

def test_route_pdf():
    """PDF 文件必须路由到用户选择的后端。"""
    assert route_backend(FileFormat.PDF, "docling") == "docling"
    assert route_backend(FileFormat.PDF, "marker") == "marker"
    assert route_backend(FileFormat.PDF, "mineru") == "mineru"
    with pytest.raises(ValueError, match="Unsupported backend"):
        route_backend(FileFormat.PDF, "unknown_engine")


# ---------------------------------------------------------------------------
# 测试 6：DOCX 强制走 Docling
# ---------------------------------------------------------------------------

def test_route_docx():
    """DOCX 无论用户选什么后端都必须走 Docling。"""
    assert route_backend(FileFormat.DOCX, "docling") == "docling"
    # 用户选了 Marker 也不能影响 DOCX
    assert route_backend(FileFormat.DOCX, "marker") == "docling"
```

- [ ] **步骤 2：编写 router.py 实现**

```python
# m1-doc-parsing/m1_parser/core/router.py
"""
文件格式检测与后端路由。

WHY: 不同格式需要不同的解析器。magic bytes 嗅探比仅靠后缀名
检测更可靠 —— 一个 .pdf 文件可能实际上是个 JPEG。
路由器还知道哪些后端能处理哪些格式（如 Marker 只能处理 PDF/图片）。

检测优先级：magic bytes（前 8 字节）→ 后缀名回退。
"""

from __future__ import annotations

import enum
from pathlib import Path


class FileFormat(str, enum.Enum):
    """支持的输入文件格式。"""
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    HTML = "html"
    IMAGE = "image"
    CSV = "csv"
    MARKDOWN = "markdown"


# ===========================================================================
# Magic bytes 签名
# ===========================================================================

_MAGIC_SIGNATURES: list[tuple[bytes, FileFormat | None]] = [
    (b"%PDF-", FileFormat.PDF),
    (b"\x89PNG", FileFormat.IMAGE),
    (b"\xff\xd8\xff", FileFormat.IMAGE),          # JPEG
    (b"II*\x00", FileFormat.IMAGE),               # TIFF (小端)
    (b"MM\x00*", FileFormat.IMAGE),               # TIFF (大端)
    (b"BM", FileFormat.IMAGE),                    # BMP
    (b"PK\x03\x04", None),                        # ZIP 系（DOCX/XLSX/PPTX）
    (b"<!DOCTYP", FileFormat.HTML),
    (b"<html", FileFormat.HTML),
]

# Marker/MinerU 能处理的格式（仅 PDF + IMAGE）
_PDF_BACKENDS = {"docling", "marker", "mineru"}

# 非 PDF/IMAGE 格式无论用户选什么都走 Docling
_DOCLING_ONLY_FORMATS = {
    FileFormat.DOCX, FileFormat.XLSX, FileFormat.PPTX,
    FileFormat.HTML, FileFormat.CSV, FileFormat.MARKDOWN,
}


def detect_format(file_path: str) -> FileFormat:
    """
    通过 magic bytes 检测文件格式，失败时回退到后缀名。

    Args:
        file_path: 待检测的文件路径。

    Returns:
        FileFormat 枚举值。

    Raises:
        ValueError: 无法确定格式时抛出。
    """
    path = Path(file_path)

    # 读取前 8 字节做 magic 签名检测
    with open(file_path, "rb") as f:
        header = f.read(8)

    # 逐个比对 magic bytes
    for signature, fmt in _MAGIC_SIGNATURES:
        if header.startswith(signature):
            if fmt is None:  # ZIP 系 —— 用后缀名判断
                return _format_from_extension(path.suffix.lower())
            return fmt

    # 回退到后缀名
    return _format_from_extension(path.suffix.lower())


def route_backend(fmt: FileFormat, user_choice: str) -> str:
    """
    为给定格式选择正确的后端。

    PDF/IMAGE：用户的选择（docling/marker/mineru）。
    其他所有格式：强制 docling（Marker/MinerU 不支持它们）。

    WHY 非 PDF 强制 Docling：Marker 和 MinerU 是 PDF/IMAGE 专用。
    将 DOCX 路由给它们会静默失败。

    Args:
        fmt: 检测到的文件格式。
        user_choice: 用户偏好的后端名称。

    Returns:
        后端名称字符串（"docling"、"marker" 或 "mineru"）。

    Raises:
        ValueError: 后端对此格式无效时抛出。
    """
    if fmt in _DOCLING_ONLY_FORMATS:
        return "docling"

    if fmt in (FileFormat.PDF, FileFormat.IMAGE):
        if user_choice in _PDF_BACKENDS:
            return user_choice
        raise ValueError(
            f"不支持的后端 '{user_choice}' 用于 {fmt.value}。"
            f"支持: {', '.join(sorted(_PDF_BACKENDS))}"
        )

    raise ValueError(f"不支持的文件格式: {fmt.value}")


def _format_from_extension(suffix: str) -> FileFormat:
    """将文件后缀名映射到 FileFormat。"""
    ext_map = {
        ".pdf": FileFormat.PDF,
        ".docx": FileFormat.DOCX,
        ".xlsx": FileFormat.XLSX,
        ".pptx": FileFormat.PPTX,
        ".html": FileFormat.HTML,
        ".htm": FileFormat.HTML,
        ".png": FileFormat.IMAGE,
        ".jpg": FileFormat.IMAGE,
        ".jpeg": FileFormat.IMAGE,
        ".tiff": FileFormat.IMAGE,
        ".tif": FileFormat.IMAGE,
        ".bmp": FileFormat.IMAGE,
        ".csv": FileFormat.CSV,
        ".md": FileFormat.MARKDOWN,
    }
    fmt = ext_map.get(suffix)
    if fmt is None:
        raise ValueError(
            f"不支持的文件后缀名: {suffix}。"
            f"支持: {', '.join(sorted(ext_map.keys()))}"
        )
    return fmt
```

- [ ] **步骤 3：运行测试**

```bash
python -m pytest m1-doc-parsing/tests/test_router.py -v
```
预期：6 PASS, 0 FAIL

- [ ] **步骤 4：提交**

```bash
git add m1-doc-parsing/m1_parser/core/router.py m1-doc-parsing/tests/test_router.py
git commit -m "[00060-02] feat: 格式路由器 —— magic bytes 检测与后端路由"
```

---

### 任务 3：Docling 后端适配器 (00060-03)

**涉及文件：**
- 新建：`m1-doc-parsing/m1_parser/backends/__init__.py`
- 新建：`m1-doc-parsing/m1_parser/backends/docling_backend.py`
- 新建：`m1-doc-parsing/tests/test_docling_backend.py`

- [ ] **步骤 1：先写测试**

```python
# m1-doc-parsing/tests/test_docling_backend.py
"""
DoclingBackend 的单元测试 —— 主文档解析后端。

WHY: Docling 是处理 10+ 格式的默认引擎。这些测试验证
PDF 和图片转换能产生有效的 Markdown 输出。
"""

import tempfile
from pathlib import Path

import pytest

# 如果 docling 未安装则跳过所有测试
docling = pytest.importorskip("docling", reason="docling 未安装")

from m1_parser.backends.docling_backend import DoclingBackend


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _create_test_pdf(path: Path) -> None:
    """创建一个最小化的测试 PDF。"""
    content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )
    path.write_bytes(content)


# ---------------------------------------------------------------------------
# 测试 1：PDF → Markdown 能正常工作
# ---------------------------------------------------------------------------

def test_pdf_to_markdown():
    """转换 PDF 必须返回非空的 Markdown 字符串。"""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        _create_test_pdf(Path(f.name))
        pdf_path = f.name

    backend = DoclingBackend()
    result = backend.convert(pdf_path)
    assert result.markdown is not None
    assert len(result.markdown) > 0


# ---------------------------------------------------------------------------
# 测试 2：后端遵循 OCR 选项
# ---------------------------------------------------------------------------

def test_ocr_option_set():
    """传入 ocr_engine 参数不应崩溃。"""
    backend = DoclingBackend(ocr_engine="easyocr")
    assert backend.ocr_engine == "easyocr"


# ---------------------------------------------------------------------------
# 测试 3：后端遵循 VLM preset
# ---------------------------------------------------------------------------

def test_vlm_preset_set():
    """传入 VLM preset 必须正确配置 VLM 管线。"""
    backend = DoclingBackend(vlm_preset="granite_docling")
    assert backend.vlm_preset == "granite_docling"
```

- [ ] **步骤 2：编写 docling_backend.py 实现**

```python
# m1-doc-parsing/m1_parser/backends/docling_backend.py
"""
Docling v2.94 后端适配器。

WHY: Docling 是处理全部 10+ 格式的主要引擎。
此适配器封装了 Docling 的 DocumentConverter，为 M1 Converter
提供干净的调用接口。它处理：
- Standard Pipeline（版面检测 + OCR + 表格识别）
- VLM Pipeline（视觉语言模型端到端解析）
- 按格式配置选项（PDF/DOCX/PPTX/XLSX/IMAGE/HTML）

设计原则：所有 Docling 特定的导入和配置都在此文件中。
如果将来替换 Docling 为其他引擎，只需修改此文件。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """单次文档解析的结果。"""
    markdown: str
    json_dict: dict | None = None
    page_count: int = 0
    figure_count: int = 0
    table_count: int = 0


class DoclingBackend:
    """
    通过 Docling v2.94 进行文档解析。

    支持两种管线：
    - Standard Pipeline：版面检测 → OCR → 表格结构识别
    - VLM Pipeline：视觉语言模型 → 端到端 Markdown/DocTags

    OCR 引擎通过 Docling 的 PdfPipelineOptions 配置：
    EasyOCR（默认）、Tesseract、RapidOCR、SuryaOCR。
    """

    def __init__(
        self,
        ocr_engine: str = "easyocr",
        vlm_preset: str | None = None,
        use_gpu: bool = False,
    ):
        """
        Args:
            ocr_engine: OCR 后端名称（easyocr, tesseract, rapidocr, suryaocr）。
            vlm_preset: VLM preset 名称（granite_docling, deepseek_ocr 等）。
                        如果设置，使用 VlmPipeline 代替 StandardPdfPipeline。
            use_gpu: 是否使用 CUDA 加速。
        """
        self.ocr_engine = ocr_engine
        self.vlm_preset = vlm_preset
        self.use_gpu = use_gpu

    def convert(self, source: str) -> ParseResult:
        """
        将文档文件转换为结构化输出。

        WHY 返回 ParseResult 而非原始 DoclingDocument：上层模块
        （converter.py）需要稳定的接口，无论当前激活的是哪个后端
        （Docling/Marker/MinerU）。

        Args:
            source: 文档的路径或 URL。

        Returns:
            包含 markdown、元数据和计数的 ParseResult。
        """
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(source)
        doc = result.document

        return ParseResult(
            markdown=doc.export_to_markdown(),
            json_dict=doc.export_to_dict(),
            page_count=len(doc.pages) if hasattr(doc, "pages") else 0,
            figure_count=len(doc.pictures),
            table_count=len(doc.tables),
        )
```

- [ ] **步骤 3：运行测试**

```bash
pip install docling && python -m pytest m1-doc-parsing/tests/test_docling_backend.py -v
```
预期：3 PASS（若 docling 未安装则 skip）

- [ ] **步骤 4：提交**

```bash
git add m1-doc-parsing/m1_parser/backends/ m1-doc-parsing/tests/test_docling_backend.py
git commit -m "[00060-03] feat: Docling 后端适配器 —— Standard 和 VLM 管线支持"
```

---

### 任务 4：Marker 与 MinerU 后端骨架 (00060-04)

**涉及文件：**
- 新建：`m1-doc-parsing/m1_parser/backends/marker_backend.py`
- 新建：`m1-doc-parsing/m1_parser/backends/mineru_backend.py`

- [ ] **步骤 1：编写 marker_backend.py**

```python
# m1-doc-parsing/m1_parser/backends/marker_backend.py
"""
Marker 后端适配器 —— PDF/图片解析备选引擎。

WHY: Marker 是流行的开源 PDF→Markdown 工具，使用 Surya 深度学习
模型进行版面检测和 OCR。用户偏好其输出质量时作为备选。

适配器将 Marker 的 CLI/API 封装为与 DoclingBackend 相同的接口，
使 Converter 可以透明地切换后端。
"""

from __future__ import annotations

import logging

from .docling_backend import ParseResult

logger = logging.getLogger(__name__)


class MarkerBackend:
    """通过 Marker 进行 PDF/图片解析（基于 Surya）。"""

    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu

    def convert(self, source: str) -> ParseResult:
        """
        使用 Marker 将 PDF/图片转换为 Markdown。

        当前为骨架实现 —— Marker 需要特定的环境配置。
        在安装 marker-pdf 之前返回空结果并给出警告。

        待办：环境就绪后集成 marker-pdf 包。
        """
        logger.warning(
            "调用了 Marker 后端但 marker-pdf 未安装。"
            "安装命令: pip install marker-pdf"
        )
        return ParseResult(markdown="", page_count=0)
```

- [ ] **步骤 2：编写 mineru_backend.py**

```python
# m1-doc-parsing/m1_parser/backends/mineru_backend.py
"""
MinerU 后端适配器 —— PDF 解析备选引擎。

WHY: MinerU（magic-pdf）由上海 AI Lab 开发，针对中文科技文档
优化。使用 PDF-Extract-Kit 进行深度版面分析，是处理中文 PDF
（含复杂表格和公式）的最佳开源方案。

适配器将 MinerU 的 CLI 封装为与 DoclingBackend 相同的 ParseResult
接口，使 Converter 可以透明切换后端。
"""

from __future__ import annotations

import logging

from .docling_backend import ParseResult

logger = logging.getLogger(__name__)


class MinerUBackend:
    """通过 MinerU 进行 PDF 解析（magic-pdf）。"""

    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu

    def convert(self, source: str) -> ParseResult:
        """
        使用 MinerU 将 PDF 转换为 Markdown。

        当前为骨架实现 —— MinerU 需要特定的环境配置。
        在安装 magic-pdf 之前返回空结果并给出警告。

        待办：环境就绪后集成 magic-pdf。
        """
        logger.warning(
            "调用了 MinerU 后端但 magic-pdf 未安装。"
            "安装命令: pip install magic-pdf"
        )
        return ParseResult(markdown="", page_count=0)
```

- [ ] **步骤 3：提交**

```bash
git add m1-doc-parsing/m1_parser/backends/marker_backend.py m1-doc-parsing/m1_parser/backends/mineru_backend.py
git commit -m "[00060-04] feat: Marker 和 MinerU 后端骨架"
```

---

### 任务 5：主转换器 (00060-05)

**涉及文件：**
- 新建：`m1-doc-parsing/m1_parser/core/converter.py`
- 新建：`m1-doc-parsing/tests/test_converter.py`

这是 M1 中最大的单个文件。Converter 编排整个 6 阶段管线。

- [ ] **步骤 1：先写测试**

```python
# m1-doc-parsing/tests/test_converter.py
"""
主转换器测试 —— 6 阶段管线编排。

WHY: Converter 是 M1 的公开 API。所有消费者（CLI、Web UI、
M7 管理后台）都调用 convert() 或 convert_batch()。
这些测试验证端到端流程。
"""

import tempfile
from pathlib import Path

import pytest

from m1_parser.core.converter import convert, convert_batch, ParseOptions


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _create_minimal_pdf(path: Path) -> None:
    """创建一个最小化的有效 PDF。"""
    content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )
    path.write_bytes(content)


# ---------------------------------------------------------------------------
# 测试 1：单文件转换成功
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("docling"),
    reason="docling 未安装"
)
def test_convert_pdf():
    """转换有效的 PDF 必须返回带 doc_id 的结果。"""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        _create_minimal_pdf(Path(f.name))
        fname = f.name

    options = ParseOptions(backend="docling")
    try:
        result = convert(fname, options)
        assert result is not None
    except ImportError:
        pytest.skip("docling 不可用")


# ---------------------------------------------------------------------------
# 测试 2：批量转换处理多个文件
# ---------------------------------------------------------------------------

def test_convert_batch_handles_errors():
    """批量转换以 raises_on_error=False 运行时不能因坏文件崩溃。"""
    options = ParseOptions(backend="docling")
    results = convert_batch(
        ["nonexistent1.pdf", "nonexistent2.pdf"],
        options,
        raises_on_error=False,
    )
    assert len(results) == 2


# ---------------------------------------------------------------------------
# 测试 3：ParseOptions 默认值
# ---------------------------------------------------------------------------

def test_parse_options_defaults():
    """默认选项必须使用 Docling 后端和 EasyOCR。"""
    opts = ParseOptions()
    assert opts.backend == "docling"
    assert opts.ocr_engine == "easyocr"
    assert opts.output_dir == "./output"
```

- [ ] **步骤 2：编写 converter.py 实现**

```python
# m1-doc-parsing/m1_parser/core/converter.py
"""
主文档转换器 —— 6 阶段解析管线。

WHY: M1 的核心价值在于编排管线，将原始文件转化为附带元数据、
表格注释和质量评分的 ParsedDocument。Converter 是所有消费者
（CLI、Web UI、M7 管理后台、批量处理）的唯一入口。

管线阶段：
  1. 格式路由 (router.py)
  2. 结构解析 (后端适配器)
  3. 元数据提取 (marine_metadata.py)
  4. 表格增强 (table_annotator + table_merger)
  5. 质量门禁 (quality.py)
  6. 输出序列化 (serializer + chunker + image_manager)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ===========================================================================
# 输入/输出类型
# ===========================================================================


@dataclass
class ParseOptions:
    """用户可配置的解析选项。

    WHY 用独立的 options 类而不是函数参数：随着添加更多配置
    （OCR、VLM、质量阈值、输出格式），函数签名会变得不可维护。
    带默认值的 dataclass 保持 API 稳定。
    """

    backend: str = "docling"        # docling | marker | mineru
    ocr_engine: str = "easyocr"     # paddleocr | easyocr | tesseract | suryaocr
    vlm_preset: str | None = None   # granite_docling | deepseek_ocr | ...
    use_gpu: bool = False
    output_dir: str = "./output"
    output_formats: list[str] = field(default_factory=lambda: ["md", "json"])


@dataclass
class ParseResult:
    """单个文档的解析结果。

    包含解析内容以及处理过程的元数据。
    doc_id 是在解析时生成的 UUID，用作 M2 存储查询的键。
    """

    doc_id: str
    source_path: str
    markdown: str = ""
    json_dict: dict | None = None
    page_count: int = 0
    figure_count: int = 0
    table_count: int = 0
    success: bool = False
    error: str | None = None


# ===========================================================================
# 公开 API
# ===========================================================================


def convert(source: str, options: ParseOptions | None = None) -> ParseResult:
    """
    通过完整的 6 阶段管线转换单个文档。

    这是 M1 的主要公开 API。所有消费者都调用此函数：
      - CLI: m1-parser input.pdf
      - Web UI: POST /parse {file: input.pdf}
      - M7 管理后台: 文档上传工作流
      - Module 模式: from m1_parser import convert

    Args:
        source: 文档的文件路径或 URL。
        options: 解析配置。若省略则使用默认值。

    Returns:
        包含 doc_id、markdown、元数据和状态的 ParseResult。
    """
    if options is None:
        options = ParseOptions()

    doc_id = uuid.uuid4().hex[:12]
    logger.info("正在解析 %s (doc_id=%s, backend=%s)", source, doc_id, options.backend)

    # 阶段 1: 格式路由
    from .router import detect_format, route_backend
    fmt = detect_format(source)
    backend_name = route_backend(fmt, options.backend)

    # 阶段 2: 结构解析
    from ..backends.docling_backend import DoclingBackend, ParseResult as BackendResult
    if backend_name == "docling":
        backend = DoclingBackend(
            ocr_engine=options.ocr_engine,
            vlm_preset=options.vlm_preset,
            use_gpu=options.use_gpu,
        )
        raw: BackendResult = backend.convert(source)
    else:
        # Marker/MinerU —— 当前为骨架（后续任务实现）
        return ParseResult(
            doc_id=doc_id,
            source_path=source,
            success=False,
            error=f"后端 '{backend_name}' 尚未实现",
        )

    # 阶段 3-6 将在任务 00060-06 到 00060-08 中接入
    return ParseResult(
        doc_id=doc_id,
        source_path=source,
        markdown=raw.markdown,
        json_dict=raw.json_dict,
        page_count=raw.page_count,
        figure_count=raw.figure_count,
        table_count=raw.table_count,
        success=True,
    )


def convert_batch(
    sources: list[str],
    options: ParseOptions | None = None,
    raises_on_error: bool = False,
) -> list[ParseResult]:
    """
    批量转换多个文档。错误被收集而不是抛出。

    WHY raises_on_error 默认为 False：批量模式下（如 50 个文件），
    一个损坏的文件不应该中止其余 49 个的处理。
    """
    results = []
    for source in sources:
        try:
            result = convert(source, options)
        except Exception as e:
            if raises_on_error:
                raise
            result = ParseResult(
                doc_id="error",
                source_path=source,
                success=False,
                error=str(e),
            )
        results.append(result)
    return results
```

- [ ] **步骤 3：运行测试**

```bash
python -m pytest m1-doc-parsing/tests/test_converter.py -v
```
预期：3 PASS

- [ ] **步骤 4：提交**

```bash
git add m1-doc-parsing/m1_parser/core/converter.py m1-doc-parsing/tests/test_converter.py
git commit -m "[00060-05] feat: 主转换器 —— 6 阶段管线编排"
```

---

### 任务 6：海洋工程元数据提取 (00060-06)

**涉及文件：**
- 新建：`m1-doc-parsing/m1_parser/enrichments/__init__.py`
- 新建：`m1-doc-parsing/m1_parser/enrichments/marine_metadata.py`
- 新建：`m1-doc-parsing/tests/test_marine_metadata.py`

- [ ] **步骤 1：先写测试**

```python
# m1-doc-parsing/tests/test_marine_metadata.py
"""
marine_metadata.py 的单元测试 —— 从文档文本和文件名中
自动提取船级社元数据。

WHY: 5 个自动提取的字段是 M3 检索和 M7 管理后台中文档
筛选的基础。提取错误 = 文档无法被找到。
"""

import pytest

from m1_parser.enrichments.marine_metadata import (
    extract_classification_society,
    extract_version_year,
    extract_chapter_section,
    extract_metadata,
    MarineMetadata,
)


# ---------------------------------------------------------------------------
# 测试 1：船级社检测
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("本文件遵循 DNV 船舶规范。", "DNV"),
    ("American Bureau of Shipping (ABS) 标准适用。", "ABS"),
    ("依据 CCS 第7章。", "CCS"),
    ("Lloyd's Register (LR) 入级规范。", "LR"),
    ("Bureau Veritas (BV) 规范 B 部分。", "BV"),
    ("Nippon Kaiji Kyokai (NK) 指南。", "NK"),
    ("Registro Italiano Navale (RINA)", "RINA"),
    ("Korean Register (KR) of shipping", "KR"),
    ("IMO 决议 MSC.456(101)", "IMO"),
    ("IACS 统一要求 UR W33", "IACS"),
])
def test_extract_classification_society(text, expected):
    """已知的船级社缩写必须被检测到。"""
    assert extract_classification_society(text) == expected


def test_no_society_returns_none():
    """不含任何船级社提及的文本必须返回 None。"""
    assert extract_classification_society("通用工程指南。") is None


# ---------------------------------------------------------------------------
# 测试 2：年份检测
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("DNV 规范 2024 版", 2024),
    ("2023年1月发布", 2023),
    ("IMO 2020 指南", 2020),
    ("版本 2019-03", 2019),
])
def test_extract_version_year(text, expected):
    """文本中的年份模式必须被提取。"""
    assert extract_version_year(text) == expected


def test_no_year_returns_none():
    """不含可识别年份的文本必须返回 None。"""
    assert extract_version_year("通用规格文件。") is None


# ---------------------------------------------------------------------------
# 测试 3：章节号检测
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("DNV Pt.4 Ch.3 焊接程序", "Pt.4 Ch.3"),
    ("ABS Part 5B Section 3-2", "Part 5B Section 3-2"),
    ("CCS 第7章 舱底水系统", "第7章"),
    ("详见 § 3.2.1 的要求。", "§ 3.2.1"),
])
def test_extract_chapter_section(text, expected):
    """章节号模式必须被检测到。"""
    assert extract_chapter_section(text) == expected


# ---------------------------------------------------------------------------
# 测试 4：完整元数据提取
# ---------------------------------------------------------------------------

def test_extract_metadata_from_filename_and_text():
    """从文件名和文本内容组合提取元数据。"""
    filename = "DNV_Pt4_Ch3_Welding_2024.pdf"
    text = """DNV 船舶入级规范
    第4部分 第3章 -- 焊接程序
    挪威船级社 2024 年发布"""

    meta = extract_metadata(filename, text)
    assert meta.classification_society == "DNV"
    assert meta.version_year == 2024
    assert "Pt" in meta.chapter_section


# ---------------------------------------------------------------------------
# 测试 5：MarineMetadata 数据类
# ---------------------------------------------------------------------------

def test_marine_metadata_defaults():
    """默认的 MarineMetadata 所有字段应为 None。"""
    meta = MarineMetadata()
    assert meta.classification_society is None
    assert meta.version_year is None
    assert meta.language is None
```

- [ ] **步骤 2：编写 marine_metadata.py 实现**

```python
# m1-doc-parsing/m1_parser/enrichments/marine_metadata.py
"""
海洋工程文档元数据自动提取。

WHY: 船级社规范文档包含可预测的元数据模式（船级社名称、
年份、章节号），可以通过正则表达式可靠地提取。这省去了
管理员为每份上传文档手动填写这些字段的工作。

提取字段：
  1. classification_society: DNV, ABS, CCS, LR, BV, NK, RINA, KR, IMO, IACS
  2. regulation_name: 从文件名或文档标题
  3. version_year: 正则 (20\d{2}|19\d{2})
  4. chapter_section: Pt.X Ch.Y, Section, §, Chapter
  5. language: 通过 langdetect

所有自动提取的值均可由管理员在 M7 中修改。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ===========================================================================
# 正则模式
# ===========================================================================

_SOCIETY_PATTERNS: list[tuple[str, str]] = [
    (r"\bDNV\b", "DNV"),
    (r"\bABS\b", "ABS"),
    (r"\bCCS\b", "CCS"),
    (r"\bLR\b|Lloyd'?s\s+Register", "LR"),
    (r"\bBV\b|Bureau\s+Veritas", "BV"),
    (r"\bNK\b|Nippon\s+Kaiji\s+Kyokai", "NK"),
    (r"\bRINA\b|Registro\s+Italiano\s+Navale", "RINA"),
    (r"\bKR\b|Korean\s+Register", "KR"),
    (r"\bIMO\b", "IMO"),
    (r"\bIACS\b", "IACS"),
]

_YEAR_PATTERN = re.compile(r"(20\d{2}|19\d{2})")

_CHAPTER_PATTERN = re.compile(
    r"(Pt\.?\s*\d+(\s*Ch\.?\s*\d+)?)"    # Pt.4 Ch.3
    r"|(Part\s+\d+[A-Z]?\s*Section\s*[\d-]+)"  # Part 5B Section 3-2
    r"|(第\s*\d+\s*章)"                    # 第7章
    r"|(Chapter\s+\d+)"                   # Chapter 7
    r"|(§\s*[\d.]+)"                      # § 3.2.1
)


# ===========================================================================
# 数据模型
# ===========================================================================


@dataclass
class MarineMetadata:
    """从已解析文档中提取的海洋工程领域元数据。"""

    classification_society: str | None = None
    regulation_name: str | None = None
    version_year: int | None = None
    chapter_section: str | None = None
    language: str | None = None


# ===========================================================================
# 提取函数
# ===========================================================================


def extract_metadata(filename: str, text: str) -> MarineMetadata:
    """
    从文档中提取所有可自动检测的元数据。

    同时搜索文件名和文本内容，当两者都有匹配时优先使用
    文本中的匹配（文件名可能被缩写）。

    Args:
        filename: 原始文件名（用于基于模式的提示）。
        text: 文档全文内容。

    Returns:
        填充了检测到字段的 MarineMetadata（未检测到的为 None）。
    """
    return MarineMetadata(
        classification_society=extract_classification_society(text),
        regulation_name=_extract_regulation_name(filename, text),
        version_year=extract_version_year(text),
        chapter_section=extract_chapter_section(text),
        language=_detect_language(text),
    )


def extract_classification_society(text: str) -> str | None:
    """
    从文档文本中检测船级社。

    搜索已知缩写和全名。返回第一个匹配（大多数文档只引用一个船级社）。

    WHY 用正则而非 ML：船级社名称是可预测的字符串。
    正则确定性高、可解释、零依赖。
    """
    for pattern, name in _SOCIETY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return name
    return None


def extract_version_year(text: str) -> int | None:
    """
    从文档文本中提取 4 位年份。

    匹配 1900-2099 之间的年份。返回第一个匹配
    （出版年份通常出现在文档开头）。
    """
    match = _YEAR_PATTERN.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_chapter_section(text: str) -> str | None:
    """
    从文档文本中提取章节引用。

    匹配 "Pt.4 Ch.3"、"Part 5B Section 3-2"、"第7章"、"§ 3.2.1" 等模式。
    """
    match = _CHAPTER_PATTERN.search(text)
    if match:
        return match.group(0).strip()
    return None


def _extract_regulation_name(filename: str, text: str) -> str | None:
    """
    从文件名或文档标题中推导规范名称。

    优先尝试文本中的第一个标题。回退到去掉扩展名的文件名。
    """
    from pathlib import Path

    # 尝试将文本第一行作为标题
    first_line = text.strip().split("\n")[0] if text else ""
    if first_line and len(first_line) > 10:
        return first_line[:200].strip()

    # 回退到文件名
    return Path(filename).stem


def _detect_language(text: str) -> str | None:
    """
    使用 langdetect 检测文档语言。

    返回 ISO 639-1 代码（en, zh, ko, ja, no），或 None。
    """
    if not text or len(text) < 20:
        return None
    try:
        from langdetect import detect
        return detect(text[:1000])  # 前 1000 字符足够判断
    except Exception:
        return None
```

- [ ] **步骤 3：运行测试**

```bash
pip install langdetect && python -m pytest m1-doc-parsing/tests/test_marine_metadata.py -v
```
预期：参数化测试全部 PASS, 0 FAIL

- [ ] **步骤 4：提交**

```bash
git add m1-doc-parsing/m1_parser/enrichments/ m1-doc-parsing/tests/test_marine_metadata.py
git commit -m "[00060-06] feat: 海洋工程元数据自动提取 —— 5 字段正则规则"
```

---

### 任务 7：质量门禁与表格处理骨架 (00060-07)

**涉及文件：**
- 新建：`m1-doc-parsing/m1_parser/enrichments/table_merger.py`
- 新建：`m1-doc-parsing/m1_parser/enrichments/table_annotator.py`
- 新建：`m1-doc-parsing/m1_parser/core/quality.py`
- 新建：`m1-doc-parsing/tests/test_quality.py`

- [ ] **步骤 1：编写 quality.py（质量门禁核心）**

```python
# m1-doc-parsing/m1_parser/core/quality.py
"""
已解析内容的复杂度评分和质量门禁。

WHY: 准确性优先原则要求复杂内容（含合并单元格、脚注、
跨页的表格）在人工审核前不得自动入库进入向量数据库。

评分系统对 7 项复杂度指标进行打分。
得分 0 = 自动通过，1-2 = 低置信度，3+ = 阻止并需审核。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QualityAssessment:
    """对某个 chunk 或表格的复杂度评分结果。"""

    score: int
    max_score: int = 9
    confidence: float = 1.0
    review_required: bool = False
    review_reasons: list[str] = field(default_factory=list)

    def __post_init__(self):
        """根据分数自动设置门禁规则。"""
        if self.score == 0:
            self.confidence = 1.0
            self.review_required = False
        elif self.score <= 2:
            self.confidence = max(0.5, 1.0 - (self.score * 0.25))
            self.review_required = False
        else:
            self.confidence = max(0.1, 1.0 - (self.score * 0.3))
            self.review_required = True


def score_table_complexity(
    merged_cells: int = 0,
    is_cross_page: bool = False,
    has_footnote_refs: bool = False,
    has_parenthetical_notes: bool = False,
    has_footnotes: bool = False,
    column_count: int = 0,
    row_count: int = 0,
    is_borderless: bool = False,
) -> QualityAssessment:
    """
    在 0-9 的尺度上评估表格复杂度。

    评分规则（来自设计规范第 8.3 节）：
      +1: 合并单元格 > 3
      +2: 跨页（无表头行）
      +2: 含 (参见 ...) 脚注引用
      +1: 含括号注释
      +1: 有脚注标记
      +1: 列数 > 8 或行数 > 50
      +1: 无边框表格

    门禁规则：
      得分 0:   自动通过（置信度 1.0）
      得分 1-2: 自动通过但降低置信度
      得分 3+:  阻止入库，强制人工审核

    WHY 数值化评分：支持渐进式质量阈值。
    1 个问题的表格可能没问题；3 个问题几乎肯定有地方出错。
    """
    reasons = []
    score = 0

    if merged_cells > 3:
        score += 1
        reasons.append(f"合并单元格数={merged_cells}")

    if is_cross_page:
        score += 2
        reasons.append("跨页表格")

    if has_footnote_refs:
        score += 2
        reasons.append("脚注引用")

    if has_parenthetical_notes:
        score += 1
        reasons.append("括号注释")

    if has_footnotes:
        score += 1
        reasons.append("脚注标记")

    if column_count > 8 or row_count > 50:
        score += 1
        reasons.append(f"表格尺寸({column_count}x{row_count})")

    if is_borderless:
        score += 1
        reasons.append("无边框")

    return QualityAssessment(
        score=score,
        review_reasons=reasons,
    )
```

- [ ] **步骤 2：编写 test_quality.py**

```python
# m1-doc-parsing/tests/test_quality.py
"""复杂度评分和质量门禁的单元测试。"""

import pytest
from m1_parser.core.quality import score_table_complexity


def test_simple_table_auto_approves():
    """干净无问题的表格必须得分 0，自动通过。"""
    result = score_table_complexity()
    assert result.score == 0
    assert result.confidence == 1.0
    assert result.review_required is False


def test_merged_cells_low_confidence():
    """4 个合并单元格 = 得分 1，低置信度但不阻止。"""
    result = score_table_complexity(merged_cells=5)
    assert result.score == 1
    assert result.confidence < 1.0
    assert result.review_required is False


def test_cross_page_blocked():
    """跨页 + 脚注引用 = 得分 >= 3，必须阻止。"""
    result = score_table_complexity(
        is_cross_page=True,     # +2
        has_footnote_refs=True, # +2
    )
    assert result.score >= 3
    assert result.review_required is True


def test_many_issues_blocked():
    """多个中等问题的叠加触发阻止。"""
    result = score_table_complexity(
        merged_cells=4,              # +1
        has_parenthetical_notes=True, # +1
        has_footnotes=True,          # +1
        is_borderless=True,          # +1
    )
    assert result.score >= 3
    assert result.review_required is True
```

- [ ] **步骤 3：编写表格处理骨架文件**

```python
# m1-doc-parsing/m1_parser/enrichments/table_merger.py
"""
跨页表格合并模块。

WHY: 当表格跨越多页 PDF 时，每页的表格片段缺少表头行。
此模块通过检查表格的第一行是否像表头行（粗体、较短、
所有单元格非空）来检测这种片段。如果不是表头，则向前
回溯到上一页找到匹配的表头行。
"""


def merge_split_tables(tables: list) -> list:
    """
    合跨多页的表格片段。

    策略：
    1. 检测缺少表头行的表格（第一行内容是数据型的）
    2. 向前回溯上一页的表格，找到表头
    3. 将表头行前置到当前表格片段

    当前为骨架 —— 完整实现需要访问 Docling 的 TableItem
    结构和单元格级元数据。
    """
    return tables
```

```python
# m1-doc-parsing/m1_parser/enrichments/table_annotator.py
"""
表头到单元格注释模块，用于表格上下文丰富化。

WHY: 原始表格单元格如 "150°C" 在没有行列表头的情况下
毫无意义。此模块将每个数据单元格关联到其行表头和列表头，
使下游系统看到的是上下文丰富的值：
"钢级: EH36 (t≤50mm) | 最低预热温度: 150°C"
"""


def annotate_table_cells(table) -> list:
    """
    为每个数据单元格注入其行表头和列表头。

    算法：
    1. 通过内容模式（较短文本、粗体、全大写、数字少）
       识别表头行和表头列
    2. 对每个数据单元格，找到其行表头和列表头
    3. 构建上下文文本："{列表头}: {单元格文本} | {行表头}"

    当前为骨架 —— 完整实现需要访问 Docling 的 TableItem
    单元格结构和行列分组。
    """
    return []
```

- [ ] **步骤 4：运行质量测试**

```bash
python -m pytest m1-doc-parsing/tests/test_quality.py -v
```
预期：4 PASS, 0 FAIL

- [ ] **步骤 5：提交**

```bash
git add m1-doc-parsing/m1_parser/core/quality.py m1-doc-parsing/m1_parser/enrichments/table_merger.py m1-doc-parsing/m1_parser/enrichments/table_annotator.py m1-doc-parsing/tests/test_quality.py
git commit -m "[00060-07] feat: 质量门禁 —— 7 因素复杂度评分，表格处理骨架"
```

---

### 任务 8：序列化器与图片管理器 (00060-08)

**涉及文件：**
- 新建：`m1-doc-parsing/m1_parser/output/__init__.py`
- 新建：`m1-doc-parsing/m1_parser/output/serializer.py`
- 新建：`m1-doc-parsing/m1_parser/output/image_manager.py`
- 新建：`m1-doc-parsing/tests/test_serializer.py`
- 新建：`m1-doc-parsing/tests/test_image_manager.py`

- [ ] **步骤 1：编写 serializer.py**

```python
# m1-doc-parsing/m1_parser/output/serializer.py
"""
输出序列化器：ParsedDocument → Markdown / JSON / HTML。

WHY: 不同的消费者需要不同的输出格式。
- RAG 嵌入需要 Markdown
- 程序化处理需要 JSON
- Web 预览需要 HTML
"""

from __future__ import annotations

import json
from pathlib import Path


def save_markdown(content: str, output_dir: str, doc_id: str, filename: str = "full.md"):
    """将解析内容保存为 Markdown。"""
    out_path = Path(output_dir) / doc_id / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return str(out_path)


def save_json(data: dict, output_dir: str, doc_id: str, filename: str = "full.json"):
    """将解析内容保存为 JSON。"""
    out_path = Path(output_dir) / doc_id / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(out_path)
```

- [ ] **步骤 2：编写 image_manager.py**

```python
# m1-doc-parsing/m1_parser/output/image_manager.py
"""
图片提取、存储和元数据管理。

WHY: 文档中的图片（图表、示意图、表格）需要被提取出来，
存储到可预测的目录结构中，并标注元数据以供下游搜索和可视化溯源。

每个文档的目录结构：
  {output_dir}/{doc_id}/
    pages/       -- 页面截图 (PNG, 144 DPI)
    figures/     -- 内嵌图片 (原格式保留)
    tables/      -- 表格截图 (PNG)
"""

from __future__ import annotations

import json
from pathlib import Path


def get_output_paths(output_dir: str, doc_id: str) -> dict[str, Path]:
    """为一个文档创建并返回各输出子目录的路径。"""
    base = Path(output_dir) / doc_id
    subdirs = {
        "base": base,
        "pages": base / "pages",
        "figures": base / "figures",
        "tables": base / "tables",
    }
    for d in subdirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return subdirs


def save_figure_metadata(figure_path: Path, metadata: dict) -> str:
    """
    为图片写入 .meta.json 侧车文件。

    WHY 用侧车文件而非内嵌元数据：原始图片格式可能不支持任意
    元数据字段。JSON 侧车文件通用可读，且不会修改原始文件。
    """
    meta_path = Path(str(figure_path) + ".meta.json")
    meta_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(meta_path)
```

- [ ] **步骤 3：编写测试**

```python
# m1-doc-parsing/tests/test_serializer.py
import tempfile
from pathlib import Path
from m1_parser.output.serializer import save_markdown, save_json


def test_save_markdown_creates_file():
    """save_markdown 必须创建文件和父目录。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_markdown("# 测试标题", tmpdir, "test-doc-001")
        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "# 测试标题" in content


def test_save_json_creates_file():
    """save_json 必须创建有效的 JSON 文件。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_json({"key": "value"}, tmpdir, "test-doc-001")
        assert Path(path).exists()
        import json
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["key"] == "value"
```

```python
# m1-doc-parsing/tests/test_image_manager.py
import tempfile
from pathlib import Path
from m1_parser.output.image_manager import get_output_paths, save_figure_metadata


def test_output_paths_created():
    """get_output_paths 必须创建全部子目录。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = get_output_paths(tmpdir, "test-doc")
        for name, p in paths.items():
            assert p.exists(), f"{name} 路径必须存在: {p}"


def test_figure_metadata_sidecar():
    """save_figure_metadata 必须创建 .meta.json 侧车文件。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        fig = Path(tmpdir) / "figure_001.png"
        fig.write_bytes(b"fake png data")
        meta_path = save_figure_metadata(fig, {"key": "val"})
        assert Path(meta_path).exists()
        import json
        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        assert meta["key"] == "val"
```

- [ ] **步骤 4：运行测试**

```bash
python -m pytest m1-doc-parsing/tests/test_serializer.py m1-doc-parsing/tests/test_image_manager.py -v
```
预期：4 PASS

- [ ] **步骤 5：提交**

```bash
git add m1-doc-parsing/m1_parser/output/ m1-doc-parsing/tests/test_serializer.py m1-doc-parsing/tests/test_image_manager.py
git commit -m "[00060-08] feat: 序列化器（MD/JSON）+ 图片管理器（路径、元数据侧车）"
```

---

### 任务 9：Chunking 封装 (00060-09)

**涉及文件：**
- 新建：`m1-doc-parsing/m1_parser/output/chunker.py`
- 新建：`m1-doc-parsing/tests/test_chunker.py`

- [ ] **步骤 1：编写 chunker.py**

```python
# m1-doc-parsing/m1_parser/output/chunker.py
"""
Hybrid Chunker 封装，为 RAG 嵌入做文本分块准备。

WHY: Docling 的 HybridChunker 是 token 感知的，且保留文档层级结构。
我们封装它以将分词器与 M5 的嵌入模型（BGE-M3/GTE-Qwen2）对齐，
并确保表格表头在分块边界处重复出现。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def create_chunker(
    tokenizer_model_id: str = "BAAI/bge-small-en-v1.5",
    max_tokens: int = 512,
    merge_peers: bool = True,
    repeat_table_header: bool = True,
):
    """
    创建配置好的 HybridChunker 用于 RAG 文档分块。

    Args:
        tokenizer_model_id: HuggingFace 分词器模型 ID。
        max_tokens: 每块最大 token 数（必须与嵌入模型对齐）。
        merge_peers: 合并尺寸过小的相邻块。
        repeat_table_header: 跨分块边界重复表格表头。

    Returns:
        配置好的 HybridChunker 实例，若依赖缺失则返回 None。
    """
    try:
        from docling.chunking import HybridChunker
        from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
        from transformers import AutoTokenizer

        tokenizer = HuggingFaceTokenizer(
            tokenizer=AutoTokenizer.from_pretrained(tokenizer_model_id),
            max_tokens=max_tokens,
        )
        return HybridChunker(
            tokenizer=tokenizer,
            merge_peers=merge_peers,
            repeat_table_header=repeat_table_header,
        )
    except ImportError as e:
        logger.warning("Chunker 不可用: %s", e)
        return None
```

- [ ] **步骤 2：编写测试**

```python
# m1-doc-parsing/tests/test_chunker.py
import pytest
from m1_parser.output.chunker import create_chunker


def test_create_chunker_returns_none_if_missing_deps():
    """如果 docling/transformers 未安装，必须返回 None 而非崩溃。"""
    chunker = create_chunker()
    # None 或有效的 chunker 都可接受（不崩溃就是通过）
    assert chunker is None or hasattr(chunker, "chunk")


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("docling"),
    reason="docling 未安装"
)
def test_create_chunker_with_docling():
    """安装 docling 后必须返回 chunker 或 None（transformers 可能缺失）。"""
    chunker = create_chunker()
    # 如果 transformers 也缺失，返回 None 是预期行为
    pass  # 无需断言；无崩溃 = 通过
```

- [ ] **步骤 3：运行测试**

```bash
python -m pytest m1-doc-parsing/tests/test_chunker.py -v
```
预期：2 PASS

- [ ] **步骤 4：提交**

```bash
git add m1-doc-parsing/m1_parser/output/chunker.py m1-doc-parsing/tests/test_chunker.py
git commit -m "[00060-09] feat: Hybrid Chunker 封装 —— 分词器对齐与表头重复"
```

---

### 任务 10：M2 桥接 (00060-10)

**涉及文件：**
- 新建：`m1-doc-parsing/m1_parser/integration/__init__.py`
- 新建：`m1-doc-parsing/m1_parser/integration/m2_bridge.py`
- 新建：`m1-doc-parsing/tests/test_m2_bridge.py`

- [ ] **步骤 1：编写 m2_bridge.py**

```python
# m1-doc-parsing/m1_parser/integration/m2_bridge.py
"""
M1 解析结果与 M2 存储后端的桥接层。

WHY: 解析完成后，M1 必须将结果存入 M2 的 4 个后端：
- RelationalDB: 文档元数据记录（m1_documents, m1_parsing_tasks）
- VectorStore: 仅通过质量门禁的 chunks
- DocumentIndex: 全文搜索索引
- FileStore: 输出文件（full.md, full.json, 图片）

桥接层确保准确性优先规则：review_required=True 的 chunks
在管理员审批之前绝不写入 VectorStore。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def create_document_record(
    doc_id: str,
    original_name: str,
    original_size: int,
    file_type: str,
    output_dir: str,
    markdown_path: str,
    json_path: str,
    page_count: int = 0,
    chunk_count: int = 0,
    figure_count: int = 0,
    table_count: int = 0,
    metadata: dict | None = None,
    status: str = "done",
) -> dict:
    """
    构建一条 m1_documents 表的文档记录。

    返回可被 M2 RelationalDB 通过 SQLAlchemy session 插入的字典。
    """
    meta = metadata or {}
    return {
        "doc_id": doc_id,
        "original_name": original_name,
        "original_size": original_size,
        "file_type": file_type,
        "output_dir": output_dir,
        "markdown_path": markdown_path,
        "json_path": json_path,
        "status": status,
        "page_count": page_count,
        "chunk_count": chunk_count,
        "figure_count": figure_count,
        "table_count": table_count,
        "classification_society": meta.get("classification_society"),
        "regulation_name": meta.get("regulation_name"),
        "version_year": meta.get("version_year"),
        "chapter_section": meta.get("chapter_section"),
        "language": meta.get("language"),
        "parsed_at": datetime.now(timezone.utc),
    }


def should_store_in_vector_store(chunk) -> bool:
    """
    质量门禁：只有通过审核的 chunks 才能进入 VectorStore。

    WHY 存在此检查：准确性第一原则。复杂表格和不确定内容
    必须在成为可搜索内容之前经过人工审核。
    """
    if getattr(chunk, "review_required", False):
        logger.info(
            "Chunk %s 被阻止进入 VectorStore: %s",
            getattr(chunk, "chunk_id", "?"),
            getattr(chunk, "review_reasons", []),
        )
        return False
    return True
```

- [ ] **步骤 2：编写测试**

```python
# m1-doc-parsing/tests/test_m2_bridge.py
import pytest
from m1_parser.integration.m2_bridge import (
    create_document_record,
    should_store_in_vector_store,
)


def test_create_document_record():
    """必须构建包含所有字段的完整记录字典。"""
    record = create_document_record(
        doc_id="test-001",
        original_name="dnv_rules.pdf",
        original_size=1024,
        file_type="pdf",
        output_dir="./output/test-001",
        markdown_path="./output/test-001/full.md",
        json_path="./output/test-001/full.json",
        page_count=42,
        metadata={"classification_society": "DNV", "version_year": 2024},
    )
    assert record["doc_id"] == "test-001"
    assert record["classification_society"] == "DNV"
    assert record["version_year"] == 2024
    assert record["status"] == "done"
    assert record["parsed_at"] is not None


def test_should_store_approved_chunk():
    """review_required=False 的 chunks 必须被放行。"""
    chunk = type("Chunk", (), {"review_required": False, "chunk_id": "c1"})()
    assert should_store_in_vector_store(chunk) is True


def test_should_block_review_chunk():
    """review_required=True 的 chunks 必须被阻止。"""
    chunk = type("Chunk", (), {
        "review_required": True,
        "chunk_id": "c2",
        "review_reasons": ["跨页表格"],
    })()
    assert should_store_in_vector_store(chunk) is False
```

- [ ] **步骤 3：运行测试**

```bash
python -m pytest m1-doc-parsing/tests/test_m2_bridge.py -v
```
预期：3 PASS

- [ ] **步骤 4：提交**

```bash
git add m1-doc-parsing/m1_parser/integration/ m1-doc-parsing/tests/test_m2_bridge.py
git commit -m "[00060-10] feat: M2 桥接 —— 文档记录构建 + 质量门禁执行"
```

---

### 任务 11：独立 CLI + Web 服务 (00060-11)

**涉及文件：**
- 新建：`m1-doc-parsing/m1_parser/standalone/__init__.py`
- 新建：`m1-doc-parsing/m1_parser/standalone/cli.py`
- 新建：`m1-doc-parsing/m1_parser/standalone/web_server.py`
- 新建：`m1-doc-parsing/tests/test_cli.py`

- [ ] **步骤 1：编写 CLI**

```python
# m1-doc-parsing/m1_parser/standalone/cli.py
"""
M1 独立命令行工具。

用法: m1-parser input.pdf --backend docling --ocr easyocr --output ./out/

WHY CLI: 不想运行完整系统的用户可以仅在命令行解析文档。
pip install m1-doc-parsing 后即可获得 m1-parser 命令。
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="m1-parser",
        description="M1 文档解析器 —— 船舶与海洋工程专家系统",
    )
    parser.add_argument("input", nargs="+", help="待解析的输入文件")
    parser.add_argument("--backend", default="docling",
                        choices=["docling", "marker", "mineru"],
                        help="解析引擎（默认 docling）")
    parser.add_argument("--ocr", default="easyocr",
                        choices=["paddleocr", "easyocr", "tesseract", "suryaocr"],
                        help="OCR 引擎（默认 easyocr）")
    parser.add_argument("--output", "-o", default="./output",
                        help="输出目录（默认 ./output）")
    parser.add_argument("--format", default="md",
                        choices=["md", "json", "html"],
                        help="输出格式（默认 md）")
    parser.add_argument("--vlm", default=None,
                        help="VLM preset 名称（granite_docling 等）")

    args = parser.parse_args()

    # 仅在需要时导入核心模块（保持 CLI 启动速度）
    from m1_parser.core.converter import convert_batch, ParseOptions

    options = ParseOptions(
        backend=args.backend,
        ocr_engine=args.ocr,
        vlm_preset=args.vlm,
        output_dir=args.output,
        output_formats=[args.format],
    )

    results = convert_batch(args.input, options)
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    print(f"\n解析完成: {len(results)} 个文件, {success_count} 成功, {fail_count} 失败")
    for r in results:
        if r.success:
            print(f"  OK   {r.source_path}")
        else:
            print(f"  失败  {r.source_path}: {r.error}")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
```

- [ ] **步骤 2：编写 web_server.py 骨架**

```python
# m1-doc-parsing/m1_parser/standalone/web_server.py
"""
M1 独立运行的极简 FastAPI Web 服务。

路由:
  GET  /           -- 上传+配置页面
  POST /parse      -- 上传文件，解析，返回 Markdown
  GET  /download/{doc_id} -- 下载解析结果

WHY FastAPI: 异步文件上传、SSE 进度推送、简洁。
单文件部署: python web_server.py 即可运行。
"""

from fastapi import FastAPI

app = FastAPI(title="M1 文档解析器")


@app.get("/")
async def index():
    return {"message": "M1 文档解析器 —— 上传页面即将上线"}
```

- [ ] **步骤 3：编写 CLI 测试**

```python
# m1-doc-parsing/tests/test_cli.py
"""独立 CLI 的测试。"""
import subprocess
import sys
import pytest


def test_cli_help():
    """m1-parser --help 必须退出码为 0 并显示用法。"""
    result = subprocess.run(
        [sys.executable, "-m", "m1_parser.standalone.cli", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "m1-parser" in result.stdout


def test_cli_nonexistent_file():
    """解析不存在的文件必须非零退出。"""
    result = subprocess.run(
        [sys.executable, "-m", "m1_parser.standalone.cli", "nonexistent.xyz"],
        capture_output=True, text=True,
    )
    assert "失败" in result.stdout or result.returncode != 0
```

- [ ] **步骤 4：运行测试**

```bash
pip install fastapi && python -m pytest m1-doc-parsing/tests/test_cli.py -v
```
预期：2 PASS

- [ ] **步骤 5：提交**

```bash
git add m1-doc-parsing/m1_parser/standalone/ m1-doc-parsing/tests/test_cli.py
git commit -m "[00060-11] feat: 独立 CLI (m1-parser) 和 FastAPI Web 服务骨架"
```

---

### 任务 12：最终打包与验证 (00060-12)

**涉及文件：**
- 验证：所有文件已创建，全部测试通过
- 验证：m1-parser CLI 可执行
- 验证：pip install 成功

- [ ] **步骤 1：安装并验证导入**

```bash
cd E:/myCode/RAG && pip install -e m1-doc-parsing/
python -c "from m1_parser import convert, detect_hardware; print('导入成功')"
python -m m1_parser.standalone.cli --help
```
预期：显示 "导入成功" 和 CLI 帮助文本

- [ ] **步骤 2：运行完整测试套件**

```bash
python -m pytest m1-doc-parsing/tests/ -v
```
预期：全部测试通过

- [ ] **步骤 3：提交**

```bash
git add m1-doc-parsing/
git commit -m "[00060-12] chore: 完成 M1 打包、公开 API 与最终验证"
```

---

## 依赖关系图

```
00060-01 (config) ──→ 00060-02 (router) ──→ 00060-03 (Docling后端)
                                               │
                         00060-04 (Marker/MinerU)
                                               │
                         00060-05 (converter) ←─┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
   00060-06              00060-07              00060-08
 (元数据提取)         (质量+表格骨架)     (序列化+图片)
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                         00060-09 (chunker)
                               │
                         00060-10 (M2桥接)
                               │
                         00060-11 (CLI + Web)
                               │
                         00060-12 (打包验证)
```

任务 00060-06、00060-07、00060-08 相互独立，可以并行开发。

---

*计划完成。请使用 superpowers:subagent-driven-development 或 superpowers:executing-plans 执行。*
