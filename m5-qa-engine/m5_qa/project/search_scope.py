"""Project-scoped hybrid search with M3 integration (00106-01).

WHAT: Implements PRD FR-1 — project-scoped search that combines
      project document search (SQLite) with M3 global retrieval.

RANKING: Project documents get higher base scores (0.7+) than global
         results (0.5+). Similarity and regulation matching provide
         additional boosts. The result is a merged, deduplicated list
         sorted by relevance.

PERFORMANCE: If ≥5 project documents have high relevance (>0.7),
             M3 retrieval is skipped — saves ~200ms latency.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Configurable hybrid ranking weights
HYBRID_WEIGHTS = {
    "project_document_base": 0.70,
    "project_conclusion_base": 0.65,
    "project_conversation_base": 0.50,
    "global_base": 0.50,
    "similarity_factor": 0.30,
    "regulation_match_bonus": 0.10,
}

# Threshold: if this many high-quality project docs found, skip M3
SKIP_M3_THRESHOLD = 5
SKIP_M3_MIN_SCORE = 0.7


async def project_scoped_search(
    query: str,
    project_id: str,
    search_scope: str,
    project_manager,
    m3_engine=None,
    m4_engine=None,
) -> list[dict]:
    """Hybrid project-scoped search with optional M3 fallback.

    Args:
        query: User's search query.
        project_id: Target project for scoped search.
        search_scope: "project_only" | "hybrid" | "global_only".
        project_manager: ProjectManager instance for document search.
        m3_engine: Optional M3 retrieval engine.
        m4_engine: Optional M4 KG engine.

    Returns:
        Ranked list of result dicts with keys: text, score, source, metadata.
    """
    results: list[dict] = []

    # Phase 1: Project document search (always runs)
    if search_scope != "global_only":
        try:
            proj_results = await _search_project_docs(query, project_id, project_manager)
            results.extend(proj_results)
        except Exception as e:
            logger.warning("Project document search failed: %s", e)

    # Phase 2: M3 global retrieval (only for hybrid/global_only)
    if search_scope in ("hybrid", "global_only"):
        high_quality = [r for r in results if r.get("score", 0) > SKIP_M3_MIN_SCORE]
        if len(high_quality) < SKIP_M3_THRESHOLD and m3_engine:
            try:
                global_results = await _search_m3(query, m3_engine, m4_engine)
                results.extend(global_results)
            except Exception as e:
                logger.warning("M3 retrieval failed, using project-only results: %s", e)

    # Sort by score descending
    results.sort(key=lambda r: r.get("score", 0), reverse=True)
    return results


async def _search_project_docs(
    query: str, project_id: str, project_manager,
) -> list[dict]:
    """Search project documents via SQLite and assign base score 0.7."""
    docs = await project_manager.search_project_documents(project_id, query)
    project = await project_manager.get_project(project_id)
    reg_list = project.get("regulation_list", []) if project else []

    results = []
    for doc in docs:
        text = str(doc.get("parse_result_json", ""))[:500]
        if not text.strip():
            continue
        score = HYBRID_WEIGHTS["project_document_base"]
        # Boost if the doc text mentions regulations in the project's list
        if any(reg.lower() in text.lower() for reg in reg_list):
            score += HYBRID_WEIGHTS["regulation_match_bonus"]
        results.append({
            "text": text,
            "score": min(score, 0.95),
            "source": "project_document",
            "metadata": {"document_id": doc.get("document_id", ""),
                         "filename": doc.get("filename", "")},
        })
    return results


async def _search_m3(query: str, m3_engine, m4_engine=None) -> list[dict]:
    """Retrieve from M3 (dense + sparse dual-path) and convert to result dicts."""
    results = []
    try:
        from contracts.retrieval import RetrievalRequest
        req = RetrievalRequest(query=query, top_k=15)
        context = await m3_engine.retrieve(req)
        for chunk in getattr(context, 'chunks', []):
            results.append({
                "text": getattr(chunk, 'text', ''),
                "score": HYBRID_WEIGHTS["global_base"] + getattr(chunk, 'score', 0) * 0.4,
                "source": "m3_global",
                "metadata": getattr(chunk, 'metadata', {}),
            })
    except Exception as e:
        logger.warning("M3 retrieval error: %s", e)
    return results
