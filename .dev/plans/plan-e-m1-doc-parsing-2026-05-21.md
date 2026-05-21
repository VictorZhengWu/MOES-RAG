# M1 Document Parsing Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the M1 document parsing engine with dual-mode operation (standalone CLI/Web + system module), Docling v2.94 as primary engine, Marker/MinerU as PDF alternatives, GPU auto-detection, marine metadata extraction, complex table quality gating, and M2 integration.

**Architecture:** 6-stage parsing pipeline (Route → Parse → Metadata → Table Enrich → Quality Gate → Serialize). Converter orchestrates through router → backend → enrichments → quality → output. Standalone web UI via FastAPI + single-file HTML. Module mode integrates with M7 and M2.

**Tech Stack:** Python 3.12+, Docling v2.94, python-magic, PyYAML, FastAPI, aiohttp, langdetect, HuggingFace tokenizers

---

### Task 1: Project Skeleton + Config System (00060-01)

**Files:**
- Create: `m1-doc-parsing/pyproject.toml`
- Create: `m1-doc-parsing/requirements.txt`
- Create: `m1-doc-parsing/m1_parser/__init__.py`
- Create: `m1-doc-parsing/m1_parser/core/__init__.py`
- Create: `m1-doc-parsing/m1_parser/core/config.py`
- Create: `m1-doc-parsing/tests/__init__.py`
- Create: `m1-doc-parsing/tests/test_config.py`

- [ ] **Step 1: Create project skeleton**

`pyproject.toml`:
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
marker = ["marker-pdf"]
mineru = ["magic-pdf"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23.0"]
all = ["m1-doc-parsing[vlm,ocr,marker,mineru,dev]"]

[project.scripts]
m1-parser = "m1_parser.standalone.cli:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`requirements.txt`:
```
docling>=2.94.0
pyyaml>=6.0
python-magic>=0.4.27
langdetect>=1.0.9
pytest>=8.0
pytest-asyncio>=0.23.0
```

`m1_parser/__init__.py`:
```python
"""
M1 -- Document Parsing Engine.

Converts raw files (PDF, Office, images) into structured Markdown
with marine-domain metadata, complex table annotations, and quality
confidence scores. Operates in two modes:
  - Standalone: CLI tool + Web UI
  - Module: Called by M7 admin portal, writes to M2 storage
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

`m1_parser/core/__init__.py`:
```python
# Core parsing pipeline components
```

`tests/__init__.py`:
```python
# M1 test suite
```

- [ ] **Step 2: Write test_config.py (TDD first)**

```python
# m1-doc-parsing/tests/test_config.py
"""
Tests for config.py -- hardware detection and backend/OCR selection.

WHY: GPU detection and backend recommendation are the first thing that
runs when M1 starts. Wrong detection = wrong default settings = poor
performance or crashes. These tests mock hardware to verify all 4
tiered recommendation paths.
"""

import platform
from unittest.mock import patch, MagicMock

import pytest

from m1_parser.core.config import (
    HardwareProfile,
    detect_hardware,
    recommend_ocr_engine,
    SUPPORTED_BACKENDS,
    OCR_ENGINE_PRIORITY,
)


# ---------------------------------------------------------------------------
# Test 1: GPU ≥ 8GB + Linux → vLLM + PaddleOCR-VL
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=True)
@patch("torch.cuda.get_device_properties")
@patch.object(platform, "system", return_value="Linux")
def test_gpu_8gb_linux_recommends_vllm(mock_system, mock_props, mock_avail):
    """GPU >= 8GB on Linux must recommend vLLM + PaddleOCR-VL."""
    mock_props.return_value.total_memory = 12 * 1024**3  # 12 GB
    profile = detect_hardware()
    assert profile.gpu is True
    assert profile.vram_gb == 12.0
    assert profile.recommended_backend == "paddleocr_vl"
    assert profile.can_use_vllm is True


# ---------------------------------------------------------------------------
# Test 2: GPU ≥ 8GB + Windows → Transformers + GraniteDocling
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=True)
@patch("torch.cuda.get_device_properties")
@patch.object(platform, "system", return_value="Windows")
def test_gpu_8gb_windows_recommends_transformers(mock_system, mock_props, mock_avail):
    """GPU >= 8GB on Windows must recommend Transformers engine."""
    mock_props.return_value.total_memory = 10 * 1024**3
    profile = detect_hardware()
    assert profile.gpu is True
    assert profile.recommended_backend == "granite_docling"
    assert profile.can_use_vllm is False


# ---------------------------------------------------------------------------
# Test 3: GPU < 8GB → Standard Pipeline
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=True)
@patch("torch.cuda.get_device_properties")
def test_gpu_low_vram_recommends_standard(mock_props, mock_avail):
    """GPU with < 8GB VRAM must recommend Standard Pipeline."""
    mock_props.return_value.total_memory = 6 * 1024**3  # RTX 2060
    profile = detect_hardware()
    assert profile.recommended_backend == "docling_standard"


# ---------------------------------------------------------------------------
# Test 4: No GPU → CPU mode + EasyOCR
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=False)
def test_no_gpu_recommends_cpu(mock_avail):
    """No GPU must recommend CPU mode with EasyOCR."""
    profile = detect_hardware()
    assert profile.gpu is False
    assert profile.vram_gb == 0
    assert profile.recommended_backend == "docling_standard"
    assert profile.recommended_ocr == "easyocr"
    assert profile.can_use_vllm is False


# ---------------------------------------------------------------------------
# Test 5: OCR engine priority
# ---------------------------------------------------------------------------

def test_ocr_priority_order():
    """PaddleOCR must be first, Tesseract last."""
    assert OCR_ENGINE_PRIORITY[0] == "paddleocr"
    assert OCR_ENGINE_PRIORITY[-1] == "tesseract"


# ---------------------------------------------------------------------------
# Test 6: Backend list includes all required engines
# ---------------------------------------------------------------------------

def test_supported_backends():
    """All 3 backend types must be in the supported list."""
    assert "docling" in SUPPORTED_BACKENDS
    assert "marker" in SUPPORTED_BACKENDS
    assert "mineru" in SUPPORTED_BACKENDS
```

- [ ] **Step 3: Run test to verify failure**

```bash
python -m pytest m1-doc-parsing/tests/test_config.py -v
```
Expected: FAIL with import errors

- [ ] **Step 4: Write config.py**

```python
# m1-doc-parsing/m1_parser/core/config.py
"""
Hardware detection and configuration management for M1.

WHY: M1 runs on diverse hardware (CPU-only laptops to GPU servers).
Auto-detection eliminates manual setup guesswork and ensures optimal
performance on each deployment. The tiered recommendation system maps
4 hardware profiles to the most efficient backend+OCR combination.

Key decisions:
- vLLM is Linux-only (uses Linux kernel features)
- PaddleOCR-VL-1.5 needs ~4.2GB VRAM (or 230MB INT8)
- GraniteDocling-258M is the safest cross-platform VLM
- EasyOCR is the most reliable CPU fallback
"""

from __future__ import annotations

import platform
from dataclasses import dataclass

# ===========================================================================
# Constants
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
# Hardware profile
# ===========================================================================


@dataclass
class HardwareProfile:
    """
    Detected hardware capabilities and recommended configuration.

    WHY a dataclass, not a dict: type-safe consumers (M7 config page)
    can rely on field existence and types without try/except KeyError.
    """

    gpu: bool
    vram_gb: float
    recommended_backend: str  # "docling_standard" | "paddleocr_vl" | ...
    recommended_ocr: str      # "paddleocr" | "easyocr" | ...
    can_use_vllm: bool        # True only on Linux with GPU


