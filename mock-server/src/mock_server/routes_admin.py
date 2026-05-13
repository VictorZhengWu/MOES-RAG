"""
Mock admin endpoints for M7 development.

WHY: M7's admin portal needs working endpoints for document management,
knowledge graph browsing, LLM configuration, user management, and
system monitoring. All return fake data matching contracts/api_schemas.py.

Endpoints are organized by admin function area with clear section comments.
"""

import asyncio
import random

from fastapi import APIRouter

from .data import (
    generate_id,
    mock_documents,
    mock_kg_entities,
    mock_kg_relations,
    mock_llm_backends,
    mock_parse_task,
    mock_system_stats,
    mock_users,
    now_iso,
)

router = APIRouter(prefix="/api/v1/admin")


# ── Document Upload & Parsing ──────────────────────────────────────

@router.post("/documents/upload")
async def upload_document():
    """
    Mock document upload. Always succeeds.

    Returns a task ID that the frontend can poll via /status.
    In real M1, this initiates an async parsing pipeline.
    """
    await asyncio.sleep(random.uniform(0.1, 0.3))
    task = mock_parse_task()
    return {
        "task_id": task["task_id"],
        "doc_id": task["doc_id"],
        "status": "queued",
        "created_at": now_iso(),
    }


@router.get("/documents/{task_id}/status")
async def get_parse_status(task_id: str):
    """
    Mock parse task status. Always returns 'completed'.

    WHY: M7's upload UI polls this endpoint to show progress.
    Returning 'completed' lets the developer verify the success
    state rendering without waiting for real parsing.
    """
    return mock_parse_task()


@router.get("/documents")
async def list_documents():
    """Return a list of fake ingested documents."""
    docs = mock_documents()
    return {"documents": docs, "total": len(docs)}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Pretend to delete a document from the knowledge base."""
    return {"doc_id": doc_id, "deleted": True}


# ── Knowledge Graph Browser ────────────────────────────────────────

@router.get("/knowledge-graph/entities")
async def list_kg_entities():
    """Return fake knowledge graph entities for the admin KG browser."""
    entities = mock_kg_entities()
    return {"entities": entities, "total": len(entities)}


@router.get("/knowledge-graph/relations")
async def list_kg_relations():
    """Return fake knowledge graph relations for the admin KG browser."""
    relations = mock_kg_relations()
    return {"relations": relations, "total": len(relations)}


# ── LLM Backend Configuration ──────────────────────────────────────

@router.get("/llm/backends")
async def list_llm_backends():
    """Return configured LLM backends."""
    backends = mock_llm_backends()
    return {"backends": backends, "total": len(backends)}


@router.post("/llm/backends")
async def create_llm_backend(body: dict):
    """Pretend to create a new LLM backend configuration."""
    return {
        "backend_id": generate_id("llm"),
        "backend_type": body.get("backend_type", "ollama"),
        "model_name": body.get("model_name", "new-model"),
        "base_url": body.get("base_url"),
        "max_tokens": body.get("max_tokens", 4096),
        "temperature": body.get("temperature", 0.7),
        "is_default": False,
        "assigned_agents": body.get("assigned_agents", []),
    }


@router.put("/llm/backends/{backend_id}")
async def update_llm_backend(backend_id: str, body: dict):
    """Pretend to update an LLM backend configuration."""
    return {"backend_id": backend_id, "updated": True}


@router.delete("/llm/backends/{backend_id}")
async def delete_llm_backend(backend_id: str):
    """Pretend to delete an LLM backend configuration."""
    return {"backend_id": backend_id, "deleted": True}


# ── User Management ────────────────────────────────────────────────

@router.get("/users")
async def list_users():
    """Return fake user list for admin user management."""
    users = mock_users()
    return {"users": users, "total": len(users)}


@router.post("/users")
async def create_user(body: dict):
    """Pretend to create a new user."""
    return {
        "user_id": generate_id("user"),
        "username": body.get("username", "new_user"),
        "email": body.get("email", "new@shipyard.com"),
        "role": body.get("role", "viewer"),
        "is_active": True,
        "api_key_count": 0,
        "total_queries": 0,
        "created_at": now_iso(),
    }


# ── System Monitoring ──────────────────────────────────────────────

@router.get("/stats")
async def get_system_stats():
    """Return fake system statistics for the admin dashboard."""
    return mock_system_stats()


@router.get("/health")
async def health_check():
    """
    Fake health check — all modules report OK.

    WHY: Health endpoint format uses per-module status keys so M7's
    monitoring dashboard can render a status grid showing each
    module as a colored indicator (green/amber/red).
    """
    return {
        "status": "ok",
        "version": "0.1.0-mock",
        "modules": {
            "m1_doc_parsing": "ok",
            "m2_storage": "ok",
            "m3_retrieval": "ok",
            "m4_knowledge_graph": "ok",
            "m5_qa_engine": "ok",
            "m8_api_gateway": "ok",
        },
        "uptime_seconds": 12345.6,
    }
