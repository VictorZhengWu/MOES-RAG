"""Tests for Report Generator (FR-5)."""

import pytest
from unittest.mock import AsyncMock, patch

from m5_qa.research.report_generator import (
    generate_report,
    REPORT_TEMPLATE,
    _build_report_prompt,
)


def test_template_has_7_sections():
    """Report template must define all 7 sections."""
    assert "§1" in REPORT_TEMPLATE or "Executive Summary" in REPORT_TEMPLATE
    assert "§2" in REPORT_TEMPLATE or "Comparison Matrix" in REPORT_TEMPLATE
    assert "§3" in REPORT_TEMPLATE or "Technical Recommendations" in REPORT_TEMPLATE
    assert "§4" in REPORT_TEMPLATE or "Inspection Checklist" in REPORT_TEMPLATE
    assert "§5" in REPORT_TEMPLATE or "Risk Matrix" in REPORT_TEMPLATE
    assert "§6" in REPORT_TEMPLATE or "Reference Trace" in REPORT_TEMPLATE
    assert "§7" in REPORT_TEMPLATE or "Limitations" in REPORT_TEMPLATE


def test_prompt_includes_query():
    """Generated prompt must embed the original query."""
    prompt = _build_report_prompt("Test query", [], [], "No conflicts")
    assert "Test query" in prompt


def test_prompt_includes_conflicts():
    """Generated prompt must include conflict information."""
    prompt = _build_report_prompt("Test", [], [], "Conflict A vs B")
    assert "Conflict A vs B" in prompt


@pytest.mark.asyncio
async def test_generate_with_llm():
    """When LLM returns valid markdown, use it."""
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = {
        "choices": [{"message": {"content": "# Research Report\n\n## Executive Summary\n\nTest finding."}}],
    }

    result = await generate_report(
        query="Compare DNV and ABS",
        regulation_results=[],
        web_results=[],
        analysis=None,
        llm_client=mock_llm,
    )
    assert "Research Report" in result or "Test finding" in result


@pytest.mark.asyncio
async def test_generate_fallback_no_llm():
    """Without LLM, return template-based fallback report."""
    result = await generate_report(
        query="Compare DNV and ABS",
        regulation_results=[{"text": "DNV requires 1.5", "source": "regulations"}],
        web_results=[],
        analysis=None,
        llm_client=None,
    )
    assert len(result) > 0
    assert "Comparison Report" in result or "DNV" in result


@pytest.mark.asyncio
async def test_generate_llm_failure_falls_back():
    """When LLM fails, return fallback report (not crash)."""
    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = Exception("LLM timeout")

    result = await generate_report(
        query="Test", regulation_results=[], web_results=[], analysis=None,
        llm_client=mock_llm,
    )
    assert len(result) > 0
