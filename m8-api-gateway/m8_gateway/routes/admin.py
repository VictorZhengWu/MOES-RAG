"""
M8 API Gateway — Admin Config Routes.

WHAT: Runtime configuration endpoints for M5 engine settings.
      Allows the M7 admin portal to update engine configuration
      without restarting M5 — changes take effect immediately
      because M8 and M5 share the same process memory.

WHY: M7 admin interface needs to persist config changes and have
     them applied instantly. The in-memory QAEngine singleton means
     config updates on the Python object take effect immediately for
     the next request without any restart or reload.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from m8_gateway.auth.key_manager import APIKey
from m8_gateway.auth.middleware import get_api_key

router = APIRouter(prefix="/admin/config", tags=["admin-config"])


@router.get("/monitoring")
async def get_monitoring(
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """
    GET /admin/monitoring — Expose M5 query metrics for M7 dashboard.

    WHAT: Returns aggregated stats from M5's MetricsCollector:
          total_queries, avg_latency_ms, and breakdown by pipeline mode.

    WHY: M7 admin dashboard has a monitoring page that previously showed
         mock data. This endpoint provides real operational metrics.
    """
    engine = request.app.state.qa_engine
    if engine is None:
        return {"total_queries": 0, "avg_latency_ms": 0, "by_mode": {}, "note": "QA Engine not initialized"}

    return engine._metrics.get_summary()


class WebSearchConfigUpdate(BaseModel):
    """Request body for updating web search engine configuration."""
    engine: str = "duckduckgo"       # duckduckgo | searxng | tavily | brave | google
    api_key: str | None = None       # Required for tavily, brave, google
    searxng_url: str = "http://localhost:8888"
    google_cx: str | None = None     # Google Custom Search Engine ID


@router.post("/web-search")
async def update_web_search_config(
    body: WebSearchConfigUpdate,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """
    POST /admin/config/web-search — Update web search engine config.

    WHAT: Accepts the new web search engine configuration from M7's
          admin UI and applies it to the running M5 QAEngine instance
          in-memory. No restart needed — changes take effect on the
          next chat request.

    WHY: M7 admin portal's Web Search Engine card has a Save button
         that calls this endpoint. Previously it only saved to
         localStorage; now it persists to the backend.
    """
    engine = request.app.state.qa_engine
    if engine is None:
        raise HTTPException(503, "QA Engine not initialized")

    engine._config.web_search_engine = body.engine
    if body.api_key:
        engine._config.web_search_api_key = body.api_key
    engine._config.web_search_searxng_url = body.searxng_url
    if body.google_cx:
        engine._config._google_cx = body.google_cx

    return {
        "updated": True,
        "engine": body.engine,
    }


@router.get("/web-search")
async def get_web_search_config(
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """GET /admin/config/web-search — Read current web search config."""
    engine = request.app.state.qa_engine
    if engine is None:
        raise HTTPException(503, "QA Engine not initialized")

    return {
        "engine": engine._config.web_search_engine,
        "has_api_key": bool(engine._config.web_search_api_key),
        "searxng_url": engine._config.web_search_searxng_url,
    }


@router.post("/web-search/test")
async def test_web_search_connection(
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """
    POST /admin/config/web-search/test — Test the current web search engine.

    WHAT: Creates the configured engine and calls health_check() to verify
          the API key is valid, the engine is reachable, and quotas are OK.

    WHY: M7 admin UI's "Test Connection" button calls this to give
         immediate feedback after changing engine settings.
         Returns structured result with ok, error message, and recoverable flag.
    """
    engine = request.app.state.qa_engine
    if engine is None:
        raise HTTPException(503, "QA Engine not initialized")

    from m5_qa.context.web_search import create_web_search_engine

    try:
        ws_engine = create_web_search_engine(
            engine=engine._config.web_search_engine,
            api_key=engine._config.web_search_api_key,
            searxng_url=engine._config.web_search_searxng_url,
            google_cx=engine._config.web_search_google_cx,
        )
        result = await ws_engine.health_check()
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc), "recoverable": False}