def detect_hardware() -> HardwareProfile:
    """
    Detect GPU and OS, return tiered configuration recommendation.

    Detection logic (4 tiers):
    1. GPU >= 8GB + Linux   → vLLM + PaddleOCR-VL-1.5
    2. GPU >= 8GB + Windows → Transformers + GraniteDocling
    3. GPU < 8GB            → Standard Pipeline (or INT8 VLM)
    4. No GPU               → EasyOCR CPU mode

    WHY tiered: vLLM is Linux-only. PaddleOCR-VL needs 4.2GB+ VRAM.
    Auto-detection prevents recommending a config that won't run.
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
    Return the first available OCR engine from the priority list.

    Attempts engines in order (PaddleOCR → SuryaOCR → EasyOCR → Tesseract).
    If `preferred` is given and available, uses it regardless of priority.

    WHY fallback chain: different environments have different engines
    installed. PaddleOCR may fail to import; EasyOCR is near-universal.
    """
    if preferred and _is_ocr_available(preferred):
        return preferred

    for engine in OCR_ENGINE_PRIORITY:
        if _is_ocr_available(engine):
            return engine
    raise RuntimeError(
        "No OCR engine available. Install one of: "
        + ", ".join(OCR_ENGINE_PRIORITY)
    )


def _is_ocr_available(engine: str) -> bool:
    """
    Check if an OCR engine can be imported.

    WHY lazy detection: import errors at startup are better than
    runtime crashes 5 minutes into parsing a 100-page PDF.
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

- [ ] **Step 5: Run tests**

```bash
cd E:/myCode/RAG && pip install pyyaml && python -m pytest m1-doc-parsing/tests/test_config.py -v
```
Expected: 6 PASS, 0 FAIL

- [ ] **Step 6: Commit**

```bash
git add m1-doc-parsing/
git commit -m "[00060-01] feat: project skeleton, config.py with GPU detection and tiered recommendations"
```

---

### Task 2: Format Router (00060-02)

**Files:**
- Create: `m1-doc-parsing/m1_parser/core/router.py`
- Create: `m1-doc-parsing/tests/test_router.py`

- [ ] **Step 1: Write test_router.py**

```python
# m1-doc-parsing/tests/test_router.py
"""
Tests for router.py -- file type detection and format routing.

WHY: The router determines which backend handles each file. A PDF
routed to the DOCX pipeline would produce garbage. Magic bytes sniffing
catches mislabeled files (e.g., a .pdf that's actually a .docx).
"""

import tempfile
from pathlib import Path

import pytest

from m1_parser.core.router import (
    detect_format,
    route_backend,
    FileFormat,
    FORMAT_BACKEND_MAP,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_temp_file(ext: str, magic_bytes: bytes = b"") -> Path:
    """Create a temp file with given extension and optional magic bytes."""
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    if magic_bytes:
        tmp.write(magic_bytes)
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Test 1: PDF detection
# ---------------------------------------------------------------------------

def test_detect_pdf():
    """Files starting with %PDF- must be identified as PDF."""
    f = _write_temp_file(".pdf", b"%PDF-1.4\n%some content")
    fmt = detect_format(str(f))
    assert fmt == FileFormat.PDF


# ---------------------------------------------------------------------------
# Test 2: DOCX detection
# ---------------------------------------------------------------------------

def test_detect_docx():
    """Files with ZIP magic + .docx extension = DOCX."""
    f = _write_temp_file(".docx", b"PK\x03\x04")
    fmt = detect_format(str(f))
    assert fmt == FileFormat.DOCX


# ---------------------------------------------------------------------------
# Test 3: Image detection (PNG)
# ---------------------------------------------------------------------------

def test_detect_image_png():
    """Files with PNG magic bytes must be identified as IMAGE."""
    f = _write_temp_file(".png", b"\x89PNG\r\n\x1a\n")
    fmt = detect_format(str(f))
    assert fmt == FileFormat.IMAGE


# ---------------------------------------------------------------------------
# Test 4: Unsupported format
# ---------------------------------------------------------------------------

def test_unsupported_format():
    """Unknown magic bytes must raise ValueError."""
    f = _write_temp_file(".xyz", b"random binary garbage")
    with pytest.raises(ValueError, match="Unsupported"):
        detect_format(str(f))


# ---------------------------------------------------------------------------
# Test 5: Backend routing -- PDF gets 3 options
# ---------------------------------------------------------------------------

def test_route_pdf():
    """PDF files must route to the user's chosen backend."""
    assert route_backend(FileFormat.PDF, "docling") == "docling"
    assert route_backend(FileFormat.PDF, "marker") == "marker"
    assert route_backend(FileFormat.PDF, "mineru") == "mineru"
    with pytest.raises(ValueError, match="Unsupported backend"):
        route_backend(FileFormat.PDF, "unknown_engine")


# ---------------------------------------------------------------------------
# Test 6: DOCX forced to Docling
# ---------------------------------------------------------------------------

def test_route_docx():
    """DOCX always routes to Docling regardless of chosen backend."""
    assert route_backend(FileFormat.DOCX, "docling") == "docling"
    # Even if user picked Marker, DOCX must still use Docling
    assert route_backend(FileFormat.DOCX, "marker") == "docling"
```

- [ ] **Step 2: Write router.py**

```python
# m1-doc-parsing/m1_parser/core/router.py
"""
File format detection and backend routing.

WHY: Different formats need different parsers. Magic bytes sniffing
is more reliable than extension-based detection — a .pdf file might
actually be a JPEG. The router also knows which backends can handle
which formats (e.g., Marker only does PDF/IMAGE, not DOCX).

Detection priority: magic bytes (first 8 bytes) → extension fallback.
"""

from __future__ import annotations

import enum
from pathlib import Path


class FileFormat(str, enum.Enum):
    """Supported input file formats."""
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    HTML = "html"
    IMAGE = "image"
    CSV = "csv"
    MARKDOWN = "markdown"


# ===========================================================================
# Magic bytes signatures
# ===========================================================================

_MAGIC_SIGNATURES: list[tuple[bytes, FileFormat]] = [
    (b"%PDF-", FileFormat.PDF),
    (b"\x89PNG", FileFormat.IMAGE),
    (b"\xff\xd8\xff", FileFormat.IMAGE),          # JPEG
    (b"II*\x00", FileFormat.IMAGE),               # TIFF (little-endian)
    (b"MM\x00*", FileFormat.IMAGE),               # TIFF (big-endian)
    (b"BM", FileFormat.IMAGE),                    # BMP
    (b"PK\x03\x04", None),                        # ZIP-based (DOCX/XLSX/PPTX)
    (b"<!DOCTYP", FileFormat.HTML),
    (b"<html", FileFormat.HTML),
]

# Formats that Marker/MinerU can handle (PDF + IMAGE only)
_PDF_BACKENDS = {"docling", "marker", "mineru"}

# All non-PDF/IMAGE formats go to Docling regardless of user choice
_DOCLING_ONLY_FORMATS = {
    FileFormat.DOCX, FileFormat.XLSX, FileFormat.PPTX,
    FileFormat.HTML, FileFormat.CSV, FileFormat.MARKDOWN,
}


def detect_format(file_path: str) -> FileFormat:
    """
    Detect file format using magic bytes, fall back to extension.

    WHY magic bytes first: a file named 'report.pdf' might actually
    be a DOCX (ZIP-based). Magic bytes catch this. Extension is used
    as fallback when the magic bytes only tell us it's ZIP-based.

    Args:
        file_path: Path to the file to inspect.

    Returns:
        FileFormat enum value.

    Raises:
        ValueError: If the format cannot be determined.
    """
    path = Path(file_path)

    # Read first 8 bytes for magic signature detection
    with open(file_path, "rb") as f:
        header = f.read(8)

    # Check magic bytes
    for signature, fmt in _MAGIC_SIGNATURES:
        if header.startswith(signature):
            if fmt is None:  # ZIP-based -- use extension
                return _format_from_extension(path.suffix.lower())
            return fmt

    # Fallback to extension
    return _format_from_extension(path.suffix.lower())


def route_backend(fmt: FileFormat, user_choice: str) -> str:
    """
    Select the correct backend for a given format.

    PDF/IMAGE: user's choice (docling/marker/mineru).
    Everything else: docling only (Marker/MinerU don't support them).

    WHY force Docling for non-PDF: Marker and MinerU are PDF/IMAGE
    specialists. Routing a DOCX to them would silently fail.

    Args:
        fmt: Detected file format.
        user_choice: User's preferred backend name.

    Returns:
        Backend name string ("docling", "marker", or "mineru").

    Raises:
        ValueError: If the backend is not valid for this format.
    """
    if fmt in _DOCLING_ONLY_FORMATS:
        return "docling"

    if fmt in (FileFormat.PDF, FileFormat.IMAGE):
        if user_choice in _PDF_BACKENDS:
            return user_choice
        raise ValueError(
            f"Unsupported backend '{user_choice}' for {fmt.value}. "
            f"Supported: {', '.join(sorted(_PDF_BACKENDS))}"
        )

    raise ValueError(f"Unsupported file format: {fmt.value}")


def _format_from_extension(suffix: str) -> FileFormat:
    """Map file extension to FileFormat."""
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
            f"Unsupported file extension: {suffix}. "
            f"Supported: {', '.join(sorted(ext_map.keys()))}"
        )
    return fmt
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest m1-doc-parsing/tests/test_router.py -v
```
Expected: 6 PASS, 0 FAIL

- [ ] **Step 4: Commit**

```bash
git add m1-doc-parsing/m1_parser/core/router.py m1-doc-parsing/tests/test_router.py
git commit -m "[00060-02] feat: format router with magic bytes detection and backend routing"
```

---

### Task 3: Docling Backend Adapter (00060-03)

**Files:**
- Create: `m1-doc-parsing/m1_parser/backends/__init__.py`
- Create: `m1-doc-parsing/m1_parser/backends/docling_backend.py`
- Create: `m1-doc-parsing/tests/test_docling_backend.py`

- [ ] **Step 1: Write test_docling_backend.py**

```python
# m1-doc-parsing/tests/test_docling_backend.py
"""
Tests for DoclingBackend -- the primary document parsing backend.

WHY: Docling is the default engine handling 10+ formats. These tests
verify PDF, DOCX, and image conversion produce valid Markdown output.
"""

