"""
M8 API Gateway — Conversation Routes.

WHAT: Exposes M5's conversation management (list, get, delete, rename)
      through the gateway. All endpoints require API key authentication.

WHY: M6 frontend's conversations.ts already calls these endpoints via
     the HTTP client at BASE_URL = http://127.0.0.1:8000. Previously these
     routes hit the Mock Server; now they route to the real M5 QAEngine.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from m8_gateway.auth.key_manager import APIKey
from m8_gateway.auth.middleware import get_api_key
from m8_gateway.models.schemas import ConversationRenameRequest

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    request: Request,
    api_key: APIKey = Depends(get_api_key),
    search: str = "",
):
    """
    GET /api/v1/conversations?search=keyword — List user's conversations.

    WHAT: Returns conversation summaries, optionally filtered by search
          keyword (matches title). Delegates to M5 QAEngine.

    WHY: M6 sidebar has a search input. Client-side filtering works for
         small lists but degrades with 100+ conversations. Server-side
         filtering keeps the sidebar responsive at any scale.
    """
    engine = request.app.state.qa_engine
    if engine is None:
        raise HTTPException(500, "QA Engine not initialized")
    conversations = await engine.list_conversations(api_key.user_id)
    if search.strip():
        q = search.strip().lower()
        conversations = [c for c in conversations if q in c.title.lower()]
    return {"conversations": conversations}


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """
    GET /api/v1/conversations/:id — Get full conversation history.

    WHAT: Delegates to M5 QAEngine.get_conversation(). Returns all messages
          in the conversation with roles and content.

    WHY: M6 frontend calls this when opening an existing conversation to
         restore the full message history.
    """
    engine = request.app.state.qa_engine
    if engine is None:
        raise HTTPException(500, "QA Engine not initialized")
    messages = await engine.get_conversation(conversation_id, api_key.user_id)
    return {"conversation_id": conversation_id, "messages": messages}


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """
    DELETE /api/v1/conversations/:id — Delete a conversation.

    WHAT: Delegates to M5 QAEngine.delete_conversation(). Returns 404 if
          not found, 200 with {deleted: true} on success.

    WHY: M6 frontend right-click → Delete calls this endpoint.
    """
    engine = request.app.state.qa_engine
    if engine is None:
        raise HTTPException(500, "QA Engine not initialized")
    ok = await engine.delete_conversation(conversation_id, api_key.user_id)
    if not ok:
        raise HTTPException(404, "Conversation not found")
    return {"deleted": True}


@router.patch("/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    body: ConversationRenameRequest,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """
    PATCH /api/v1/conversations/:id — Rename a conversation.

    WHAT: Delegates to M5 QAEngine.rename_conversation() with the new title.
          Auto-validated by Pydantic: title must be 1-200 characters.

    WHY: M6 frontend right-click → Rename → inline edit → save calls this.
    """
    title = body.title.strip()

    engine = request.app.state.qa_engine
    if engine is None:
        raise HTTPException(500, "QA Engine not initialized")
    ok = await engine.rename_conversation(conversation_id, title)
    if not ok:
        raise HTTPException(404, "Conversation not found")
    return {"conversation_id": conversation_id, "title": title}
