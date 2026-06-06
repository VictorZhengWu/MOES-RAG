"""
M5 QA Engine — Web Search (Pluggable Engines).

WHAT: Multi-engine web search as a supplementary retrieval source.
      Supports DuckDuckGo (free), SearXNG (self-hosted, Baidu/Bing),
      Tavily (paid, AI-optimized), and Brave Search (free tier).

WHY: Different deployments need different search engines:
      - Personal: DuckDuckGo (free, no setup) or SearXNG (Baidu for China)
      - Enterprise: Tavily (highest precision, $0.01/query)
      - SaaS: Brave Search (2000 free/month, then $5/1000)

      All engines return the same list[WebResult] format so the rest of
      the pipeline (formatting, context injection) is engine-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import httpx


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class WebResult:
    """A single web search result — engine-agnostic format."""
    title: str
    url: str
    snippet: str
    source: str = "web"


# ---------------------------------------------------------------------------
# Engine Protocol
# ---------------------------------------------------------------------------


class WebSearchEngine(Protocol):
    """Interface for pluggable web search backends."""

    @property
    def name(self) -> str:
        """Engine identifier: 'duckduckgo', 'searxng', 'tavily', 'brave'."""
        ...

    async def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        """Execute a web search and return normalized results."""
        ...


# ---------------------------------------------------------------------------
# Engine Implementations
# ---------------------------------------------------------------------------


class DuckDuckGoEngine:
    """
    DuckDuckGo Instant Answer API — free, no API key required.

    WHAT: Uses DuckDuckGo's JSON API for instant answers and related topics.
          No authentication, no rate limit for personal use.

    WHY: Default engine for personal mode — zero setup, zero cost.
         Best for English-language technical queries.
         Limitation: may be blocked/unreliable in some regions.
    """

    name: str = "duckduckgo"

    async def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": "1",
                        "skip_disambig": "1",
                    },
                    headers={"User-Agent": "MarineExpertSystem/0.1"},
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()

            results: list[WebResult] = []

            # Primary abstract
            abstract = data.get("AbstractText", "")
            abstract_url = data.get("AbstractURL", "")
            if abstract:
                results.append(WebResult(
                    title=data.get("Heading", query),
                    url=abstract_url,
                    snippet=abstract,
                ))

            # Related topics
            for topic in data.get("RelatedTopics", [])[:max_results - len(results)]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append(WebResult(
                        title=topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                        url=topic.get("FirstURL", ""),
                        snippet=topic.get("Text", ""),
                    ))

            return results[:max_results]
        except Exception:
            return []


class SearXNEngine:
    """
    SearXNG — self-hosted privacy-respecting meta-search engine.

    WHAT: Queries a SearXNG instance. The instance can be configured to
          use Baidu, Bing, Google, or any combination of upstream engines.
          Default endpoint: http://localhost:8888/search?format=json

    WHY: Best option for Chinese users — self-host SearXNG with Baidu + Bing
         as upstream engines. Full control over search sources.
         Also great for enterprise deployments that require data privacy
         (no queries sent to third-party APIs).

    Setup: docker run -d -p 8888:8080 searxng/searxng
           Configure engines in /etc/searxng/settings.yml
    """

    name: str = "searxng"

    def __init__(self, base_url: str = "http://localhost:8888"):
        self._base_url = base_url.rstrip("/")

    async def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "engines": "bing,baidu,google",
                        "language": "zh-CN",
                    },
                    headers={"User-Agent": "MarineExpertSystem/0.1"},
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()

            results: list[WebResult] = []
            for entry in data.get("results", [])[:max_results]:
                results.append(WebResult(
                    title=entry.get("title", ""),
                    url=entry.get("url", ""),
                    snippet=entry.get("content", entry.get("snippet", "")),
                ))
            return results
        except Exception:
            return []


class TavilyEngine:
    """
    Tavily Search API — AI-optimized for RAG applications.

    WHAT: Tavily is purpose-built for AI agent web search. It returns
          cleaned, relevant snippets optimized for LLM consumption.
          Requires an API key (free tier: 1000 queries/month).

    WHY: Highest precision for RAG — results are pre-filtered for relevance
         and formatted for LLM context windows. Recommended for enterprise
         deployments where search quality directly impacts answer quality.

    API: https://tavily.com
    """

    name: str = "tavily"

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                    },
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()

            results: list[WebResult] = []
            for entry in data.get("results", [])[:max_results]:
                results.append(WebResult(
                    title=entry.get("title", ""),
                    url=entry.get("url", ""),
                    snippet=entry.get("content", ""),
                ))
            return results
        except Exception:
            return []


class BraveEngine:
    """
    Brave Search API — independent search index, generous free tier.

    WHAT: Brave's web search API with 2000 free queries/month.
          Requires a free API key from https://brave.com/search/api/

    WHY: Good middle-ground between free DuckDuckGo and paid Tavily.
         Brave has its own index (not Bing/Google proxy), so results
         complement other engines.
    """

    name: str = "brave"

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": min(max_results, 20)},
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": self._api_key,
                    },
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()

            results: list[WebResult] = []
            for entry in data.get("web", {}).get("results", [])[:max_results]:
                results.append(WebResult(
                    title=entry.get("title", ""),
                    url=entry.get("url", ""),
                    snippet=entry.get("description", ""),
                ))
            return results
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_web_search_engine(
    engine: str = "duckduckgo",
    api_key: str | None = None,
    searxng_url: str = "http://localhost:8888",
) -> WebSearchEngine:
    """
    Factory function — creates the configured web search engine.

    WHY: Same pattern as M2's storage backend factory — the rest of the
         pipeline works with the protocol, never the concrete class.
         Switching engines is a config change, not a code change.
    """
    if engine == "tavily":
        if not api_key:
            raise ValueError("Tavily requires an API key")
        return TavilyEngine(api_key)

    if engine == "brave":
        if not api_key:
            raise ValueError("Brave Search requires an API key")
        return BraveEngine(api_key)

    if engine == "searxng":
        return SearXNEngine(searxng_url)

    # Default: DuckDuckGo (free, no key)
    return DuckDuckGoEngine()


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_web_results(results: list[WebResult]) -> str:
    """
    Format web search results as context text for the LLM prompt.

    WHAT: Converts WebResult objects to a structured text block suitable
          for inclusion in the LLM's system prompt context section.

    WHY: The LLM needs web results in the same format as document chunks
         so it can reason across both sources seamlessly.
    """
    if not results:
        return ""

    lines = ["## Web Search Results"]
    for i, r in enumerate(results):
        lines.append(f"[Web{i+1}] {r.title}")
        lines.append(f"  {r.snippet[:300]}")
        lines.append(f"  Source: {r.url}")
        lines.append("")
    return "\n".join(lines)
