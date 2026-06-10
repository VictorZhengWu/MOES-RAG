"""Tests for Analysis Agent (FR-4)."""

import pytest
from unittest.mock import AsyncMock, patch

from m5_qa.research.analyzer import (
    extract_requirements,
    detect_conflicts,
    AnalysisResult,
)


# ---------------------------------------------------------------------------
# Rule-based requirement extraction tests (no LLM)
# ---------------------------------------------------------------------------

def test_extract_chinese_requirements():
    """中文数值要求 must be extracted."""
    chunks = [
        {"text": "强度 ≥ 1.5× 设计载荷，板厚 ≥ 12mm", "source": "regulations", "metadata": {"society": "DNV"}},
    ]
    reqs = extract_requirements(chunks)
    assert "强度" in reqs or "板厚" in reqs


def test_extract_english_requirements():
    """English numerical requirements must be extracted."""
    chunks = [
        {"text": "The strength factor shall be >= 1.67 and minimum thickness is 14 mm", "source": "regulations", "metadata": {"society": "ABS"}},
    ]
    reqs = extract_requirements(chunks)
    assert len(reqs) >= 1


def test_extract_empty_input():
    """Empty chunks → empty requirements dict."""
    assert extract_requirements([]) == {}


def test_extract_multi_society():
    """Parameters from different societies must be aggregated."""
    chunks = [
        {"text": "强度 ≥ 1.5× 载荷", "source": "regulations", "metadata": {"society": "DNV"}},
        {"text": "强度 ≥ 1.67× 载荷", "source": "regulations", "metadata": {"society": "ABS"}},
    ]
    reqs = extract_requirements(chunks)
    # Both societies should appear under the same parameter
    for param, values in reqs.items():
        if "载荷" in param or "strength" in param.lower():
            assert "DNV" in values or "ABS" in values


# ---------------------------------------------------------------------------
# Conflict detection tests (no LLM)
# ---------------------------------------------------------------------------

def test_conflict_detected_different_values():
    """Different values for same parameter → conflict."""
    reqs = {"强度系数": {"DNV": 1.5, "ABS": 1.67}}
    conflicts = detect_conflicts(reqs)
    assert len(conflicts) >= 1
    assert conflicts[0]["severity"] in ("warning", "info")


def test_no_conflict_same_values():
    """Same value across societies → no conflict."""
    reqs = {"强度系数": {"DNV": 1.5, "ABS": 1.5}}
    conflicts = detect_conflicts(reqs)
    assert len(conflicts) == 0


def test_no_conflict_single_society():
    """Only one society → no conflict."""
    reqs = {"强度系数": {"DNV": 1.5}}
    conflicts = detect_conflicts(reqs)
    assert len(conflicts) == 0


def test_conflict_mixed_types():
    """String + float values must be comparable."""
    reqs = {"板厚": {"DNV": "12", "ABS": "14.0"}}
    conflicts = detect_conflicts(reqs)
    assert len(conflicts) >= 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_extract_no_numerical():
    """Text without numerical values → empty."""
    chunks = [{"text": "This clause defines the scope of application.", "source": "regulations", "metadata": {}}]
    assert extract_requirements(chunks) == {}


def test_extract_partial_metadata():
    """Chunks without society metadata must still work."""
    chunks = [{"text": "强度 ≥ 1.5× 载荷", "source": "regulations", "metadata": {}}]
    reqs = extract_requirements(chunks)
    assert len(reqs) >= 1
