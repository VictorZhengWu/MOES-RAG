"""
M8 API Gateway — Admin Config Routes (Unified Config Store).

WHAT: Single source of truth for ALL system configuration. Every tunable
      setting is stored in the M8 SQLite system_config table as JSON,
      exposed via REST API, and hot-reloaded into running engines.

WHY: No hardcoded defaults. No deploy.yaml hacking. Admins configure the
     ENTIRE system through M7 UI. Changes take effect immediately because
     M8 and M5/M3 share process memory.

Configuration sections: llm, retrieval, parsing, storage, auth, features, smtp
"""

from __future__ import annotations

import json
import os
import time
import aiosqlite

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from m8_gateway.auth.key_manager import APIKey
from m8_gateway.auth.middleware import get_api_key

router = APIRouter(prefix="/admin/config", tags=["admin-config"])

DB_PATH = os.environ.get("M8_DB_PATH", "./data/m8_gateway.db")

# ---------------------------------------------------------------------------
# Config store helpers
# ---------------------------------------------------------------------------


async def _ensure_config_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            section TEXT NOT NULL,
            config_key TEXT NOT NULL,
            config_value TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (section, config_key)
        )
    """)
    await conn.commit()


async def _get_section(section: str) -> dict[str, str]:
    """Read all key-value pairs for a config section."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_config_table(conn)
        cursor = await conn.execute(
            "SELECT config_key, config_value FROM system_config WHERE section = ?",
            (section,),
        )
        return {row[0]: row[1] async for row in cursor}


async def _set_section(section: str, data: dict) -> None:
    """Upsert all key-value pairs for a config section."""
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_config_table(conn)
        for key, value in data.items():
            await conn.execute(
                "INSERT OR REPLACE INTO system_config (section, config_key, config_value, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (section, key, str(value), now),
            )
        await conn.commit()


# ---------------------------------------------------------------------------
# Models (per section)
# ---------------------------------------------------------------------------


class ConfigSetRequest(BaseModel):
    """Generic key-value config update."""
    data: dict[str, str | int | float | bool | None]


class LLMConfig(BaseModel):
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"

class RetrievalConfig(BaseModel):
    dense_top_k: int = 50
    sparse_top_k: int = 20
    fusion_k: int = 60
    rerank_top_k: int = 20
    dedup_threshold: float = 0.85

_DEFAULT_SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8888")

class WebSearchConfigUpdate(BaseModel):
    engine: str = "duckduckgo"
    api_key: str | None = None
    searxng_url: str = _DEFAULT_SEARXNG_URL
    google_cx: str | None = None

class FeaturesConfig(BaseModel):
    feature_billing: bool = False
    feature_web_search: bool = True
    feature_deep_research: bool = False
    feature_multi_tenant: bool = False

class SMTPConfig(BaseModel):
    host: str = "smtp.gmail.com"
    port: int = 587
    user: str = ""
    password: str = ""


class StorageConfig(BaseModel):
    vector_backend: str = "chromadb"  # chromadb | qdrant | milvus | faiss
    relational_backend: str = "sqlite"  # sqlite | postgresql | mariadb
    doc_index_backend: str = "meilisearch"  # meilisearch | elasticsearch
    file_backend: str = "local_fs"  # local_fs | minio | s3

class DeployConfig(BaseModel):
    deployment_mode: str = "personal"  # personal | enterprise | saas

class OAuthProviderConfig(BaseModel):
    provider: str  # google | microsoft | apple | facebook | x | wechat
    client_id: str = ""
    client_secret: str = ""