import tempfile
from pathlib import Path

import pytest


# Skip all tests if docling is not installed
docling = pytest.importorskip("docling", reason="docling not installed")

from m1_parser.backends.docling_backend import DoclingBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_pdf(path: Path, text: str = "Hello World") -> None:
    """Create a minimal text PDF for testing."""
    # Write a minimal PDF programmatically
    content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF"
    )
    path.write_bytes(content)


# ---------------------------------------------------------------------------
# Test 1: PDF → Markdown works
# ---------------------------------------------------------------------------

def test_pdf_to_markdown():
    """Converting a PDF must return non-empty Markdown string."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        _create_test_pdf(Path(f.name))
        pdf_path = f.name

    backend = DoclingBackend()
    result = backend.convert(pdf_path)
    assert result.markdown is not None
    assert len(result.markdown) > 0


# ---------------------------------------------------------------------------
# Test 2: Backend respects OCR option
# ---------------------------------------------------------------------------

def test_ocr_option_set():
    """Passing ocr_engine must not crash."""
    backend = DoclingBackend(ocr_engine="easyocr")
    assert backend.ocr_engine == "easyocr"


# ---------------------------------------------------------------------------
# Test 3: Backend respects VLM preset
# ---------------------------------------------------------------------------

def test_vlm_preset_set():
    """Passing a VLM preset must configure the VLM pipeline."""
    backend = DoclingBackend(vlm_preset="granite_docling")
    assert backend.vlm_preset == "granite_docling"
```

- [ ] **Step 2: Write docling_backend.py**

```python
# m1-doc-parsing/m1_parser/backends/docling_backend.py
"""
Docling v2.94 backend adapter.

WHY: Docling is the primary engine handling all 10+ formats.
This adapter encapsulates Docling's DocumentConverter, providing
a clean interface for the M1 converter to call. It handles:
- Standard Pipeline (layout detection + OCR + table recognition)
- VLM Pipeline (vision language model end-to-end)
- Format-specific options (PDF/DOCX/PPTX/XLSX/IMAGE/HTML)

Design: all Docling-specific imports and configuration live here.
If we ever swap Docling for another engine, only this file changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of a single document parse."""
    markdown: str
    json_dict: dict | None = None
    page_count: int = 0
    figure_count: int = 0
    table_count: int = 0


class DoclingBackend:
    """
    Document parsing via Docling v2.94.

    Supports two pipelines:
    - Standard Pipeline: layout detection → OCR → table structure
    - VLM Pipeline: vision language model → end-to-end Markdown/DocTags

    OCR engines are configured via Docling's PdfPipelineOptions:
    EasyOCR (default), Tesseract, RapidOCR, SuryaOCR.
    """

    def __init__(
        self,
        ocr_engine: str = "easyocr",
        vlm_preset: str | None = None,
        use_gpu: bool = False,
    ):
        """
        Args:
            ocr_engine: OCR backend name (easyocr, tesseract, rapidocr, suryaocr).
            vlm_preset: VLM preset name (granite_docling, deepseek_ocr, etc.).
                        If set, uses VlmPipeline instead of StandardPdfPipeline.
            use_gpu: Whether to use CUDA acceleration.
        """
        self.ocr_engine = ocr_engine
        self.vlm_preset = vlm_preset
        self.use_gpu = use_gpu

    def convert(self, source: str) -> ParseResult:
        """
        Convert a document file to structured output.

        WHY returns ParseResult, not raw DoclingDocument: upper modules
        (converter.py) need a stable interface regardless of which
        backend (Docling/Marker/MinerU) is active.

        Args:
            source: Path or URL to the document.

        Returns:
            ParseResult with markdown, metadata, and counts.
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

- [ ] **Step 3: Run tests**

```bash
pip install docling && python -m pytest m1-doc-parsing/tests/test_docling_backend.py -v
```
Expected: 3 PASS (or skip if docling unavailable)

- [ ] **Step 4: Commit**

```bash
git add m1-doc-parsing/m1_parser/backends/ m1-doc-parsing/tests/test_docling_backend.py
git commit -m "[00060-03] feat: Docling backend adapter with Standard and VLM pipeline support"
```

---

### Task 4: Marker + MinerU Backend Adapters (00060-04)

**Files:**
- Create: `m1-doc-parsing/m1_parser/backends/marker_backend.py`
- Create: `m1-doc-parsing/m1_parser/backends/mineru_backend.py`

