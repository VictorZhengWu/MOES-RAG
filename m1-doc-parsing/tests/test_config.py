# -*- coding: utf-8 -*-
"""
Unit tests for config.py -- hardware detection and backend/OCR engine selection.

WHY: GPU detection and backend recommendation is the very first operation
performed at M1 startup. Wrong detection = wrong defaults = poor performance
or outright crashes. These tests verify all 4 tiered recommendation paths
by mocking hardware capabilities.
"""

import platform
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Pre-seed sys.modules with a fake torch to prevent @patch decorators
# from attempting to import the real (potentially broken) torch package.
# WHY: This machine has a torch installation with missing CUDA shared
# libraries, causing import errors when unittest.mock tries to resolve
# "torch.cuda.is_available" during patch context __enter__.
# ---------------------------------------------------------------------------
if "torch" not in sys.modules:
    _fake_torch = MagicMock()
    _fake_torch.cuda = MagicMock()
    _fake_torch.cuda.is_available = MagicMock()
    _fake_torch.cuda.get_device_properties = MagicMock()
    sys.modules["torch"] = _fake_torch

from m1_parser.core.config import (
    HardwareProfile,
    detect_hardware,
    recommend_ocr_engine,
    SUPPORTED_BACKENDS,
    OCR_ENGINE_PRIORITY,
)


# ---------------------------------------------------------------------------
# Test 1: GPU >= 8GB + Linux -> recommend vLLM + PaddleOCR-VL
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=True)
@patch("torch.cuda.get_device_properties")
@patch.object(platform, "system", return_value="Linux")
def test_gpu_8gb_linux_recommends_vllm(mock_system, mock_props, mock_avail):
    """GPU >= 8GB on Linux MUST recommend vLLM + PaddleOCR-VL."""
    # Simulate 12 GB VRAM (e.g., RTX 4070)
    mock_props.return_value.total_memory = 12 * 1024**3  # 12 GB
    profile = detect_hardware()
    assert profile.gpu is True
    assert profile.vram_gb == 12.0
    assert profile.recommended_backend == "paddleocr_vl"
    assert profile.can_use_vllm is True


# ---------------------------------------------------------------------------
# Test 2: GPU >= 8GB + Windows -> recommend Transformers + GraniteDocling
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=True)
@patch("torch.cuda.get_device_properties")
@patch.object(platform, "system", return_value="Windows")
def test_gpu_8gb_windows_recommends_transformers(mock_system, mock_props, mock_avail):
    """GPU >= 8GB on Windows MUST recommend Transformers engine."""
    # Simulate 10 GB VRAM (e.g., RTX 3080)
    mock_props.return_value.total_memory = 10 * 1024**3
    profile = detect_hardware()
    assert profile.gpu is True
    assert profile.recommended_backend == "granite_docling"
    assert profile.can_use_vllm is False


# ---------------------------------------------------------------------------
# Test 3: GPU < 8GB -> recommend Standard Pipeline
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=True)
@patch("torch.cuda.get_device_properties")
def test_gpu_low_vram_recommends_standard(mock_props, mock_avail):
    """GPU with insufficient VRAM MUST recommend Standard Pipeline."""
    # Simulate 6 GB VRAM (e.g., RTX 2060)
    mock_props.return_value.total_memory = 6 * 1024**3
    profile = detect_hardware()
    assert profile.recommended_backend == "docling_standard"


# ---------------------------------------------------------------------------
# Test 4: No GPU -> recommend CPU mode + EasyOCR
# ---------------------------------------------------------------------------

@patch("torch.cuda.is_available", return_value=False)
def test_no_gpu_recommends_cpu(mock_avail):
    """No GPU MUST recommend CPU mode + EasyOCR."""
    profile = detect_hardware()
    assert profile.gpu is False
    assert profile.vram_gb == 0
    assert profile.recommended_backend == "docling_standard"
    assert profile.recommended_ocr == "easyocr"
    assert profile.can_use_vllm is False


# ---------------------------------------------------------------------------
# Test 5: OCR engine priority ordering
# ---------------------------------------------------------------------------

def test_ocr_priority_order():
    """PaddleOCR MUST rank first, Tesseract MUST rank last."""
    assert OCR_ENGINE_PRIORITY[0] == "paddleocr"
    assert OCR_ENGINE_PRIORITY[-1] == "tesseract"


# ---------------------------------------------------------------------------
# Test 6: Supported backends list
# ---------------------------------------------------------------------------

def test_supported_backends():
    """All three backend types MUST be present in the supported list."""
    assert "docling" in SUPPORTED_BACKENDS
    assert "marker" in SUPPORTED_BACKENDS
    assert "mineru" in SUPPORTED_BACKENDS
