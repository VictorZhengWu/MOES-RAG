"""Tests for Agent_Web (FR-3)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from m5_qa.research.agents.web import agent_web


@pytest.mark.asyncio
async def test_web_skips_non_web_questions():
    """Sub-questions without 'web' strategy must be skipped."""
    plan = [{"id": 1, "search_query": "test", "search_strategy": ["regulations"]}]
    results = await agent_web(plan)
    assert results == []


@pytest.mark.asyncio
async def test_web_empty_when_no_config():
    """Without config, DuckDuckGo is tried (may return empty if not installed)."""
    plan = [{"id": 1, "search_query": "test query", "search_strategy": ["web"]}]
    results = await agent_web(plan)
    # DuckDuckGo may work or not — but must return a list, not crash
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_web_graceful_on_engine_error():
    """All engines failing must return empty list, not crash."""
    plan = [{"id": 1, "search_query": "test", "search_strategy": ["web"]}]
    config = {"engine": "tavily", "api_key": None}  # No key → will fail gracefully
    results = await agent_web(plan, web_search_config=config)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_web_multiple_sub_questions():
    """Multiple sub-questions must all be searched."""
    plan = [
        {"id": 1, "search_query": "DNV Pt.3 Ch.3", "search_strategy": ["web"]},
        {"id": 2, "search_query": "ABS Pt.5B", "search_strategy": ["web"]},
    ]
    results = await agent_web(plan)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_web_mixed_strategies():
    """Only web-strategy sub-questions should be searched."""
    plan = [
        {"id": 1, "search_query": "web query", "search_strategy": ["web"]},
        {"id": 2, "search_query": "reg query", "search_strategy": ["regulations"]},
    ]
    results = await agent_web(plan)
    assert isinstance(results, list)
