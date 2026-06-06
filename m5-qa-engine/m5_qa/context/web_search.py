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
# Error handling
# ---------------------------------------------------------------------------


class WebSearchError(Exception):
    """Base error for web search failures."""
    def __init__(self, message: str, engine: str = "", recoverable: bool = True):
        super().__init__(message)
        self.engine = engine
        self.recoverable = recoverable  # True = can retry, False = config issue


class WebSearchConfigError(WebSearchError):
    """Configuration error: missing API key, invalid key format."""
    def __init__(self, message: str, engine: str = ""):
        super().__init__(message, engine, recoverable=False)


class WebSearchQuotaError(WebSearchError):
    """Quota exhausted for the search engine."""
    def __init__(self, message: str, engine: str = ""):
        super().__init__(message, engine, recoverable=False)


class WebSearchNetworkError(WebSearchError):
    """Network timeout, DNS failure, connection refused."""
    def __init__(self, message: str, engine: str = ""):
        super().__init__(message, engine, recoverable=True)


class WebSearchAuthError(WebSearchError):
    """API key invalid or expired."""
    def __init__(self, message: str, engine: str = ""):
        super().__init__(message, engine, recoverable=False)


# ---------------------------------------------------------------------------
# Engine Protocol
# ---------------------------------------------------------------------------


class WebSearchEngine(Protocol):
    """Interface for pluggable web search backends."""

    @property
    def name(self) -> str:
        """Engine identifier: 'duckduckgo', 'searxng', 'tavily', 'brave', 'google'."""
        ...

    async def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        """Execute a web search and return normalized results."""
        ...

    async def health_check(self) -> dict:
        """Verify the engine is configured correctly and reachable.
        Returns {'ok': True} or {'ok': False, 'error': '...', 'recoverable': bool}."""
        ...


# ---------------------------------------------------------------------------
# Engine Implementations
# ---------------------------------------------------------------------------


class DuckDuckGoEngine:
    """
    DuckDuckGo Instant Answer API — free, no API key required.
    """

    name: str = "duckduckgo"

    async def health_check(self) -> dict:
        try:
            results = await self.search("test query", max_results=1)
            return {"ok": True}
        except WebSearchNetworkError as e:
            return {"ok": False, "error": str(e), "recoverable": True}
        except Exception:
            return {"ok": False, "error": "DuckDuckGo is unreachable", "recoverable": True}

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
        except httpx.TimeoutException:
            raise WebSearchNetworkError("DuckDuckGo timed out — network may be unstable")
        except httpx.ConnectError:
            raise WebSearchNetworkError("DuckDuckGo is unreachable — check network or region restrictions")
        except Exception as exc:
            raise WebSearchError(f"DuckDuckGo error: {exc}") from exc


class SearXNEngine:
    """SearXNG — self-hosted meta-search engine (Baidu/Bing/Google)."""

    name: str = "searxng"

    def __init__(self, base_url: str = "http://localhost:8888"):
        self._base_url = base_url.rstrip("/")

    async def health_check(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/healthz")
                if resp.status_code == 200:
                    return {"ok": True}
                return {"ok": False, "error": f"SearXNG returned {resp.status_code}", "recoverable": True}
        except httpx.ConnectError:
            return {"ok": False, "error": f"SearXNG not running at {self._base_url}. Start with: docker run -d -p 8888:8080 searxng/searxng", "recoverable": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "recoverable": True}

    async def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/search",
                    params={"q": query, "format": "json", "engines": "bing,baidu,google", "language": "zh-CN"},
                    headers={"User-Agent": "MarineExpertSystem/0.1"},
                )
                if resp.status_code != 200:
                    raise WebSearchError(f"SearXNG returned HTTP {resp.status_code}")
                data = resp.json()

            results: list[WebResult] = []
            for entry in data.get("results", [])[:max_results]:
                results.append(WebResult(
                    title=entry.get("title", ""),
                    url=entry.get("url", ""),
                    snippet=entry.get("content", entry.get("snippet", "")),
                ))
            return results
        except httpx.ConnectError:
            raise WebSearchNetworkError(f"SearXNG not reachable at {self._base_url}")
        except Exception as exc:
            if isinstance(exc, WebSearchError):
                raise
            raise WebSearchError(f"SearXNG error: {exc}") from exc


class TavilyEngine:
    """Tavily Search API — AI-optimized for RAG ($0.01/query, 1000 free/mo)."""

    name: str = "tavily"

    def __init__(self, api_key: str):
        if not api_key or api_key == "tvly-...":
            raise WebSearchConfigError("Tavily API key is missing or invalid. Get one at https://tavily.com", engine="tavily")
        self._api_key = api_key

    async def health_check(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={"query": "test", "max_results": 1},
                    headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                )
                if resp.status_code == 401:
                    return {"ok": False, "error": "Tavily API key is invalid or expired", "recoverable": False}
                if resp.status_code == 429:
                    return {"ok": False, "error": "Tavily quota exhausted (1000/month limit)", "recoverable": False}
                return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "recoverable": True}

    async def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={"query": query, "max_results": max_results, "search_depth": "basic"},
                    headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                )
                if resp.status_code == 401:
                    raise WebSearchAuthError("Tavily API key is invalid. Check your key at https://tavily.com", engine="tavily")
                if resp.status_code == 429:
                    raise WebSearchQuotaError("Tavily monthly quota exhausted (1000/month). Upgrade at https://tavily.com", engine="tavily")
                if resp.status_code == 403:
                    raise WebSearchQuotaError("Tavily daily quota exhausted", engine="tavily")
                if resp.status_code != 200:
                    raise WebSearchError(f"Tavily returned HTTP {resp.status_code}", engine="tavily")
                data = resp.json()

            results: list[WebResult] = []
            for entry in data.get("results", [])[:max_results]:
                results.append(WebResult(
                    title=entry.get("title", ""), url=entry.get("url", ""),
                    snippet=entry.get("content", ""),
                ))
            return results
        except (WebSearchError, WebSearchAuthError, WebSearchQuotaError):
            raise
        except httpx.TimeoutException:
            raise WebSearchNetworkError("Tavily API timed out", engine="tavily")
        except Exception as exc:
            raise WebSearchError(f"Tavily error: {exc}", engine="tavily") from exc


