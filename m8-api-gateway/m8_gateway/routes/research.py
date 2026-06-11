"""M8 Research routes — Deep Research SSE endpoint.

POST /api/v1/agent/research
    Start a Deep Research study. Returns SSE event stream with progress
    updates and the final report.

POST /api/v1/agent/research/{report_id}/question
    Submit a follow-up question about a specific conclusion in the report.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from m8_gateway.auth.key_manager import APIKey
from m8_gateway.auth.middleware import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["deep-research"])


class ResearchRequest(BaseModel):
    """Request body for starting Deep Research."""
    query: str
    sub_questions: Optional[list[dict]] = None
    stream: bool = True
    include_cases: bool = False  # P0-3: Include archived case studies


class ResearchQuestion(BaseModel):
    """Follow-up question about a report conclusion."""
    conclusion_id: int
    question: str


@router.post("/research")
async def start_research(
    request: Request,
    body: ResearchRequest,
    api_key: APIKey = Depends(get_api_key),
):
    """Start a Deep Research study with SSE progress streaming.

    WHAT: Executes the 4-phase pipeline (planning → retrieval →
          analysis → reporting) and streams progress as SSE events
          for the M6 frontend to display in real-time.

    Returns:
        text/event-stream with progress, report_chunk, and done events.
    """
    # Get QA engine from app state
    qa_engine = request.app.state.qa_engine
    if qa_engine is None:
        raise HTTPException(503, "QA Engine not initialized")

    # Get research dependencies from the engine
    m3_engine = getattr(qa_engine._retriever, '_m3', None) if hasattr(qa_engine, '_retriever') else None
    m4_engine = getattr(qa_engine._retriever, '_m4', None) if hasattr(qa_engine, '_retriever') else None
    llm_client = getattr(qa_engine, '_llm_client', None)

    # Web search config from engine config
    web_config = {
        "engine": getattr(qa_engine._config, 'web_search_engine', 'duckduckgo'),
        "api_key": getattr(qa_engine._config, 'web_search_api_key', None),
        "google_cx": getattr(qa_engine._config, 'web_search_google_cx', None),
    }

    from m5_qa.research.progress import execute_research

    async def event_stream():
        """Generate SSE event stream from research execution."""
        try:
            async for event in execute_research(
                query=body.query,
                sub_questions=body.sub_questions,
                m3_engine=m3_engine,
                m4_engine=m4_engine,
                llm_client=llm_client,
                web_search_config=web_config,
                include_cases=body.include_cases,
            ):
                yield event
        except Exception as e:
            logger.exception("Research execution failed")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/research/{report_id}/question")
async def question_research(
    request: Request,
    report_id: str,
    body: ResearchQuestion,
    api_key: APIKey = Depends(get_api_key),
):
    """Submit a follow-up question about a specific conclusion.

    WHAT: Allows the user to "challenge" a specific finding in the
          report. The system re-analyzes the relevant evidence and
          updates the conclusion.

    Args:
        report_id: The research report ID to question.
        body: conclusion_id + question text.

    Returns:
        Updated conclusion text with additional analysis.
    """
    qa_engine = request.app.state.qa_engine
    if qa_engine is None:
        raise HTTPException(503, "QA Engine not initialized")

    llm_client = getattr(qa_engine, '_llm_client', None)
    if llm_client is None:
        raise HTTPException(503, "LLM backend not configured")

    # P0-1 fix: Retrieve stored research context for meaningful re-analysis
    from m5_qa.research.progress import get_research_context
    ctx = get_research_context(report_id)

    if ctx:
        reg_text = "\n".join(
            f"[{r.get('source', '?')}] {str(r.get('text', ''))[:300]}"
            for r in ctx.get("regulation_results", [])[:5]
        ) or "No regulation results available."
        web_text = "\n".join(
            f"[web] {r.get('title', '')}: {str(r.get('snippet', ''))[:200]}"
            for r in ctx.get("web_results", [])[:3]
        ) or "No web results."
        conflicts_text = str(ctx.get("conflicts", "None"))
        prompt = (
            f"A user has questioned a conclusion from a Deep Research report.\n\n"
            f"=== ORIGINAL REPORT ===\n{ctx['report'][:3000]}\n\n"
            f"=== REGULATION FINDINGS ===\n{reg_text}\n\n"
            f"=== WEB FINDINGS ===\n{web_text}\n\n"
            f"=== DETECTED CONFLICTS ===\n{conflicts_text}\n\n"
            f"The user questions conclusion #{body.conclusion_id}:\n"
            f"\"{body.question}\"\n\n"
            f"Re-examine ALL the evidence above. If the user's concern is valid, "
            f"acknowledge it and provide a corrected analysis with citations. "
            f"If the original conclusion stands, explain why with specific evidence."
        )
    else:
        prompt = (
            f"A user has questioned conclusion #{body.conclusion_id} "
            f"from a Deep Research report (ID: {report_id}).\n\n"
            f"Their question: {body.question}\n\n"
            f"Re-examine the evidence and provide an updated analysis."
        )

    try:
        response = await llm_client.complete(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )
        content = response["choices"][0]["message"]["content"]
        return {
            "report_id": report_id,
            "conclusion_id": body.conclusion_id,
            "updated_analysis": content,
            "has_context": ctx is not None,
            # P0-4: Return original evidence so frontend can display it
            "evidence": {
                "regulation_results": [
                    {"text": str(r.get("text", ""))[:200], "source": r.get("source", "?")}
                    for r in ctx.get("regulation_results", [])[:5]
                ] if ctx else [],
                "web_results": [
                    {"title": r.get("title", ""), "snippet": str(r.get("snippet", ""))[:200]}
                    for r in ctx.get("web_results", [])[:3]
                ] if ctx else [],
                "conflicts": ctx.get("conflicts", []) if ctx else [],
            },
        }
    except Exception as e:
        logger.exception("Research question failed")
        raise HTTPException(500, f"Failed to analyze question: {e}")


@router.post("/research/{report_id}/export")
async def export_research_pdf(
    request: Request,
    report_id: str,
    api_key: APIKey = Depends(get_api_key),
):
    """POST /api/v1/agent/research/{id}/export — Export report as PDF.

    Accepts report markdown in request body (no URL length limit).
    Falls back to stored research context if body is empty.
    """
    from m5_qa.research.export_pdf import export_report_pdf

    try:
        body = await request.json()
    except Exception:
        body = {}

    report_md = body.get("report", "")

    # Fallback: try stored research context
    if not report_md:
        from m5_qa.research.progress import get_research_context
        ctx = get_research_context(report_id)
        if ctx:
            report_md = ctx.get("report", "")

    if not report_md:
        raise HTTPException(400, "Report content required. Send as JSON body: {\"report\": \"...\"}")

    pdf_bytes = await export_report_pdf(report_md)
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    return StreamingResponse(BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=research_{report_id}.pdf"})
