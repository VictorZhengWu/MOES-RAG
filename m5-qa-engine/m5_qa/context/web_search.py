"""
M5 QA Engine — Web Search Retriever.

WHAT: DuckDuckGo-based web search as a supplementary retrieval source.
      When the M6 frontend's web_search toggle is enabled, this fetches
      up-to-date web results to complement M3 (vector) and M4 (graph).

WHY: Marine engineering knowledge is not static — new regulations, incident
     reports, and industry updates appear online. Web search provides the
     "fresh knowledge" that a static document corpus cannot.
     90%+ of marine engineering Q&A can be answered from the document base
     alone, but the remaining 10% (e.g. "latest IMO regulation on ballast
     water", "recent offshore incident") need live search.

Free tier: DuckDuckGo Instant Answer API (no key required). Phase 3 can
           upgrade to Brave Search API or Google Custom Search.
"""

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class WebResult:
    """A single web search result."""
    title: str
    url: str
    snippet: str      # Brief description/summary
    source: str = "web"


async def search_web(query: str, max_results: int = 5) -> list[WebResult]:
    """
    Search the web using DuckDuckGo's free API.

    WHAT: Sends a query to DuckDuckGo, parses the response, and returns
          up to max_results of title+url+snippet.

    WHY: DuckDuckGo's API is free, requires no registration, and returns
         relevant results for technical queries. The snippet field provides
         enough context to verify relevance before fetching full pages.

    Falls back gracefully: returns empty list on any error (network timeout,
    API change, rate limiting) so the main RAG pipeline is never blocked.
    """
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

            data: dict[str, Any] = resp.json()
            results: list[WebResult] = []

            # DuckDuckGo abstract (primary answer)
            abstract: str = data.get("AbstractText", "")
            abstract_url: str = data.get("AbstractURL", "")
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
        # DuckDuckGo is a secondary source — never block the main pipeline
        return []


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