class BraveEngine:
    """Brave Search API — independent index, 2000 free/month."""

    name: str = "brave"

    def __init__(self, api_key: str):
        if not api_key or api_key == "BSA-...":
            raise WebSearchConfigError("Brave Search API key is missing. Get one at https://brave.com/search/api/", engine="brave")
        self._api_key = api_key

    async def health_check(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": "test", "count": 1},
                    headers={"Accept": "application/json", "X-Subscription-Token": self._api_key},
                )
                if resp.status_code == 401:
                    return {"ok": False, "error": "Brave API key is invalid", "recoverable": False}
                if resp.status_code == 429:
                    return {"ok": False, "error": "Brave monthly quota exhausted (2000/month)", "recoverable": False}
                return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "recoverable": True}

    async def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": min(max_results, 20)},
                    headers={"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": self._api_key},
                )
                if resp.status_code == 401:
                    raise WebSearchAuthError("Brave API key is invalid. Check at https://brave.com/search/api/", engine="brave")
                if resp.status_code == 429:
                    raise WebSearchQuotaError("Brave monthly quota exhausted (2000/month)", engine="brave")
                if resp.status_code != 200:
                    raise WebSearchError(f"Brave returned HTTP {resp.status_code}", engine="brave")
                data = resp.json()

            results: list[WebResult] = []
            for entry in data.get("web", {}).get("results", [])[:max_results]:
                results.append(WebResult(
                    title=entry.get("title", ""), url=entry.get("url", ""),
                    snippet=entry.get("description", ""),
                ))
            return results
        except (WebSearchError, WebSearchAuthError, WebSearchQuotaError):
            raise
        except httpx.TimeoutException:
            raise WebSearchNetworkError("Brave API timed out", engine="brave")
        except Exception as exc:
            raise WebSearchError(f"Brave error: {exc}", engine="brave") from exc


class GoogleCustomSearchEngine:
    """Google Custom Search JSON API — 100 free/day."""

    name: str = "google"

    def __init__(self, api_key: str, cx: str):
        if not api_key:
            raise WebSearchConfigError("Google API key is missing. Get one at https://console.cloud.google.com", engine="google")
        if not cx:
            raise WebSearchConfigError("Google Search Engine ID (cx) is missing. Create one at https://programmablesearchengine.google.com", engine="google")
        self._api_key = api_key
        self._cx = cx

    async def health_check(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={"key": self._api_key, "cx": self._cx, "q": "test", "num": 1},
                )
                if resp.status_code == 403:
                    return {"ok": False, "error": "Google API key is invalid or API not enabled", "recoverable": False}
                if resp.status_code == 429:
                    return {"ok": False, "error": "Google daily quota exhausted (100/day)", "recoverable": False}
                if resp.status_code == 400:
                    return {"ok": False, "error": "Google Search Engine ID (cx) is invalid", "recoverable": False}
                return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "recoverable": True}

    async def search(self, query: str, max_results: int = 5) -> list[WebResult]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={"key": self._api_key, "cx": self._cx, "q": query, "num": min(max_results, 10)},
                )
                if resp.status_code == 403:
                    raise WebSearchAuthError("Google API key is invalid or Custom Search API not enabled. Check https://console.cloud.google.com", engine="google")
                if resp.status_code == 429:
                    raise WebSearchQuotaError("Google daily quota exhausted (100/day). Resets at midnight Pacific Time.", engine="google")
                if resp.status_code == 400:
                    raise WebSearchConfigError("Google Search Engine ID (cx) is invalid", engine="google")
                if resp.status_code != 200:
                    raise WebSearchError(f"Google returned HTTP {resp.status_code}", engine="google")
                data = resp.json()

            results: list[WebResult] = []
            for entry in data.get("items", [])[:max_results]:
                results.append(WebResult(
                    title=entry.get("title", ""), url=entry.get("link", ""),
                    snippet=entry.get("snippet", ""),
                ))
            return results
        except (WebSearchError, WebSearchAuthError, WebSearchQuotaError):
            raise
        except httpx.TimeoutException:
            raise WebSearchNetworkError("Google API timed out", engine="google")
        except Exception as exc:
            raise WebSearchError(f"Google error: {exc}", engine="google") from exc


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_web_search_engine(
    engine: str = "duckduckgo",
    api_key: str | None = None,
    searxng_url: str = "http://localhost:8888",
    google_cx: str | None = None,
) -> WebSearchEngine:
    """
    Factory function — creates the configured web search engine.

    WHY: Same pattern as M2's storage backend factory — the rest of the
         pipeline works with the protocol, never the concrete class.
         Switching engines is a config change, not a code change.
    """
    if engine == "google":
        if not api_key or not google_cx:
            raise ValueError("Google Custom Search requires both api_key and cx (Search Engine ID)")
        return GoogleCustomSearchEngine(api_key, google_cx)

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
