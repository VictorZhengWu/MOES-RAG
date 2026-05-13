"""
Mock conversation management endpoints.

WHY: M6's sidebar shows a conversation list with create/rename/delete
capabilities. These endpoints must return correct data shapes so the
frontend conversation management logic can be fully tested in Phase 1.
"""

from fastapi import APIRouter

from .data import mock_conversations, mock_conversation_messages

router = APIRouter(prefix="/api/v1")


@router.get("/conversations")
async def list_conversations():
    """Return a list of fake conversations.

    WHY: M6 renders the sidebar conversation list from this endpoint.
    Returning multiple items with different dates tests the sorting
    and timestamp formatting logic in the frontend.
    """
    convos = mock_conversations()
    return {"conversations": convos, "total": len(convos)}


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """Return fake messages for a conversation.

    WHY: When a user clicks a conversation, M6 fetches the full
    message history. The response includes alternating user/assistant
    roles so the frontend can test message bubble alignment.
    """
    return {
        "conversation_id": conv_id,
        "messages": mock_conversation_messages(conv_id),
    }


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """Pretend to delete a conversation.

    WHY: M6's conversation list has a delete action. The mock
    returns success immediately so the frontend can test the
    optimistic-remove UI pattern.
    """
    return {"conversation_id": conv_id, "deleted": True}


@router.patch("/conversations/{conv_id}")
async def rename_conversation(conv_id: str, body: dict):
    """Pretend to rename a conversation.

    WHY: M6 supports inline-edit of conversation titles. This
    endpoint returns the new title so the frontend can update
    its local state without re-fetching the full list.
    """
    return {"conversation_id": conv_id, "title": body.get("title", "Untitled")}
