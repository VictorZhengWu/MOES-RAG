"""Research progress orchestrator — SSE event stream for Deep Research.

WHAT: Executes the full 4-phase Deep Research pipeline and emits SSE
      progress events for real-time frontend updates. Ties together
      planner, agents, analyzer, and report generator.

WHY: The frontend needs to show real-time progress: which phase is
     active, what each agent found, and stream the final report as
     it's being generated. SSE is the standard for this pattern.

EVENT TYPES:
    progress: phase change + percentage + agent status
    error: non-fatal error (one agent failed, others continue)
    report_chunk: partial report content (streaming)
    done: research complete + final report
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator, Optional

from m5_qa.research.planner import decompose_query
from m5_qa.research.agents.regulations import agent_regulations
from m5_qa.research.agents.web import agent_web
from m5_qa.research.analyzer import analyze, AnalysisResult
from m5_qa.research.report_generator import generate_report

logger = logging.getLogger(__name__)

# In-memory store for research context — enables question/re-analysis.
# Keyed by report_id, stores the full report + retrieval results.
# TTL: 1 hour (auto-cleaned on next research execution for that report_id).
_research_store: dict[str, dict] = {}


def get_research_context(report_id: str) -> dict | None:
    """Retrieve stored research context for question/re-analysis."""
    return _research_store.get(report_id)


async def execute_research(
    query: str,
    sub_questions: Optional[list[dict]] = None,
    m3_engine=None,
    m4_engine=None,
    llm_client=None,
    web_search_config: Optional[dict] = None,
    include_cases: bool = False,
) -> AsyncIterator[str]:
    """Execute the full Deep Research pipeline with SSE progress events.

    Args:
        query: Original user question.
        sub_questions: Optional pre-defined plan (skips planner if given).
        m3_engine: M3 retrieval engine.
        m4_engine: M4 KG engine.
        llm_client: M5 LLM client for planner/analyzer/reporter.
        web_search_config: Dict with engine/api_key for Agent_Web.

    Yields:
        SSE event strings: "event: progress\ndata: {...}\n\n"
    """
    report_id = f"rpt-{uuid.uuid4().hex[:12]}"
    t_start = time.time()

    # ------------------------------------------------------------------
    # Phase 1: Planning
    # ------------------------------------------------------------------
    yield _sse("progress", {
        "phase": "planning",
        "progress": 0.0,
        "message": "Analyzing question and creating research plan...",
        "report_id": report_id,
    })

    if sub_questions is None:
        try:
            # Set LLM client on the planner singleton
            decompose_query._llm_client = llm_client
            plan = await decompose_query(query, m4_engine=m4_engine)
        except Exception as e:
            logger.error("Planning failed: %s", e)
            yield _sse("error", {"phase": "planning", "error": str(e)})
            return
    else:
        # User pre-selected sub-questions (from M6 UI)
        enabled = [sq for sq in sub_questions if sq.get("enabled", True)]
        plan = {
            "sub_questions": enabled,
            "estimated_runtime_seconds": len(enabled) * 15 + 25,
        }

    # P0-3: If case studies requested, add a sub-question for archived projects
    if include_cases:
        next_id = len(plan["sub_questions"]) + 1
        plan["sub_questions"].append({
            "id": next_id,
            "question": "Relevant case studies from archived projects",
            "search_strategy": ["web", "cases"],
            "search_query": f"{query} marine accident investigation report case study",
        })

    yield _sse("progress", {
        "phase": "planning",
        "progress": 0.15,
        "message": f"Research plan ready: {len(plan['sub_questions'])} sub-questions"
            + (" (including case studies)" if include_cases else ""),
        "plan": plan,
    })

    # ------------------------------------------------------------------
    # Phase 2: Parallel retrieval
    # ------------------------------------------------------------------
    yield _sse("progress", {
        "phase": "retrieving",
        "progress": 0.20,
        "message": "Searching regulations and web...",
    })

    reg_task = agent_regulations(
        plan["sub_questions"], m3_engine=m3_engine, m4_engine=m4_engine,
    )
    web_task = agent_web(
        plan["sub_questions"], web_search_config=web_search_config,
    )

    reg_results, web_results = await asyncio.gather(reg_task, web_task)

    yield _sse("progress", {
        "phase": "retrieving",
        "progress": 0.50,
        "message": f"Retrieved {len(reg_results)} regulation + {len(web_results)} web results",
        "regulation_count": len(reg_results),
        "web_count": len(web_results),
    })

    # ------------------------------------------------------------------
    # Phase 3: Analysis
    # ------------------------------------------------------------------
    yield _sse("progress", {
        "phase": "analyzing",
        "progress": 0.55,
        "message": "Cross-referencing regulations and detecting conflicts...",
    })

    try:
        analysis: AnalysisResult = await analyze(
            query, reg_results, web_results,
            llm_client=llm_client, m4_engine=m4_engine,
        )
    except Exception as e:
        logger.warning("Analysis failed, continuing with empty analysis: %s", e)
        analysis = AnalysisResult()

    yield _sse("progress", {
        "phase": "analyzing",
        "progress": 0.75,
        "message": f"Analysis complete: {len(analysis.conflicts)} conflicts found",
        "conflicts_count": len(analysis.conflicts),
    })

    # ------------------------------------------------------------------
    # Phase 4: Report generation
    # ------------------------------------------------------------------
    yield _sse("progress", {
        "phase": "reporting",
        "progress": 0.80,
        "message": "Generating research report...",
    })

    try:
        report = await generate_report(
            query, reg_results, web_results, analysis, llm_client=llm_client,
        )
    except Exception as e:
        logger.error("Report generation failed: %s", e)
        yield _sse("error", {"phase": "reporting", "error": str(e)})
        return

    # Stream report as report_chunk events (one per section)
    sections = report.split("\n## ")
    for section in sections:
        yield _sse("report_chunk", {
            "delta": (section if sections.index(section) == 0 else "## " + section),
        })

    # ------------------------------------------------------------------
    # Store context for question/re-analysis (P0-1 fix)
    # ------------------------------------------------------------------
    _research_store[report_id] = {
        "query": query,
        "report": report,
        "regulation_results": reg_results[:10],
        "web_results": web_results[:5],
        "conflicts": getattr(analysis, 'conflicts', []),
        "stored_at": time.time(),
    }

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    elapsed = round(time.time() - t_start, 1)
    yield _sse("done", {
        "report_id": report_id,
        "elapsed_seconds": elapsed,
        "regulation_count": len(reg_results),
        "web_count": len(web_results),
        "conflicts_count": len(analysis.conflicts),
        "full_report": report,
    })


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format a dict as an SSE event string.

    WHAT: SSE protocol requires "event: <name>\ndata: <json>\n\n".
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
