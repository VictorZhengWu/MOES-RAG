"""Agent_Regulations — maritime document retrieval via M3 + M4.

WHAT: For each sub-question in the research plan, queries M3 (dense +
      sparse dual-path retrieval), M4 (1-hop graph traversal), and
      appends ISO standard descriptions when standard numbers are found.

WHY: M3 provides full-text and vector search across all indexed documents.
     M4 provides structured knowledge graph traversal to discover related
     entities and cross-references. ISO standards are frequently referenced
     in marine engineering but don't have full documents in the vector store
     — a lightweight dictionary lookup fills the gap.

RETURN FORMAT:
    List of dicts: [{chunk_id, text, score, source (dense|sparse|graph|iso), metadata}]
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Top 10 ISO standards for marine engineering (Phase 4-A lightweight lookup)
ISO_STANDARDS: dict[str, dict[str, str]] = {
    "ISO 5817": {
        "title": "Welding — Fusion-welded joints in steel — Quality levels for imperfections",
        "scope": "Specifies three quality levels (B, C, D) for imperfections in fusion-welded joints in steel. Level B corresponds to the highest quality.",
    },
    "ISO 9712": {
        "title": "Non-destructive testing — Qualification and certification of NDT personnel",
        "scope": "Establishes a system for the qualification and certification of personnel performing industrial NDT.",
    },
    "ISO 17635": {
        "title": "Non-destructive testing of welds — General rules for metallic materials",
        "scope": "Provides general rules and standards for non-destructive testing of welds in metallic materials.",
    },
    "ISO 17640": {
        "title": "Non-destructive testing of welds — Ultrasonic testing — Techniques, testing levels, and assessment",
        "scope": "Specifies techniques for the manual ultrasonic testing of fusion-welded joints in metallic materials.",
    },
    "ISO 15614": {
        "title": "Specification and qualification of welding procedures — Welding procedure test",
        "scope": "Specifies how a preliminary welding procedure specification is qualified by welding procedure tests.",
    },
    "ISO 12944": {
        "title": "Paints and varnishes — Corrosion protection of steel structures by protective paint systems",
        "scope": "Covers corrosion protection of steel structures using protective paint systems, relevant for offshore and ship structures.",
    },
    "ISO 19901": {
        "title": "Petroleum and natural gas industries — Specific requirements for offshore structures",
        "scope": "Contains specific requirements for various types of offshore structures in the petroleum and natural gas industries.",
    },
    "ISO 19902": {
        "title": "Petroleum and natural gas industries — Fixed steel offshore structures",
        "scope": "Specifies requirements and provides recommendations for the structural design of fixed steel offshore structures.",
    },
    "ISO 19903": {
        "title": "Petroleum and natural gas industries — Concrete offshore structures",
        "scope": "Specifies requirements and provides recommendations for the structural design of concrete offshore structures.",
    },
    "ISO 2400": {
        "title": "Non-destructive testing — Ultrasonic testing — Specification for calibration block No. 1",
        "scope": "Specifies the requirements for the dimensions, material, and manufacture of a steel calibration block for ultrasonic testing.",
    },
}


async def agent_regulations(
    sub_questions: list[dict],
    m3_engine=None,
    m4_engine=None,
) -> list[dict]:
    """Execute regulation retrieval for each sub-question.

    Args:
        sub_questions: List of {"id", "search_query", ...} from planner.
        m3_engine: M3 retrieval engine (may be None for testing).
        m4_engine: M4 KG engine (may be None).

    Returns:
        Merged list of search result dicts from all sources.
    """
    all_results: list[dict] = []
    seen_ids: set[str] = set()

    for sq in sub_questions:
        if "regulations" not in sq.get("search_strategy", []):
            continue
        query = sq["search_query"]

        # --- M3 dense retrieval ---
        try:
            if m3_engine:
                dense = await _retrieve_m3(m3_engine, query, source="dense", top_k=10)
                for r in dense:
                    if r["chunk_id"] not in seen_ids:
                        seen_ids.add(r["chunk_id"])
                        all_results.append(r)
        except Exception as e:
            logger.warning("M3 dense retrieval failed for '%s': %s", query[:40], e)

        # --- M3 sparse retrieval ---
        try:
            if m3_engine:
                sparse = await _retrieve_m3(m3_engine, query, source="sparse", top_k=5)
                for r in sparse:
                    if r["chunk_id"] not in seen_ids:
                        seen_ids.add(r["chunk_id"])
                        all_results.append(r)
        except Exception as e:
            logger.warning("M3 sparse retrieval failed for '%s': %s", query[:40], e)

        # --- M4 graph traversal (1-hop) ---
        try:
            if m4_engine:
                graph = await _retrieve_m4(m4_engine, query)
                for r in graph:
                    if r["chunk_id"] not in seen_ids:
                        seen_ids.add(r["chunk_id"])
                        all_results.append(r)
        except Exception as e:
            logger.warning("M4 graph traversal failed for '%s': %s", query[:40], e)

        # --- ISO standard lookup ---
        iso_found = _lookup_iso_standards(query)
        for r in iso_found:
            iso_id = r["chunk_id"]
            if iso_id not in seen_ids:
                seen_ids.add(iso_id)
                all_results.append(r)

    return all_results


async def _retrieve_m3(engine, query: str, source: str, top_k: int) -> list[dict]:
    """Call M3 retrieval and normalize to dict format.

    WHY normalize: M3 returns ScoredChunk objects with different field
         access patterns (some via .attribute, some via dict keys).
         Normalizing to plain dicts ensures consistent downstream handling.
    """
    from contracts.retrieval import RetrievalRequest

    req = RetrievalRequest(
        query=query,
        top_k=top_k,
    )
    context = await engine.retrieve(req)

    results = []
    for chunk, score in context.chunks if hasattr(context, 'chunks') else []:
        results.append({
            "chunk_id": getattr(chunk, "chunk_id", str(hash(chunk.text))),
            "text": chunk.text if hasattr(chunk, "text") else str(chunk),
            "score": score,
            "source": source,
            "metadata": getattr(chunk, "metadata", {}),
        })
    return results


async def _retrieve_m4(engine, query: str) -> list[dict]:
    """Call M4 graph search and normalize results.

    WHY include graph results: M4 stores entities and relations extracted
         from documents. A 1-hop BFS from entities matching the query
         discovers related clauses, materials, and equipment that M3
         keyword search would miss.
    """
    try:
        subgraph = await engine.graph_search(query, depth=1)
    except Exception:
        return []

    results = []
    entities = getattr(subgraph, "entities", []) or []
    for entity in entities:
        name = getattr(entity, "name", str(entity))
        entity_type = getattr(entity, "entity_type", "unknown")
        text = f"[KG] {entity_type}: {name}"
        results.append({
            "chunk_id": f"kg-{hash(text) & 0xFFFFFFFF:08x}",
            "text": text,
            "score": 0.6,  # KG results have lower confidence than direct retrieval
            "source": "graph",
            "metadata": {"entity_type": entity_type},
        })
    return results


def _lookup_iso_standards(query: str) -> list[dict]:
    """Check if the query references any known ISO standards.

    WHY: ISO standards are critical to marine engineering but the full
         text is not in our vector store. A lightweight keyword match
         against known standard numbers provides the title and scope as
         a hint for the LLM analyzer.
    """
    results = []
    query_upper = query.upper()
    for code, info in ISO_STANDARDS.items():
        if code.upper() in query_upper:
            results.append({
                "chunk_id": f"iso-{code}",
                "text": f"[ISO Standard] {code}: {info['title']}. {info['scope']}",
                "score": 0.8,
                "source": "iso",
                "metadata": {"iso_code": code},
            })
            break  # Only add the first matching ISO standard
    return results