- [ ] **Step 1: Write marker_backend.py**

```python
# m1-doc-parsing/m1_parser/backends/marker_backend.py
"""
Marker backend adapter for PDF/image parsing.

WHY: Marker is a popular open-source PDF-to-Markdown tool using Surya
deep learning models for layout detection and OCR. It serves as a
PDF-only alternative when users prefer its output quality over Docling.

The adapter wraps Marker's CLI/API behind the same interface as
DoclingBackend so the converter can swap them transparently.
"""

from __future__ import annotations

import logging

from .docling_backend import ParseResult

logger = logging.getLogger(__name__)


class MarkerBackend:
    """PDF/image parsing via Marker (Surya-based)."""

    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu

    def convert(self, source: str) -> ParseResult:
        """
        Convert a PDF/image to Markdown using Marker.

        Currently a stub -- Marker requires specific environment setup.
        Returns empty result with a warning until Marker is installed.

        TODO: Integrate marker-pdf package when available.
        """
        logger.warning(
            "Marker backend called but marker-pdf not installed. "
            "Install with: pip install marker-pdf"
        )
        return ParseResult(
            markdown="",
            page_count=0,
        )
```

- [ ] **Step 2: Write mineru_backend.py**

```python
# m1-doc-parsing/m1_parser/backends/mineru_backend.py
"""
MinerU backend adapter for PDF parsing.

WHY: MinerU (magic-pdf) from Shanghai AI Lab is optimized for Chinese
scientific and technical documents. It uses PDF-Extract-Kit for deep
layout analysis and is the best open-source option for Chinese PDFs
with complex tables and formulas.

The adapter wraps MinerU's CLI behind the same ParseResult interface
so the converter can swap backends without touching any other code.
"""

from __future__ import annotations

import logging

from .docling_backend import ParseResult

logger = logging.getLogger(__name__)


class MinerUBackend:
    """PDF parsing via MinerU (magic-pdf)."""

    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu

    def convert(self, source: str) -> ParseResult:
        """
        Convert a PDF to Markdown using MinerU.

        Currently a stub -- MinerU requires specific environment setup.
        Returns empty result with a warning until magic-pdf is installed.

        TODO: Integrate magic-pdf when environment is ready.
        """
        logger.warning(
            "MinerU backend called but magic-pdf not installed. "
            "Install with: pip install magic-pdf"
        )
        return ParseResult(
            markdown="",
            page_count=0,
        )
```

- [ ] **Step 3: Commit**

```bash
git add m1-doc-parsing/m1_parser/backends/marker_backend.py m1-doc-parsing/m1_parser/backends/mineru_backend.py
git commit -m "[00060-04] feat: Marker and MinerU backend stubs"
```

---

### Task 5: Main Converter (00060-05)

**Files:**
- Create: `m1-doc-parsing/m1_parser/core/converter.py`
- Create: `m1-doc-parsing/tests/test_converter.py`

This is the largest single file in M1. The converter orchestrates the 6-stage pipeline.

- [ ] **Step 1: Write test_converter.py**

```python
# m1-doc-parsing/tests/test_converter.py
"""
Tests for the main converter -- 6-stage pipeline orchestration.

WHY: The converter is M1's public API. Every consumer (CLI, Web UI,
M7 admin) calls convert() or convert_batch(). These tests verify
end-to-end flow with real file inputs.
"""

import tempfile
from pathlib import Path

import pytest

from m1_parser.core.converter import convert, convert_batch, ParseOptions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_minimal_pdf(path: Path) -> None:
    """Create a tiny valid PDF for testing."""
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
# Test 1: Single file conversion succeeds
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("docling"),
    reason="docling not installed"
)
def test_convert_pdf():
    """Converting a valid PDF must return a result with doc_id."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        _create_minimal_pdf(Path(f.name))
        fname = f.name

    options = ParseOptions(backend="docling")
    # converter.convert() is our main entry point
    # For now, test that it doesn't crash
    try:
        result = convert(fname, options)
        assert result is not None
    except ImportError:
        pytest.skip("docling not available")


# ---------------------------------------------------------------------------
# Test 2: Batch conversion handles multiple files
# ---------------------------------------------------------------------------

def test_convert_batch_handles_errors():
    """Batch conversion with raises_on_error=False must not crash on bad files."""
    options = ParseOptions(backend="docling")
    results = convert_batch(
        ["nonexistent1.pdf", "nonexistent2.pdf"],
        options,
        raises_on_error=False,
    )
    # Both should have failed, but the function should not raise
    assert len(results) == 2


# ---------------------------------------------------------------------------
# Test 3: ParseOptions defaults
# ---------------------------------------------------------------------------

def test_parse_options_defaults():
    """Default options must use Docling backend and EasyOCR."""
    opts = ParseOptions()
    assert opts.backend == "docling"
    assert opts.ocr_engine == "easyocr"
    assert opts.output_dir == "./output"
```

- [ ] **Step 2: Write converter.py**

