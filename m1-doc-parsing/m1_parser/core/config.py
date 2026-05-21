# -*- coding: utf-8 -*-
"""
M1 hardware detection and configuration management.

WHY: M1 runs on diverse hardware (from GPU-less laptops to GPU servers).
Auto-detection eliminates manual setup guesswork and ensures each deployment
environment gets its optimal configuration. The tiered recommendation system
maps 4 hardware profiles to the most efficient backend+OCR combination.

Key decisions:
  - vLLM only supports Linux (depends on Linux kernel features)
  - PaddleOCR-VL-1.5 requires ~4.2GB VRAM (or 230MB with INT8 quantization)
  - GraniteDocling-258M is the safest cross-platform VLM
  - EasyOCR is the most reliable CPU fallback
"""

from __future__ import annotations

import platform
from dataclasses import dataclass

# ===========================================================================
# Constants
# ===========================================================================

SUPPORTED_BACKENDS: list[str] = ["docling", "marker", "mineru"]

OCR_ENGINE_PRIORITY: list[str] = [
    "paddleocr",
    "suryaocr",
    "easyocr",
    "tesseract",
]

VLM_PRESETS: list[str] = [
    "granite_docling",
    "paddleocr_vl",
    "deepseek_ocr",
    "smoldocling",
    "granite_vision",
]


# ===========================================================================
# Hardware profile data model
# ===========================================================================


@dataclass
class HardwareProfile:
    """
    Detected hardware capabilities and recommended configuration.

    WHY dataclass instead of dict: type-safe consumers (M7 config page)
    can rely on field existence and types without try/except KeyError.
    """

    gpu: bool
    vram_gb: float
    recommended_backend: str  # "docling_standard" | "paddleocr_vl" | ...
    recommended_ocr: str      # "paddleocr" | "easyocr" | ...
    can_use_vllm: bool        # True only for Linux + GPU


@dataclass
class M1Config:
    """
    M1-specific configuration parsed from deploy.yaml.

    WHY separate from HardwareProfile: HardwareProfile is auto-detected
    at runtime; M1Config carries user overrides from the deployment config.
    The two combine at startup: M1Config overrides HardwareProfile defaults
    when the user has explicitly set backend/OCR preferences.

    Fields:
      - backend_override: force a specific backend (docling/marker/mineru)
      - ocr_override: force a specific OCR engine
      - output_dir: where to write output files
      - quality_threshold: minimum acceptable quality score (1-5)
    """

    backend_override: str | None = None
    ocr_override: str | None = None
    output_dir: str = "./output"
    quality_threshold: int = 3


def detect_hardware() -> HardwareProfile:
    """
    Detect GPU and OS, returning a tiered configuration recommendation.

    Detection logic (4 tiers):
    1. GPU >= 8GB + Linux  -> vLLM + PaddleOCR-VL-1.5 (fastest)
    2. GPU >= 8GB + Windows -> Transformers + GraniteDocling (cross-platform)
    3. GPU < 8GB            -> Standard Pipeline (or INT8 VLM)
    4. No GPU               -> EasyOCR CPU mode

    WHY tiered: vLLM is Linux-only. PaddleOCR-VL needs 4.2GB+ VRAM.
    Auto-detection prevents recommending a config that simply won't run.
    """
    try:
        import torch
        gpu_available = torch.cuda.is_available()
    except ImportError:
        # torch not installed -- fall back to nvidia-smi subprocess check.
        # WHY: some deployments have GPU drivers but not PyTorch.
        # nvidia-smi can confirm GPU presence even without torch.
        if _check_nvidia_smi():
            return HardwareProfile(
                gpu=True,
                vram_gb=0.0,  # VRAM unknown but GPU confirmed present
                recommended_backend="docling_standard",
                recommended_ocr="paddleocr",
                can_use_vllm=False,
            )
        gpu_available = False

    if gpu_available:
        vram_bytes: int = torch.cuda.get_device_properties(0).total_memory
        vram_gb: float = vram_bytes / (1024**3)
        is_linux: bool = platform.system() == "Linux"

        if vram_gb >= 8:
            if is_linux:
                return HardwareProfile(
                    gpu=True,
                    vram_gb=vram_gb,
                    recommended_backend="paddleocr_vl",
                    recommended_ocr="paddleocr",
                    can_use_vllm=True,
                )
            else:
                return HardwareProfile(
                    gpu=True,
                    vram_gb=vram_gb,
                    recommended_backend="granite_docling",
                    recommended_ocr="paddleocr",
                    can_use_vllm=False,
                )
        else:
            # GPU present but insufficient VRAM for VLM acceleration
            return HardwareProfile(
                gpu=True,
                vram_gb=vram_gb,
                recommended_backend="docling_standard",
                recommended_ocr="paddleocr",
                can_use_vllm=False,
            )
    else:
        # CPU-only -- no GPU detected or torch not installed
        return HardwareProfile(
            gpu=False,
            vram_gb=0,
            recommended_backend="docling_standard",
            recommended_ocr="easyocr",
            can_use_vllm=False,
        )


