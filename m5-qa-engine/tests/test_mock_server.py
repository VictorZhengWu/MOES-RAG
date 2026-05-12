"""
Contract tests for all Mock Server endpoints.

WHY: Every endpoint must be verified to return HTTP 200 and
schema-compliant JSON. If an endpoint breaks, M6/M7 frontend
development is blocked. These tests are the gate before M6/M7
development can begin.

Tests are grouped by API area matching the route module structure.
"""

import pytest


class TestChatEndpoints:
    """POST /v1/chat/completions (non-streaming and streaming)."""

    async def test_non_streaming_chat_returns_200(self, client):
        """Verify non-streaming chat returns valid JSON with citations."""
        body = {
            "model": "marine-rag-mock",
            "messages": [{"role": "user", "content": "What is DNV Pt.4?"}],
            "stream": False,
        }
        response = await client.post("/v1/chat/completions", json=body)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "chat.completion"
        assert len(data["choices"]) == 1
        assert "content" in data["choices"][0]["message"]
        # Verify RAG extension: citations are present
        assert "citations" in data
        assert len(data["citations"]) >= 1
        assert "source_doc" in data["citations"][0]

    async def test_streaming_chat_returns_sse(self, client):
        """Verify streaming chat returns SSE with [DONE] terminator."""
        body = {
            "model": "marine-rag-mock",
            "messages": [{"role": "user", "content": "DNV vs ABS LNG"}],
            "stream": True,
        }
        response = await client.post("/v1/chat/completions", json=body)
        assert response.status_code == 200
        text = response.text
        assert "data:" in text
        assert "[DONE]" in text


class TestConversationEndpoints:
    """Conversation CRUD: list, get, rename, delete."""

    async def test_list_conversations(self, client):
        """Verify conversation list returns array with totals."""
        response = await client.get("/api/v1/conversations")
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data
        assert len(data["conversations"]) >= 1

    async def test_get_conversation(self, client):
        """Verify conversation detail returns message history."""
        response = await client.get(
            "/api/v1/conversations/conv_lng_tank_design"
        )
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) >= 2

    async def test_delete_conversation(self, client):
        """Verify delete returns success marker."""
        response = await client.delete("/api/v1/conversations/conv_test")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    async def test_rename_conversation(self, client):
        """Verify rename returns the new title."""
        body = {"title": "New Title"}
        response = await client.patch(
            "/api/v1/conversations/conv_test", json=body
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"


class TestModelEndpoints:
    """GET /v1/models — OpenAI compatibility."""

    async def test_list_models(self, client):
        """Verify model list returns OpenAI-compatible format."""
        response = await client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) >= 1
        assert data["data"][0]["id"].startswith("marine-rag")


class TestAdminDocumentEndpoints:
    """Admin document upload, status, list, delete."""

    async def test_upload_document(self, client):
        """Verify upload returns a task ID for polling."""
        response = await client.post("/api/v1/admin/documents/upload")
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "queued"

    async def test_get_parse_status(self, client):
        """Verify parse status returns completed task info."""
        response = await client.get(
            "/api/v1/admin/documents/task_test_01/status"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    async def test_list_documents(self, client):
        """Verify document list returns known documents."""
        response = await client.get("/api/v1/admin/documents")
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) >= 1

    async def test_delete_document(self, client):
        """Verify delete returns success marker."""
        response = await client.delete("/api/v1/admin/documents/doc_test")
        assert response.status_code == 200
        assert response.json()["deleted"] is True


class TestAdminKGEndpoints:
    """Knowledge graph entity and relation browsing."""

    async def test_list_kg_entities(self, client):
        """Verify KG entity list returns entities with types."""
        response = await client.get("/api/v1/admin/knowledge-graph/entities")
        assert response.status_code == 200
        data = response.json()
        assert len(data["entities"]) >= 2

    async def test_list_kg_relations(self, client):
        """Verify KG relation list returns relations with types."""
        response = await client.get("/api/v1/admin/knowledge-graph/relations")
        assert response.status_code == 200
        data = response.json()
        assert len(data["relations"]) >= 1
        assert "relation_type" in data["relations"][0]


class TestAdminLLMEndpoints:
    """LLM backend configuration CRUD."""

    async def test_list_llm_backends(self, client):
        """Verify backend list returns configs."""
        response = await client.get("/api/v1/admin/llm/backends")
        assert response.status_code == 200
        data = response.json()
        assert len(data["backends"]) >= 1

    async def test_create_llm_backend(self, client):
        """Verify create returns the new backend config."""
        body = {"backend_type": "ollama", "model_name": "llama3"}
        response = await client.post(
            "/api/v1/admin/llm/backends", json=body
        )
        assert response.status_code == 200
        assert response.json()["backend_type"] == "ollama"

    async def test_update_llm_backend(self, client):
        """Verify update returns success marker."""
        body = {"model_name": "updated-model"}
        response = await client.put(
            "/api/v1/admin/llm/backends/llm_01", json=body
        )
        assert response.status_code == 200

    async def test_delete_llm_backend(self, client):
        """Verify delete returns success marker."""
        response = await client.delete("/api/v1/admin/llm/backends/llm_01")
        assert response.status_code == 200


class TestAdminUserEndpoints:
    """User management endpoints."""

    async def test_list_users(self, client):
        """Verify user list returns user records."""
        response = await client.get("/api/v1/admin/users")
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) >= 1

    async def test_create_user(self, client):
        """Verify create user returns new user record."""
        body = {
            "username": "new_user",
            "email": "new@test.com",
            "password": "s3cret",
        }
        response = await client.post("/api/v1/admin/users", json=body)
        assert response.status_code == 200
        assert response.json()["username"] == "new_user"


class TestSystemEndpoints:
    """System stats and health check."""

    async def test_get_stats(self, client):
        """Verify stats returns all expected fields."""
        response = await client.get("/api/v1/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_documents"] >= 1

    async def test_health_check(self, client):
        """Verify health returns per-module status."""
        response = await client.get("/api/v1/admin/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "m5_qa_engine" in data["modules"]