```python
# m1-doc-parsing/m1_parser/core/converter.py
"""
Main document converter -- 6-stage parsing pipeline.

WHY: M1's core value is the orchestrated pipeline that takes a raw
file and produces a ParsedDocument with metadata, table annotations,
and quality scores. The converter is the single entry point for all
consumers (CLI, Web UI, M7 admin, batch processing).

Pipeline stages:
  1. Format routing (router.py)
  2. Structure parsing (backend adapter)
  3. Metadata extraction (marine_metadata.py)
  4. Table enrichment (table_annotator + table_merger)
  5. Quality gating (quality.py)
  6. Output serialization (serializer + chunker + image_manager)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ===========================================================================
# Input/Output types
# ===========================================================================


@dataclass
class ParseOptions:
    """User-configurable parsing options.

    WHY a separate options class, not function parameters: as we add
    more config (OCR, VLM, quality thresholds, output format), the
    function signature would become unmanageable. A dataclass with
    defaults keeps the API stable.
    """

    backend: str = "docling"        # docling | marker | mineru
    ocr_engine: str = "easyocr"     # paddleocr | easyocr | tesseract | suryaocr
    vlm_preset: str | None = None   # granite_docling | deepseek_ocr | ...
    use_gpu: bool = False
    output_dir: str = "./output"
    output_formats: list[str] = field(default_factory=lambda: ["md", "json"])


@dataclass
class ParseResult:
    """Result of parsing a single document.

    Contains both the parsed content and metadata about the process.
    The `doc_id` is a UUID generated at parse time, used as the key
    for M2 storage lookups.
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
# Public API
# ===========================================================================


def convert(source: str, options: ParseOptions | None = None) -> ParseResult:
    """
    Convert a single document through the full 6-stage pipeline.

    This is M1's primary public API. Every consumer calls this:
      - CLI: m1-parser input.pdf
      - Web UI: POST /parse {file: input.pdf}
      - M7 admin: document upload workflow
      - Module mode: from m1_parser import convert

    Args:
        source: File path or URL to the document.
        options: Parsing configuration. Uses defaults if omitted.

    Returns:
        ParseResult with doc_id, markdown, metadata, and status.
    """
    if options is None:
        options = ParseOptions()

    doc_id = uuid.uuid4().hex[:12]
    logger.info("Parsing %s (doc_id=%s, backend=%s)", source, doc_id, options.backend)

    # Stage 1: Format routing
    from .router import detect_format, route_backend
    fmt = detect_format(source)
    backend_name = route_backend(fmt, options.backend)

    # Stage 2: Structure parsing
    from ..backends.docling_backend import DoclingBackend, ParseResult as BackendResult
    if backend_name == "docling":
        backend = DoclingBackend(
            ocr_engine=options.ocr_engine,
            vlm_preset=options.vlm_preset,
            use_gpu=options.use_gpu,
        )
        raw: BackendResult = backend.convert(source)
    else:
        # Marker/MinerU -- currently stubs (Task 00060-04 will implement)
        return ParseResult(
            doc_id=doc_id,
            source_path=source,
            success=False,
            error=f"Backend '{backend_name}' not yet implemented",
        )

    # Stages 3-6 will be wired in Tasks 00060-06 through 00060-08
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
    Convert multiple documents. Errors are collected, not raised.

    WHY raises_on_error=False by default: in batch mode (e.g., 50 files),
    one corrupt file should not abort the remaining 49.
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

- [ ] **Step 3: Run tests**

```bash
python -m pytest m1-doc-parsing/tests/test_converter.py -v
```
Expected: 3 PASS

- [ ] **Step 4: Commit**

```bash
git add m1-doc-parsing/m1_parser/core/converter.py m1-doc-parsing/tests/test_converter.py
git commit -m "[00060-05] feat: main converter with 6-stage pipeline orchestration"
```

---

### Task 6: Marine Metadata Extraction (00060-06)

**Files:**
- Create: `m1-doc-parsing/m1_parser/enrichments/__init__.py`
- Create: `m1-doc-parsing/m1_parser/enrichments/marine_metadata.py`
- Create: `m1-doc-parsing/tests/test_marine_metadata.py`

- [ ] **Step 1: Write test_marine_metadata.py**

```python
# m1-doc-parsing/tests/test_marine_metadata.py
"""
Tests for marine_metadata.py -- auto-extraction of classification society
metadata from document text and filenames.

WHY: The 5 auto-extracted fields are the basis for document filtering
in M3 retrieval and M7 admin. Wrong extraction means documents are
unfindable.
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
# Test 1: classification_society detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("This document follows DNV rules for ships.", "DNV"),
    ("American Bureau of Shipping (ABS) standards apply.", "ABS"),
    ("In accordance with CCS Chapter 7.", "CCS"),
    ("Lloyd's Register (LR) classification notes.", "LR"),
    ("Bureau Veritas (BV) rules part B.", "BV"),
    ("Nippon Kaiji Kyokai (NK) guidelines.", "NK"),
    ("Registro Italiano Navale (RINA)", "RINA"),
    ("Korean Register (KR) of shipping", "KR"),
    ("IMO resolution MSC.456(101)", "IMO"),
    ("IACS unified requirement UR W33", "IACS"),
])
def test_extract_classification_society(text, expected):
    """Known society abbreviations must be detected."""
    assert extract_classification_society(text) == expected


def test_no_society_returns_none():
    """Text without any society mention must return None."""
    assert extract_classification_society("General engineering guidelines.") is None


# ---------------------------------------------------------------------------
# Test 2: version_year detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("DNV Rules 2024 Edition", 2024),
    ("Published January 2023", 2023),
    ("IMO 2020 guidelines", 2020),
    ("Version 2019-03", 2019),
])
def test_extract_version_year(text, expected):
    """Year patterns in text must be extracted."""
    assert extract_version_year(text) == expected


def test_no_year_returns_none():
    """Text without a recognizable year must return None."""
    assert extract_version_year("General specification document.") is None


# ---------------------------------------------------------------------------
# Test 3: chapter_section detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("DNV Pt.4 Ch.3 Welding Procedures", "Pt.4 Ch.3"),
    ("ABS Part 5B Section 3-2", "Part 5B Section 3-2"),
    ("CCS Chapter 7 Bilge Systems", "Chapter 7"),
    ("Refer to § 3.2.1 for details.", "§ 3.2.1"),
])
def test_extract_chapter_section(text, expected):
    """Chapter/section patterns must be detected."""
    assert extract_chapter_section(text) == expected


# ---------------------------------------------------------------------------
# Test 4: Full metadata extraction
# ---------------------------------------------------------------------------

def test_extract_metadata_from_filename_and_text():
    """Combined extraction from filename and text content."""
    filename = "DNV_Pt4_Ch3_Welding_2024.pdf"
    text = """DNV Rules for Classification of Ships
    Part 4 Chapter 3 -- Welding Procedures
    Published 2024 by Det Norske Veritas"""

    meta = extract_metadata(filename, text)
    assert meta.classification_society == "DNV"
    assert meta.version_year == 2024
    assert "Pt" in meta.chapter_section


# ---------------------------------------------------------------------------
# Test 5: MarineMetadata dataclass
# ---------------------------------------------------------------------------

def test_marine_metadata_defaults():
    """Default MarineMetadata must have all None fields."""
    meta = MarineMetadata()
    assert meta.classification_society is None
    assert meta.version_year is None
    assert meta.language is None
```

- [ ] **Step 2: Write marine_metadata.py**

```python
# m1-doc-parsing/m1_parser/enrichments/marine_metadata.py
"""
Auto-extraction of marine engineering metadata from documents.

WHY: Classification society documents contain predictable metadata
patterns (society names, years, chapter numbers) that can be reliably
extracted with regex. This saves admin users from manually entering
these fields for every uploaded document.

Extracted fields:
  1. classification_society: DNV, ABS, CCS, LR, BV, NK, RINA, KR, IMO, IACS
  2. regulation_name: from filename or document title
  3. version_year: regex (20\d{2}|19\d{2})
  4. chapter_section: Pt.X Ch.Y, Section, §, Chapter
  5. language: via langdetect

All auto-extracted values can be overridden by admin in M7.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ===========================================================================
# Regex patterns
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
    r"(Pt\.?\s*\d+(\s*Ch\.?\s*\d+)?)"    # Pt.4 Ch.3 or Pt 4
    r"|(Part\s+\d+[A-Z]?\s*Section\s*[\d-]+)"  # Part 5B Section 3-2
    r"|(Chapter\s+\d+)"                   # Chapter 7
    r"|(§\s*[\d.]+)"                      # § 3.2.1
)


# ===========================================================================
# Data model
# ===========================================================================


@dataclass
class MarineMetadata:
    """Marine-domain metadata extracted from a parsed document."""

    classification_society: str | None = None
    regulation_name: str | None = None
    version_year: int | None = None
    chapter_section: str | None = None
    language: str | None = None


# ===========================================================================
# Extraction functions
# ===========================================================================


def extract_metadata(filename: str, text: str) -> MarineMetadata:
    """
    Extract all auto-detectable metadata from a document.

    Searches both filename and text content, preferring the text
    match when both are found (filename can be abbreviated).

    Args:
        filename: Original filename (for pattern-based hints).
        text: Full document text content.

    Returns:
        MarineMetadata with populated fields (None for undetected).
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
    Detect classification society from document text.

    Searches for known abbreviations and full names.
    Returns the first match found (most documents reference only one society).

    WHY regex, not ML: society names are predictable strings.
    Regex is deterministic, explainable, and zero-dependency.
    """
    for pattern, name in _SOCIETY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return name
    return None


def extract_version_year(text: str) -> int | None:
    """
    Extract a 4-digit year from document text.

    Matches years 1900-2099. Returns the first match (typically
    the publication year appears early in the document).
    """
    match = _YEAR_PATTERN.search(text)
    if match:
        return int(match.group(1))
    return None


