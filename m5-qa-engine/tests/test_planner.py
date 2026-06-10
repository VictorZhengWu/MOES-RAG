"""Tests for research planner (FR-2).

WHAT: Verifies the planner can decompose queries into sub-questions
      and gracefully handle LLM failures with rule-based fallback.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from m5_qa.research.planner import (
    decompose_query,
    PLANNER_PROMPT,
    MAX_SUB_QUESTIONS,
    _rule_based_decompose,
)


# ---------------------------------------------------------------------------
# JSON parsing tests (no LLM needed)
# ---------------------------------------------------------------------------

def test_parse_valid_json_response():
    """Valid JSON with sub_questions must parse correctly."""
    raw_json = json.dumps({
        "sub_questions": [
            {"id": 1, "question": "DNV Pt.3 Ch.3 requirements",
             "search_strategy": ["regulations"], "search_query": "DNV hatch cover strength"},
            {"id": 2, "question": "ABS comparison",
             "search_strategy": ["regulations", "web"], "search_query": "ABS hatch cover"},
        ],
        "estimated_runtime_seconds": 45,
    })
    plan = decompose_query._parse_plan(raw_json)
    assert len(plan["sub_questions"]) == 2
    assert plan["sub_questions"][0]["id"] == 1
    assert plan["estimated_runtime_seconds"] == 45


def test_parse_json_with_markdown_fence():
    """JSON inside ```json fence must be extracted."""
    raw = '```json\n' + json.dumps({
        "sub_questions": [{"id": 1, "question": "Test", "search_strategy": ["regulations"], "search_query": "test"}],
        "estimated_runtime_seconds": 10,
    }) + '\n```'
    plan = decompose_query._parse_plan(raw)
    assert len(plan["sub_questions"]) == 1


def test_parse_invalid_json_falls_back_to_rules():
    """Invalid JSON must trigger rule-based decomposition, not crash."""
    result = decompose_query._parse_plan("not valid json at all {broken")
    assert len(result["sub_questions"]) >= 1


# ---------------------------------------------------------------------------
# Rule-based decomposition tests (no LLM needed)
# ---------------------------------------------------------------------------

def test_rule_based_single_society():
    """Single society query → 1 sub-question."""
    result = _rule_based_decompose("DNV Pt.3 Ch.3 §6 hatch cover strength")
    assert len(result["sub_questions"]) >= 1
    assert "DNV" in str(result["sub_questions"])


def test_rule_based_multi_society():
    """Multi-society query → 1 sub-question per society."""
    result = _rule_based_decompose("Compare DNV and ABS and CCS bulk carrier requirements")
    # Should create sub-questions for each society
    societies_found = sum(
        1 for sq in result["sub_questions"]
        if any(s.lower() in str(sq).lower() for s in ["DNV", "ABS", "CCS"])
    )
    assert societies_found >= 2


def test_rule_based_no_society():
    """Query with no society → 1 generic sub-question."""
    result = _rule_based_decompose("What is the fatigue life of steel structures?")
    assert len(result["sub_questions"]) >= 1


def test_rule_based_max_limit():
    """Should never exceed MAX_SUB_QUESTIONS."""
    # Query with many societies
    result = _rule_based_decompose(
        "Compare DNV ABS CCS LR BV RINA NK KR IACS IMO requirements"
    )
    assert len(result["sub_questions"]) <= MAX_SUB_QUESTIONS


def test_rule_based_estimated_runtime():
    """Estimated runtime should be reasonable."""
    result = _rule_based_decompose("DNV Pt.3 Ch.3 requirements")
    assert 10 <= result["estimated_runtime_seconds"] <= 120


# ---------------------------------------------------------------------------
# Mocked LLM integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_success_decomposes():
    """When LLM returns valid JSON, use that plan."""
    mock_response = {"choices": [{"message": {"content": json.dumps({
        "sub_questions": [
            {"id": 1, "question": "DNV requirements", "search_strategy": ["regulations"], "search_query": "DNV Pt.3 Ch.3"},
            {"id": 2, "question": "ABS requirements", "search_strategy": ["regulations"], "search_query": "ABS Pt.5B"},
        ],
        "estimated_runtime_seconds": 30,
    })}}]}

    with patch.object(decompose_query, '_call_llm', AsyncMock(return_value=mock_response)):
        plan = await decompose_query("Compare DNV and ABS requirements")

    assert len(plan["sub_questions"]) == 2
    assert plan["estimated_runtime_seconds"] == 30


@pytest.mark.asyncio
async def test_llm_failure_falls_back():
    """When LLM fails, use rule-based decomposition."""
    with patch.object(decompose_query, '_call_llm', AsyncMock(side_effect=Exception("LLM down"))):
        plan = await decompose_query("Compare DNV and ABS requirements")

    assert len(plan["sub_questions"]) >= 1
    assert plan["estimated_runtime_seconds"] > 0


@pytest.mark.asyncio
async def test_llm_invalid_json_falls_back():
    """When LLM returns invalid JSON, use rule-based."""
    mock_response = {"choices": [{"message": {"content": "Sure! Let me think about that... not JSON"}}]}

    with patch.object(decompose_query, '_call_llm', AsyncMock(return_value=mock_response)):
        plan = await decompose_query("Compare DNV and ABS")

    assert len(plan["sub_questions"]) >= 1
