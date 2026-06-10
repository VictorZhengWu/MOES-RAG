"""Tests for Agent_Regulations (FR-3)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from m5_qa.research.agents.regulations import (
    agent_regulations,
    _lookup_iso_standards,
    ISO_STANDARDS,
)


# ---------------------------------------------------------------------------
# ISO lookup tests (unit, no M3/M4 needed)
# ---------------------------------------------------------------------------

def test_iso_lookup_found():
    """Query mentioning ISO 5817 must return that standard."""
    results = _lookup_iso_standards("What is ISO 5817 welding quality level?")
    assert len(results) == 1
    assert results[0]["source"] == "iso"
    assert "ISO 5817" in results[0]["text"]


def test_iso_lookup_not_found():
    """Query without any ISO standard → empty."""
    assert _lookup_iso_standards("DNV Pt.3 Ch.3 strength requirements") == []


def test_iso_all_standards_defined():
    """All 10 ISO standards must have title and scope."""
    assert len(ISO_STANDARDS) == 10
    for code, info in ISO_STANDARDS.items():
        assert "title" in info, f"{code} missing title"
        assert "scope" in info, f"{code} missing scope"


# ---------------------------------------------------------------------------
# Integration tests (mocked M3/M4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regulations_with_m3():
    """When M3 returns results, they must be included."""
    mock_m3 = AsyncMock()
    mock_context = MagicMock()
    mock_context.chunks = [
        (MagicMock(chunk_id="c1", text="DNV Pt.3 Ch.3 §6.2 requires strength ≥ 1.5× load",
                   metadata={}), 0.85),
    ]
    mock_m3.retrieve.return_value = mock_context

    plan = [{"id": 1, "search_query": "DNV hatch cover", "search_strategy": ["regulations"]}]
    results = await agent_regulations(plan, m3_engine=mock_m3)

    assert len(results) >= 1
    assert any("DNV" in r["text"] for r in results)


@pytest.mark.asyncio
async def test_regulations_empty_when_no_engines():
    """When no engines are provided, must return empty list (no crash)."""
    plan = [{"id": 1, "search_query": "test", "search_strategy": ["regulations"]}]
    results = await agent_regulations(plan)
    assert results == []


@pytest.mark.asyncio
async def test_regulations_skips_non_regulation_questions():
    """Sub-questions without 'regulations' strategy must be skipped."""
    plan = [{"id": 1, "search_query": "test", "search_strategy": ["web"]}]
    results = await agent_regulations(plan)
    assert results == []


@pytest.mark.asyncio
async def test_regulations_with_iso():
    """Query with ISO standard should get ISO info even without M3."""
    plan = [{"id": 1, "search_query": "ISO 9712 NDT qualification", "search_strategy": ["regulations"]}]
    results = await agent_regulations(plan)
    assert len(results) >= 1
    assert any(r["source"] == "iso" for r in results)


@pytest.mark.asyncio
async def test_regulations_graceful_on_m3_error():
    """M3 failure must not crash — return empty and log warning."""
    mock_m3 = AsyncMock()
    mock_m3.retrieve.side_effect = Exception("M3 down")

    plan = [{"id": 1, "search_query": "test", "search_strategy": ["regulations"]}]
    results = await agent_regulations(plan, m3_engine=mock_m3)
    # Should return empty but not crash
    assert isinstance(results, list)