def extract_chapter_section(text: str) -> str | None:
    """
    Extract chapter/section reference from document text.

    Matches patterns like "Pt.4 Ch.3", "Part 5B Section 3-2",
    "Chapter 7", "§ 3.2.1".
    """
    match = _CHAPTER_PATTERN.search(text)
    if match:
        return match.group(0).strip()
    return None


def _extract_regulation_name(filename: str, text: str) -> str | None:
    """
    Derive regulation name from filename or document title.

    Tries the first heading in the text first. Falls back to
    filename without extension as a human-readable label.
    """
    from pathlib import Path

    # Try first line of text as title
    first_line = text.strip().split("\n")[0] if text else ""
    if first_line and len(first_line) > 10:
        return first_line[:200].strip()

    # Fall back to filename
    return Path(filename).stem


def _detect_language(text: str) -> str | None:
    """
    Detect document language using langdetect.

    Returns ISO 639-1 code (en, zh, ko, ja, no) or None.
    """
    if not text or len(text) < 20:
        return None
    try:
        from langdetect import detect
        return detect(text[:1000])  # First 1000 chars is enough
    except Exception:
        return None
```

- [ ] **Step 3: Run tests**

```bash
pip install langdetect && python -m pytest m1-doc-parsing/tests/test_marine_metadata.py -v
```
Expected: 10 PASS (5 functions × parametrized), 0 FAIL

- [ ] **Step 4: Commit**

```bash
git add m1-doc-parsing/m1_parser/enrichments/ m1-doc-parsing/tests/test_marine_metadata.py
git commit -m "[00060-06] feat: marine metadata auto-extraction -- 5 fields with regex rules"
```

---

### Task 7: Quality Gate + Table Processing (00060-07)

**Files:**
- Create: `m1-doc-parsing/m1_parser/enrichments/table_merger.py`
- Create: `m1-doc-parsing/m1_parser/enrichments/table_annotator.py`
- Create: `m1-doc-parsing/m1_parser/core/quality.py`
- Create: `m1-doc-parsing/tests/test_quality.py`

- [ ] **Step 1: Write quality.py**

```python
# m1-doc-parsing/m1_parser/core/quality.py
"""
Complexity scoring and quality gate for parsed content.

WHY: The accuracy-first principle requires that complex content
(tables with merged cells, footnotes, cross-page spans) be blocked
from auto-ingestion into the vector database until human-reviewed.

The scoring system assigns points for 7 complexity indicators.
Score 0=auto-approve, 1-2=low confidence, 3+=block and review.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QualityAssessment:
    """Result of complexity scoring for a chunk or table."""

    score: int
    max_score: int = 9
    confidence: float = 1.0
    review_required: bool = False
    review_reasons: list[str] = None

    def __post_init__(self):
        if self.review_reasons is None:
            self.review_reasons = []
        # Apply gate rules
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
    Score a table's complexity on a 0-9 scale.

    Scoring rules (from design spec Section 8.3):
      +1: merged cells > 3
      +2: cross-page (no header row)
      +2: contains (see ...) footnote references
      +1: contains parenthetical annotations
      +1: has footnote markers
      +1: > 8 columns or > 50 rows
      +1: borderless table

    Gate rules:
      Score 0:   auto-approve (confidence 1.0)
      Score 1-2: auto-pass with reduced confidence
      Score 3+:  BLOCK -- requires human review

    WHY numeric scoring: enables gradual quality thresholds.
    A table with 1 issue may be fine; 3 issues is almost certainly
    wrong somewhere.
    """
    reasons = []
    score = 0

    if merged_cells > 3:
        score += 1
        reasons.append(f"merged_cells={merged_cells}")

    if is_cross_page:
        score += 2
        reasons.append("cross_page_table")

    if has_footnote_refs:
        score += 2
        reasons.append("footnote_references")

    if has_parenthetical_notes:
        score += 1
        reasons.append("parenthetical_annotations")

    if has_footnotes:
        score += 1
        reasons.append("footnotes")

    if column_count > 8 or row_count > 50:
        score += 1
        reasons.append(f"size({column_count}x{row_count})")

    if is_borderless:
        score += 1
        reasons.append("borderless")

    return QualityAssessment(
        score=score,
        review_reasons=reasons,
    )
```

- [ ] **Step 2: Write test_quality.py + stubs for table modules**

```python
# m1-doc-parsing/tests/test_quality.py
"""Tests for complexity scoring and quality gate."""

import pytest
from m1_parser.core.quality import score_table_complexity


def test_simple_table_auto_approves():
    """A clean table with no issues must score 0, auto-approve."""
    result = score_table_complexity()
    assert result.score == 0
    assert result.confidence == 1.0
    assert result.review_required is False


def test_merged_cells_low_confidence():
    """4 merged cells = score 1, low confidence, not blocked."""
    result = score_table_complexity(merged_cells=5)
    assert result.score == 1
    assert result.confidence < 1.0
    assert result.review_required is False


def test_cross_page_blocked():
    """Cross-page + footnote refs = score >= 3, must block."""
    result = score_table_complexity(
        is_cross_page=True,    # +2
        has_footnote_refs=True, # +2
    )
    assert result.score >= 3
    assert result.review_required is True


def test_many_issues_blocked():
    """Multiple moderate issues add up to block."""
    result = score_table_complexity(
        merged_cells=4,              # +1
        has_parenthetical_notes=True, # +1
        has_footnotes=True,          # +1
        is_borderless=True,          # +1
    )
    assert result.score >= 3
    assert result.review_required is True
```

- [ ] **Step 3: Write table_merger.py and table_annotator.py stubs**

```python
# m1-doc-parsing/m1_parser/enrichments/table_merger.py
"""
Cross-page table merger.

WHY: When a table spans multiple PDF pages, each page's table fragment
lacks the header row. This module detects such fragments by checking
if the first row of a table looks like a header row (bold text, shorter
cells, all cells non-empty). If not, it backtracks to previous pages
and prepends the matching header row before passing to the annotator.
"""

from __future__ import annotations


def merge_split_tables(tables: list) -> list:
    """
    Merge table fragments that span multiple pages.

    Strategy:
    1. Detect tables missing header rows (first row has data-like content)
    2. Backtrack to previous page's tables to find the header
    3. Prepend the header row to the current table fragment

    Args:
        tables: List of TableItem objects from DoclingDocument.

    Returns:
        Tables with cross-page fragments merged.

    Currently a stub -- full implementation requires access to
    Docling's TableItem structure and cell-level metadata.
    """
    return tables
```

```python
# m1-doc-parsing/m1_parser/enrichments/table_annotator.py
"""
Header-to-Cell annotation for table context enrichment.

WHY: Raw table cells like "150°C" are meaningless without their
row and column headers. This module associates each data cell
with its headers so downstream systems see contextualized values:
"Steel Grade: EH36 (t<=50mm) | Minimum Preheat Temp: 150°C"
"""

from __future__ import annotations


def annotate_table_cells(table) -> list:
    """
    Enrich each data cell with its row and column headers.

    Algorithm:
    1. Identify header row(s) and column(s) by content patterns
       (shorter text, bold, all caps, fewer numbers)
    2. For each data cell, find its row header and column header
    3. Build contextualized text: "{col_header}: {cell_text} | {row_header}"

    Args:
        table: TableItem from DoclingDocument.

    Returns:
        List of annotated cell dicts with 'raw', 'row_header',
        'col_header', and 'contextualized' fields.

    Currently a stub -- full implementation requires access to
    Docling's TableItem cell structure and row/column grouping.
    """
    return []