def _check_nvidia_smi() -> bool:
    """
    Detect NVIDIA GPU presence via the nvidia-smi CLI tool.

    WHAT: runs ``nvidia-smi --query-gpu=memory.total --format=csv,noheader``
    with a 5-second timeout. Returns True if the command succeeds.

    WHY: when torch is not installed, we can still detect GPU hardware
    through the NVIDIA driver's management interface. This provides a
    graceful degradation path: GPU exists but PyTorch is missing.
    """
    import subprocess
    try:
        subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader"],
            capture_output=True,
            timeout=5,
            check=True,
        )
        return True
    except Exception:
        # FileNotFoundError: nvidia-smi not installed
        # CalledProcessError: command failed
        # TimeoutExpired: hung process
        return False


def recommend_ocr_engine(preferred: str | None = None) -> str:
    """
    Return the first available OCR engine from the priority list.

    Attempts in order: PaddleOCR -> SuryaOCR -> EasyOCR -> Tesseract.
    If 'preferred' is given and available, use it directly.

    WHY fallback chain: different environments have different engines
    installed. PaddleOCR may fail to import; EasyOCR is near-universal.
    """
    if preferred and _is_ocr_available(preferred):
        return preferred

    for engine in OCR_ENGINE_PRIORITY:
        if _is_ocr_available(engine):
            return engine
    raise RuntimeError(
        "No OCR engine available. Please install one of: "
        + ", ".join(OCR_ENGINE_PRIORITY)
    )


def _is_ocr_available(engine: str) -> bool:
    """
    Check whether an OCR engine can be imported.

    WHY lazy detection: an import error at startup is far better than
    a runtime crash 5 minutes into parsing a 100-page PDF.
    """
    import_map: dict[str, str] = {
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


def load_m1_config(path: str = "deploy.yaml") -> M1Config:
    """
    Parse M1-specific configuration from deploy.yaml.

    WHAT: reads the ``m1:`` section of deploy.yaml and returns an M1Config
    dataclass with any overrides found. Non-M1 sections are silently ignored.

    WHY: deploy.yaml is the single source of truth for deployment-wide
    settings (storage backends, LLM backends, module configs). M1 reads
    its own section at startup so that operators can set backend/OCR
    preferences once and have them apply consistently across restarts.

    Returns M1Config with defaults when the file is missing or has no
    ``m1:`` section -- this ensures M1 works out-of-the-box without
    deploy.yaml, using only auto-detected hardware recommendations.
    """
    import yaml

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError:
        # No deploy.yaml -- return defaults, rely on auto-detection
        return M1Config()

    m1 = raw.get("m1", {})
    if not isinstance(m1, dict):
        return M1Config()

    return M1Config(
        backend_override=m1.get("backend"),
        ocr_override=m1.get("ocr"),
        output_dir=m1.get("output_dir", "./output"),
        quality_threshold=m1.get("quality_threshold", 3),
    )
