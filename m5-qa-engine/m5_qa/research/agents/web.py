"""Agent_Web — live web search for Deep Research.

WHAT: For each sub-question, queries a web search engine (DuckDuckGo,
      Tavily, or Brave) and returns top 3-5 results as structured dicts.

WHY: Maritime regulations and incident reports are frequently published
     online (IMO circulars, MAIB reports, class society news). Web search
     provides up-to-date context that the local vector store may not have.

GRACEFUL DEGRADATION:
    If no web search engine is configured or all calls fail, returns an
    empty list. The research pipeline continues with regulations-only results.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default DuckDuckGo search (no API key needed)
_DEFAULT_ENGINE = "duckduckgo"


async def agent_web(
    sub_questions: list[dict],
    web_search_config: Optional[dict[str, Any]] = None,
) -> list[dict]:
    """Execute web search for each sub-question.

    Args:
        sub_questions: List of {"id", "search_query", "search_strategy", ...}.
        web_search_config: Dict with keys: engine, api_key, base_url.
                           Uses DuckDuckGo by default if not provided.

    Returns:
        List of dicts: [{title, url, snippet, source: "web"}]
    """
    engine_name = (
        web_search_config.get("engine", _DEFAULT_ENGINE)
        if web_search_config
        else _DEFAULT_ENGINE
    )

    all_results: list[dict] = []
    seen_urls: set[str] = set()

    # Phase 4-C (00108-01): Domain-aware query suffix for standards/cases/regulations
    for sq in sub_questions:
        query = sq["search_query"]
        # Append domain suffixes based on search strategy
        if "standards" in sq.get("search_strategy", []):
            query = f"{query} ISO ASTM API standard"
        if "cases" in sq.get("search_strategy", []):
            query = f"{query} marine accident report MAIB NTSB"
        if "regulations_imo" in sq.get("search_strategy", []):
            query = f"{query} IMO SOLAS MARPOL MSC MEPC circular"
        sq["search_query"] = query

    for sq in sub_questions:
        if "web" not in sq.get("search_strategy", []):
            continue
        query = sq["search_query"]

        try:
            results = await _search_web(query, engine_name, web_search_config)
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
        except Exception as e:
            logger.warning("Web search failed for '%s' (engine=%s): %s",
                           query[:40], engine_name, e)

    return all_results


async def _search_web(
    query: str,
    engine_name: str,
    config: Optional[dict] = None,
) -> list[dict]:
    """Dispatch to the appropriate search engine implementation.

    WHY dispatch: Different deployments use different engines:
        Personal → DuckDuckGo (free, no API key)
        Enterprise → Tavily (higher quality, paid)
        SaaS → Brave or Google (enterprise-grade)
    """
    if engine_name == "duckduckgo":
        return await _search_duckduckgo(query)
    elif engine_name == "tavily":
        return await _search_tavily(query, config)
    elif engine_name == "brave":
        return await _search_brave(query, config)
    elif engine_name == "google":
        return await _search_google(query, config)
    else:
        logger.warning("Unknown web search engine: %s, using DuckDuckGo", engine_name)
        return await _search_duckduckgo(query)


async def _search_duckduckgo(query: str) -> list[dict]:
    """Search DuckDuckGo Instant Answer API (no API key needed).

    Uses duckduckgo_search library if installed, otherwise falls back
    to a simple HTML scrape (unreliable but functional).

    WHY DuckDuckGo: zero-config default for Personal mode. No API key,
         no rate limit concerns for Deep Research use case (~10 calls/study).
    """
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "source": "web",
                })
        return results
    except ImportError:
        logger.debug("duckduckgo_search not installed, skipping web search")
        return []
    except Exception as e:
        logger.warning("DuckDuckGo search error: %s", e)
        return []


async def _search_tavily(
    query: str, config: Optional[dict] = None,
) -> list[dict]:
    """Search via Tavily API (requires API key).

    Tavily is optimized for AI research use cases with clean snippets
    and relevance scoring.
    """
    api_key = config.get("api_key") if config else None
    if not api_key:
        logger.warning("Tavily API key not configured, skipping")
        return []

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": 3,
                    "search_depth": "basic",
                },
            )
            if resp.status_code != 200:
                logger.warning("Tavily API error: %s", resp.status_code)
                return []
            data = resp.json()
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                    "source": "web",
                }
                for r in data.get("results", [])
            ]
    except ImportError:
        logger.debug("httpx not installed, skipping Tavily")
        return []
    except Exception as e:
        logger.warning("Tavily search error: %s", e)
        return []


async def _search_brave(
    query: str, config: Optional[dict] = None,
) -> list[dict]:
    """Search via Brave Search API."""
    api_key = config.get("api_key") if config else None
    if not api_key:
        logger.warning("Brave API key not configured, skipping")
        return []

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 3},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": api_key,
                },
            )
            if resp.status_code != 200:
                logger.warning("Brave API error: %s", resp.status_code)
                return []
            data = resp.json()
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("description", ""),
                    "source": "web",
                }
                for r in data.get("web", {}).get("results", [])
            ]
    except ImportError:
        logger.debug("httpx not installed, skipping Brave")
        return []
    except Exception as e:
        logger.warning("Brave search error: %s", e)
        return []


async def _search_google(
    query: str, config: Optional[dict] = None,
) -> list[dict]:
    """Search via Google Custom Search API."""
    api_key = config.get("api_key") if config else None
    cx = config.get("google_cx") if config else None
    if not api_key or not cx:
        logger.warning("Google API key or CX not configured, skipping")
        return []

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": api_key, "cx": cx, "q": query, "num": 3},
            )
            if resp.status_code != 200:
                logger.warning("Google API error: %s", resp.status_code)
                return []
            data = resp.json()
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "snippet": r.get("snippet", ""),
                    "source": "web",
                }
                for r in data.get("items", [])
            ]
    except ImportError:
        logger.debug("httpx not installed, skipping Google")
        return []
    except Exception as e:
        logger.warning("Google search error: %s", e)
        return []