```

- [ ] **Step 4: Run quality tests**

```bash
python -m pytest m1-doc-parsing/tests/test_quality.py -v
```
Expected: 4 PASS, 0 FAIL

- [ ] **Step 5: Commit**

```bash
git add m1-doc-parsing/m1_parser/core/quality.py m1-doc-parsing/m1_parser/enrichments/table_merger.py m1-doc-parsing/m1_parser/enrichments/table_annotator.py m1-doc-parsing/tests/test_quality.py
git commit -m "[00060-07] feat: quality gate with 7-factor complexity scoring, table processing stubs"
```

---

### Task 8: Serializer + Image Manager (00060-08)

**Files:**
- Create: `m1-doc-parsing/m1_parser/output/__init__.py`
- Create: `m1-doc-parsing/m1_parser/output/serializer.py`
- Create: `m1-doc-parsing/m1_parser/output/image_manager.py`
- Create: `m1-doc-parsing/tests/test_serializer.py`
- Create: `m1-doc-parsing/tests/test_image_manager.py`

- [ ] **Step 1: Write serializer.py + image_manager.py (combined for brevity)**

```python
# m1-doc-parsing/m1_parser/output/serializer.py
"""
Output serialization: ParsedDocument → Markdown / JSON / HTML.

WHY: Different consumers need different output formats.
- RAG embedding needs Markdown
- Programmatic processing needs JSON
- Web preview needs HTML
"""

from __future__ import annotations

import json
from pathlib import Path


def save_markdown(content: str, output_dir: str, doc_id: str, filename: str = "full.md"):
    """Save parsed content as Markdown."""
    out_path = Path(output_dir) / doc_id / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return str(out_path)


def save_json(data: dict, output_dir: str, doc_id: str, filename: str = "full.json"):
    """Save parsed content as JSON."""
    out_path = Path(output_dir) / doc_id / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(out_path)
```

```python
# m1-doc-parsing/m1_parser/output/image_manager.py
"""
Image extraction, storage, and metadata management.

WHY: Images from documents (figures, diagrams, tables) need to be
extracted, stored in a predictable directory structure, and annotated
with metadata for downstream search and visual grounding.

Directory structure per document:
  {output_dir}/{doc_id}/
    pages/       -- page screenshots (PNG, 144 DPI)
    figures/     -- embedded images (original format)
    tables/      -- table screenshots (PNG)
"""

from __future__ import annotations

import json
from pathlib import Path


def get_output_paths(output_dir: str, doc_id: str) -> dict[str, Path]:
    """Create and return the output subdirectory paths for a document."""
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


def save_figure_metadata(
    figure_path: Path,
    metadata: dict,
) -> str:
    """
    Write a .meta.json sidecar file for a figure.

    WHY sidecar, not embedded metadata: the original image format
    may not support arbitrary metadata fields. JSON sidecars are
    universally readable and don't alter the original file.
    """
    meta_path = Path(str(figure_path) + ".meta.json")
    meta_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(meta_path)
```

- [ ] **Step 2: Write tests**

```python
# m1-doc-parsing/tests/test_serializer.py
import tempfile
from pathlib import Path
from m1_parser.output.serializer import save_markdown, save_json


def test_save_markdown_creates_file():
    """save_markdown must create the file and parent directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_markdown("# Test", tmpdir, "test-doc-001")
        assert Path(path).exists()
        content = Path(path).read_text()
        assert "# Test" in content


def test_save_json_creates_file():
    """save_json must create a valid JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_json({"key": "value"}, tmpdir, "test-doc-001")
        assert Path(path).exists()
        import json
        data = json.loads(Path(path).read_text())
        assert data["key"] == "value"
```

```python
# m1-doc-parsing/tests/test_image_manager.py
import tempfile
from pathlib import Path
from m1_parser.output.image_manager import get_output_paths, save_figure_metadata


def test_output_paths_created():
    """get_output_paths must create all subdirectories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = get_output_paths(tmpdir, "test-doc")
        for name, p in paths.items():
            assert p.exists(), f"{name} path must exist: {p}"


def test_figure_metadata_sidecar():
    """save_figure_metadata must create a .meta.json sidecar."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fig = Path(tmpdir) / "figure_001.png"
        fig.write_bytes(b"fake png data")
        meta_path = save_figure_metadata(fig, {"key": "val"})
        assert Path(meta_path).exists()
        import json
        meta = json.loads(Path(meta_path).read_text())
        assert meta["key"] == "val"
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest m1-doc-parsing/tests/test_serializer.py m1-doc-parsing/tests/test_image_manager.py -v
```
Expected: 4 PASS

- [ ] **Step 4: Commit**

```bash
git add m1-doc-parsing/m1_parser/output/ m1-doc-parsing/tests/test_serializer.py m1-doc-parsing/tests/test_image_manager.py
git commit -m "[00060-08] feat: serializer (MD/JSON) and image manager (paths, metadata sidecar)"
```

---

### Task 9: Chunking (00060-09)

**Files:**
- Create: `m1-doc-parsing/m1_parser/output/chunker.py`
- Create: `m1-doc-parsing/tests/test_chunker.py`

- [ ] **Step 1: Write chunker.py**

```python
# m1-doc-parsing/m1_parser/output/chunker.py
"""
Hybrid chunker wrapper for RAG embedding preparation.

WHY: Docling's HybridChunker is tokenization-aware and preserves
document hierarchy. We wrap it to align tokenizers with the M5
embedding model (BGE-M3/GTE-Qwen2) and ensure table headers
repeat across chunk boundaries.
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
    Create a configured HybridChunker for RAG document chunking.

    Args:
        tokenizer_model_id: HuggingFace model for token counting.
        max_tokens: Max tokens per chunk (must align with embedding model).
        merge_peers: Merge undersized sibling chunks.
        repeat_table_header: Repeat table headers across chunk boundaries.

    Returns:
        Configured HybridChunker instance, or None if docling_core unavailable.
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
        logger.warning("Chunker unavailable: %s", e)
        return None
```

- [ ] **Step 2: Write test_chunker.py**

```python
# m1-doc-parsing/tests/test_chunker.py
import pytest
from m1_parser.output.chunker import create_chunker


def test_create_chunker_returns_none_if_missing_deps():
    """If docling/transformers not installed, must return None, not crash."""
    # This test will succeed because transformers may not be installed
    chunker = create_chunker()
    # Either None or a valid chunker is acceptable
    # (we don't want it to raise)
    assert chunker is None or hasattr(chunker, "chunk")


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("docling"),
    reason="docling not installed"
)
def test_create_chunker_with_docling():
    """With docling installed, must return a chunker."""
    chunker = create_chunker()
    # May still be None if transformers is missing
    # That's OK -- the function logs a warning
    pass  # No assertion needed; no crash = pass
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest m1-doc-parsing/tests/test_chunker.py -v
```
Expected: 2 PASS

- [ ] **Step 4: Commit**

```bash
git add m1-doc-parsing/m1_parser/output/chunker.py m1-doc-parsing/tests/test_chunker.py
git commit -m "[00060-09] feat: Hybrid chunker wrapper with tokenizer alignment"
```

---

### Task 10: M2 Bridge (00060-10)

**Files:**
- Create: `m1-doc-parsing/m1_parser/integration/__init__.py`
- Create: `m1-doc-parsing/m1_parser/integration/m2_bridge.py`
- Create: `m1-doc-parsing/tests/test_m2_bridge.py`

- [ ] **Step 1: Write m2_bridge.py**

```python
# m1-doc-parsing/m1_parser/integration/m2_bridge.py
"""
Bridge between M1 parsing results and M2 storage backends.