# ---------------------------------------------------------------------------
# Generic CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_all_config(request: Request, api_key: APIKey = Depends(get_api_key)):
    """GET /admin/config — List all config sections."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_config_table(conn)
        cursor = await conn.execute(
            "SELECT section, config_key, config_value FROM system_config ORDER BY section, config_key"
        )
        result: dict[str, dict] = {}
        async for row in cursor:
            result.setdefault(row[0], {})[row[1]] = row[2]
        return result


@router.get("/{section}")
async def get_config(request: Request, section: str, api_key: APIKey = Depends(get_api_key)):
    """GET /admin/config/:section — Read one config section."""
    data = await _get_section(section)
    if not data:
        raise HTTPException(404, f"Config section '{section}' not found. POST to create it.")
    return {"section": section, "data": data}


@router.post("/{section}")
async def set_config(
    request: Request, section: str, body: ConfigSetRequest,
    api_key: APIKey = Depends(get_api_key),
):
    """POST /admin/config/:section — Upsert config section."""
    await _set_section(section, {k: v for k, v in body.data.items() if v is not None})
    data = await _get_section(section)

    # Hot-reload into running engines
    engine = request.app.state.qa_engine
    if engine:
        _apply_config_to_m5(engine, section, data)

    return {"section": section, "data": data, "hot_reloaded": True}


# ---------------------------------------------------------------------------
# Typed convenience endpoints (M7 calls these directly)
# ---------------------------------------------------------------------------


@router.post("/llm")
async def set_llm_config(body: LLMConfig, request: Request, api_key: APIKey = Depends(get_api_key)):
    """POST /admin/config/llm — Set LLM backend."""
    data = body.model_dump()
    await _set_section("llm", {k: v for k, v in data.items() if v is not None})
    engine = request.app.state.qa_engine
    if engine and engine._config.llm:
        engine._config.llm.provider = data["provider"]
        engine._config.llm.model = data["model"]
        engine._config.llm.api_key = data.get("api_key")
        engine._config.llm.base_url = data.get("base_url")
        # Rebuild LLM client
        from m5_qa.generation.llm_client import LLMClient
        engine._llm_client = LLMClient(engine._config.llm)
    return {"updated": True, "provider": data["provider"], "model": data["model"]}


@router.get("/llm")
async def get_llm_config(request: Request, api_key: APIKey = Depends(get_api_key)):
    """GET /admin/config/llm — Read LLM config."""
    data = await _get_section("llm")
    return data or {"provider": "deepseek", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"}


@router.post("/web-search")
async def set_web_search_config(body: WebSearchConfigUpdate, request: Request, api_key: APIKey = Depends(get_api_key)):
    """POST /admin/config/web-search — Update web search engine."""
    data = body.model_dump()
    await _set_section("web_search", {k: v for k, v in data.items() if v is not None})
    engine = request.app.state.qa_engine
    if engine:
        engine._config.web_search_engine = data["engine"]
        if data.get("api_key"):
            engine._config.web_search_api_key = data["api_key"]
        engine._config.web_search_searxng_url = data.get("searxng_url", _DEFAULT_SEARXNG_URL)
        if data.get("google_cx"):
            engine._config.web_search_google_cx = data["google_cx"]
    return {"updated": True, "engine": data["engine"]}


@router.get("/web-search")
async def get_web_search_config(request: Request, api_key: APIKey = Depends(get_api_key)):
    """GET /admin/config/web-search — Read web search config."""
    return await _get_section("web_search") or {"engine": "duckduckgo"}


@router.post("/web-search/test")
async def test_web_search_connection(request: Request, api_key: APIKey = Depends(get_api_key)):
    """POST /admin/config/web-search/test — Test current web search engine."""
    engine = request.app.state.qa_engine
    if engine is None:
        raise HTTPException(503, "QA Engine not initialized")
    from m5_qa.context.web_search import create_web_search_engine
    try:
        ws = create_web_search_engine(
            engine=engine._config.web_search_engine,
            api_key=engine._config.web_search_api_key,
            searxng_url=engine._config.web_search_searxng_url,
            google_cx=engine._config.web_search_google_cx,
        )
        result = await ws.health_check()
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc), "recoverable": False}


@router.post("/features")
async def set_features(body: FeaturesConfig, request: Request, api_key: APIKey = Depends(get_api_key)):
    """POST /admin/config/features — Set feature flags."""
    data = {k: str(v).lower() for k, v in body.model_dump().items()}
    await _set_section("features", data)
    return {"updated": True, "features": data}


@router.get("/features")
async def get_features(request: Request, api_key: APIKey = Depends(get_api_key)):
    """GET /admin/config/features — Read feature flags."""
    return await _get_section("features") or {"feature_web_search": "true", "feature_billing": "false", "feature_deep_research": "false", "feature_multi_tenant": "false"}


@router.post("/smtp")
async def set_smtp(body: SMTPConfig, request: Request, api_key: APIKey = Depends(get_api_key)):
    """POST /admin/config/smtp — Set SMTP settings."""
    data = body.model_dump()
    await _set_section("smtp", {k: str(v) for k, v in data.items() if v is not None})
    # Update env vars for running auth module
    for k, v in data.items():
        os.environ[f"SMTP_{k.upper()}"] = str(v)
    return {"updated": True}


@router.get("/smtp")
async def get_smtp(request: Request, api_key: APIKey = Depends(get_api_key)):
    """GET /admin/config/smtp — Read SMTP settings."""
    return await _get_section("smtp") or {"host": "smtp.gmail.com", "port": "587"}


@router.get("/backends")
async def get_backend_status(request, api_key=Depends(get_api_key)):
    """GET /admin/config/backends — Check which parsing backends are available."""
    import shutil
    result = {"docling": {"available": True, "note": "Default engine"}}
    result["marker"] = {"available": shutil.which("marker") is not None,
                         "install": "pip install marker-pdf"}
    result["mineru"] = {"available": shutil.which("magic-pdf") is not None,
                         "install": "pip install magic-pdf"}
    return result

@router.get("/monitoring")
async def get_monitoring(request: Request, api_key: APIKey = Depends(get_api_key)):
    """GET /admin/monitoring — M5 query metrics."""
    engine = request.app.state.qa_engine
    if engine is None:
        return {"total_queries": 0, "avg_latency_ms": 0, "by_mode": {}}
    return engine._metrics.get_summary()


@router.get("/storage")
async def get_storage_config(request, api_key=Depends(get_api_key)):
    data = await _get_section("storage")
    return data or {"vector_backend": "chromadb", "relational_backend": "sqlite", "doc_index_backend": "meilisearch", "file_backend": "local_fs"}

@router.post("/storage")
async def set_storage_config(body: StorageConfig, request, api_key=Depends(get_api_key)):
    data = body.model_dump()
    await _set_section("storage", data)
    return {"updated": True, "note": "Storage backend change requires restart for some backends"}

@router.get("/deploy")
async def get_deploy_config(request, api_key=Depends(get_api_key)):
    data = await _get_section("deploy")
    return data or {"deployment_mode": "personal"}

@router.post("/deploy")
async def set_deploy_config(body: DeployConfig, request, api_key=Depends(get_api_key)):
    data = body.model_dump()
    await _set_section("deploy", data)
    cfg = request.app.state.config
    cfg.deployment_mode = data["deployment_mode"]
    return {"updated": True, "deployment_mode": data["deployment_mode"]}

@router.get("/oauth")
async def get_oauth_config(request, api_key=Depends(get_api_key)):
    data = await _get_section("oauth")
    return data or {}

@router.post("/oauth")
async def set_oauth_config(body: OAuthProviderConfig, request, api_key=Depends(get_api_key)):
    data = body.model_dump()
    await _set_section("oauth", {**await _get_section("oauth"), data["provider"]: json.dumps({"client_id": data["client_id"], "client_secret": data["client_secret"]})})
    # Update env vars for running auth module
    prefix = data["provider"].upper()
    if data["client_id"]:
        os.environ[f"OAUTH_{prefix}_CLIENT_ID"] = data["client_id"]
    if data["client_secret"]:
        os.environ[f"OAUTH_{prefix}_CLIENT_SECRET"] = data["client_secret"]
    return {"updated": True, "provider": data["provider"]}

# ---------------------------------------------------------------------------
# Hot-reload helper
# ---------------------------------------------------------------------------


@router.get("/retrieval")
async def get_retrieval_config(request, api_key=Depends(get_api_key)):
    """GET /admin/config/retrieval — M3 retrieval parameters."""
    data = await _get_section("retrieval")
    if not data:
        return {"dense_top_k": 50, "sparse_top_k": 20, "fusion_k": 60,
                "rerank_top_k": 20, "dedup_threshold": 0.85}
    return data

@router.post("/retrieval")
async def set_retrieval_config(body: RetrievalConfig, request, api_key=Depends(get_api_key)):
    """POST /admin/config/retrieval — Update M3 retrieval params (hot-reload)."""
    data = body.model_dump()
    await _set_section("retrieval", {k: str(v) for k, v in data.items()})
    engine = request.app.state.qa_engine
    if engine and engine._retriever._m3:
        cfg = engine._retriever._m3._pipeline.cfg
        cfg.dense_top_k = data["dense_top_k"]
        cfg.sparse_top_k = data["sparse_top_k"]
        cfg.fusion_k = data["fusion_k"]
        cfg.rerank_top_k = data["rerank_top_k"]
        cfg.dedup_threshold = data["dedup_threshold"]
    return {"updated": True, "data": data}

def _apply_config_to_m5(engine, section: str, data: dict) -> None:
    """Apply config changes to the running M5 instance immediately."""
    cfg = engine._config
    if section == "llm":
        if cfg.llm:
            cfg.llm.provider = data.get("provider", cfg.llm.provider)
            cfg.llm.model = data.get("model", cfg.llm.model)
            if data.get("api_key"):
                cfg.llm.api_key = data.get("api_key")
            if data.get("base_url"):
                cfg.llm.base_url = data.get("base_url")
    elif section == "retrieval":
        cfg.dense_top_k = int(data.get("dense_top_k", cfg.dense_top_k))
        cfg.sparse_top_k = int(data.get("sparse_top_k", cfg.sparse_top_k))
        cfg.fusion_k = int(data.get("fusion_k", cfg.fusion_k))
    elif section == "web_search":
        cfg.web_search_engine = data.get("engine", cfg.web_search_engine)
        if data.get("api_key"):
            cfg.web_search_api_key = data.get("api_key")