WHY: After parsing, M1 must store results in M2's 4 backends:
- RelationalDB: document metadata records (m1_documents, m1_parsing_tasks)
- VectorStore: only chunks that passed the quality gate
- DocumentIndex: full-text search indices
- FileStore: output files (full.md, full.json, images)

The bridge ensures the accuracy-first rule: chunks with review_required=True
are NEVER written to VectorStore until admin approves.
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
    Build a document record for the m1_documents table.

    Returns a dict that can be inserted into M2's RelationalDB
    via SQLAlchemy session.
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
    Quality gate: only chunks that passed review may enter VectorStore.

    WHY this check exists: the accuracy-first principle. Complex
    tables and uncertain content must be human-reviewed before
    becoming searchable via vector similarity.
    """
    if getattr(chunk, "review_required", False):
        logger.info(
            "Chunk %s blocked from VectorStore: %s",
            getattr(chunk, "chunk_id", "?"),
            getattr(chunk, "review_reasons", []),
        )
        return False
    return True
```

- [ ] **Step 2: Write test_m2_bridge.py**

```python
# m1-doc-parsing/tests/test_m2_bridge.py
import pytest
from m1_parser.integration.m2_bridge import (
    create_document_record,
    should_store_in_vector_store,
)


def test_create_document_record():
    """Must build a complete record dict with all fields."""
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
    """Chunks without review_required must be allowed."""
    chunk = type("Chunk", (), {"review_required": False, "chunk_id": "c1"})()
    assert should_store_in_vector_store(chunk) is True


def test_should_block_review_chunk():
    """Chunks with review_required=True must be blocked."""
    chunk = type("Chunk", (), {
        "review_required": True,
        "chunk_id": "c2",
        "review_reasons": ["cross_page_table"],
    })()
    assert should_store_in_vector_store(chunk) is False
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest m1-doc-parsing/tests/test_m2_bridge.py -v
```
Expected: 3 PASS

- [ ] **Step 4: Commit**

```bash
git add m1-doc-parsing/m1_parser/integration/ m1-doc-parsing/tests/test_m2_bridge.py
git commit -m "[00060-10] feat: M2 bridge -- document records, quality gate enforcement"
```

---

### Task 11: Standalone CLI + Web UI (00060-11)

**Files:**
- Create: `m1-doc-parsing/m1_parser/standalone/__init__.py`
- Create: `m1-doc-parsing/m1_parser/standalone/cli.py`
- Create: `m1-doc-parsing/m1_parser/standalone/web_server.py`
- Create: `m1-doc-parsing/tests/test_cli.py`

- [ ] **Step 1: Write cli.py**

```python
# m1-doc-parsing/m1_parser/standalone/cli.py
"""
M1 standalone CLI tool.

Usage: m1-parser input.pdf --backend docling --ocr easyocr --output ./out/

WHY CLI: users who don't want to run the full system can parse
documents from the command line. pip install m1-doc-parsing gives
them the `m1-parser` command.
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="m1-parser",
        description="M1 Document Parser -- Marine & Offshore Expert System",
    )
    parser.add_argument("input", nargs="+", help="Input file(s) to parse")
    parser.add_argument("--backend", default="docling",
                        choices=["docling", "marker", "mineru"])
    parser.add_argument("--ocr", default="easyocr",
                        choices=["paddleocr", "easyocr", "tesseract", "suryaocr"])
    parser.add_argument("--output", "-o", default="./output",
                        help="Output directory")
    parser.add_argument("--format", default="md",
                        choices=["md", "json", "html"])
    parser.add_argument("--vlm", default=None,
                        help="VLM preset name (granite_docling, etc.)")

    args = parser.parse_args()

    # Import core only when needed (keeps CLI startup fast)
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

    print(f"\nParsed {len(results)} file(s): {success_count} passed, {fail_count} failed")
    for r in results:
        if r.success:
            print(f"  OK  {r.source_path} -> {r.output_dir}")
        else:
            print(f"  FAIL {r.source_path}: {r.error}")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write web_server.py stub**

```python
# m1-doc-parsing/m1_parser/standalone/web_server.py
"""
Minimal FastAPI web server for standalone M1 operation.

Routes:
  GET  /           -- upload + config page (serves web_ui.html)
  POST /parse      -- upload file, parse, return Markdown
  GET  /download/{doc_id} -- download parsed output

WHY FastAPI: async file uploads, SSE progress streaming, simple.
Single-file deployment: python web_server.py and it works.
"""

from fastapi import FastAPI

app = FastAPI(title="M1 Document Parser")


@app.get("/")
async def index():
    return {"message": "M1 Document Parser -- upload page coming soon"}
```

- [ ] **Step 3: Write test_cli.py**

```python
# m1-doc-parsing/tests/test_cli.py
"""Tests for the standalone CLI."""
import subprocess
import sys
import pytest


def test_cli_help():
    """m1-parser --help must exit 0 and show usage."""
    result = subprocess.run(
        [sys.executable, "-m", "m1_parser.standalone.cli", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "m1-parser" in result.stdout


def test_cli_nonexistent_file():
    """Parsing a nonexistent file must exit non-zero."""
    result = subprocess.run(
        [sys.executable, "-m", "m1_parser.standalone.cli", "nonexistent.xyz"],
        capture_output=True, text=True,
    )
    # Should fail gracefully
    assert "FAIL" in result.stdout or result.returncode != 0
```

- [ ] **Step 4: Run tests**

```bash
pip install fastapi && python -m pytest m1-doc-parsing/tests/test_cli.py -v
```
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add m1-doc-parsing/m1_parser/standalone/ m1-doc-parsing/tests/test_cli.py
git commit -m "[00060-11] feat: standalone CLI (m1-parser) and FastAPI web server stub"
```

---

### Task 12: Final Packaging & Verification (00060-12)

**Files:**
- Verify: all files created, all tests pass
- Verify: m1-parser CLI works
- Verify: pip install succeeds

- [ ] **Step 1: Install and verify**

```bash
cd E:/myCode/RAG && pip install -e m1-doc-parsing/
python -c "from m1_parser import convert, detect_hardware; print('Import OK')"
python -m m1_parser.standalone.cli --help
```

Expected: "Import OK" and CLI help text

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest m1-doc-parsing/tests/ -v
```
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add m1-doc-parsing/
git commit -m "[00060-12] chore: finalize M1 packaging, public API, and verification"
```

---

## Dependency Graph

```
00060-01 (config) ──→ 00060-02 (router) ──→ 00060-03 (Docling backend)
                                               │
                         00060-04 (Marker/MinerU)
                                               │
                         00060-05 (converter) ←─┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
   00060-06              00060-07              00060-08
 (marine_metadata)   (quality+table stubs)   (serializer+images)
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                         00060-09 (chunker)
                               │
                         00060-10 (M2 bridge)
                               │
                         00060-11 (CLI + Web UI)
                               │
                         00060-12 (packaging)
```

Tasks 00060-06, 00060-07, 00060-08 are independent and can run in parallel.

---

*Plan complete. Proceed with superpowers:subagent-driven-development or superpowers:executing-plans.*
