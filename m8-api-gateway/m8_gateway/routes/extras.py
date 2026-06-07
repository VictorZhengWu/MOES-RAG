"""
M8 API Gateway — Share, Pin, Account Deletion, Projects routes.

WHAT: Additional user-facing routes beyond the core chat/auth/conversation API.
      - Share: generate shareable links for conversations
      - Pin: toggle conversation pin status
      - Account: delete user account with cascade
      - Projects: CRUD for grouping conversations into projects

WHY: M6 frontend UI has these features built but they were stubbed with
     console.log. These routes make them functional against real data.

Security: All routes require API key auth. Share links are public (no auth).
          Account deletion cascades all user data. DB tables created lazily.
"""

from __future__ import annotations

import hashlib
import secrets
import time
import aiosqlite

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from m8_gateway.auth.key_manager import APIKey
from m8_gateway.auth.middleware import get_api_key

router = APIRouter(tags=["extras"])

DB_PATH = __import__("os").environ.get("M8_DB_PATH", "./data/m8_gateway.db")
M6_BASE_URL = __import__("os").environ.get("M6_BASE_URL", "http://localhost:3000")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _ensure_shared_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS shared_conversations (
            share_token TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL,  -- NULL = never expires
            view_count INTEGER DEFAULT 0
        )
    """)
    await conn.commit()


async def _ensure_pinned_column(conn):
    """Add is_pinned column if it doesn't exist (idempotent migration)."""
    try:
        await conn.execute(
            "ALTER TABLE conversations ADD COLUMN is_pinned INTEGER DEFAULT 0"
        )
        await conn.commit()
    except aiosqlite.OperationalError:
        pass  # Column already exists


async def _ensure_projects_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS project_conversations (
            project_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            added_at REAL NOT NULL,
            PRIMARY KEY (project_id, conversation_id)
        )
    """)
    await conn.commit()


def _generate_id() -> str:
    return secrets.token_hex(8)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ShareResponse(BaseModel):
    share_token: str
    share_url: str


class SharedConversation(BaseModel):
    conversation_id: str
    messages: list[dict]


class PinRequest(BaseModel):
    is_pinned: bool


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class MoveConversationRequest(BaseModel):
    conversation_id: str


# ---------------------------------------------------------------------------
# Share routes
# ---------------------------------------------------------------------------


@router.post("/api/v1/conversations/{conversation_id}/share")
async def share_conversation(
    conversation_id: str,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """
    POST /api/v1/conversations/:id/share — Generate a shareable link.

    WHAT: Creates a share token (32-char hex, unguessable) for a conversation.
          Anyone with the link can view it without authentication.

    WHY: Users want to share Q&A sessions with colleagues. The share link
         is read-only and does not expose the user's API key.
    """
    share_token = secrets.token_hex(16)  # 32 chars = 128 bits entropy

    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_shared_table(conn)

        # Verify the user owns this conversation
        cursor = await conn.execute(
            "SELECT conversation_id FROM conversations "
            "WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, api_key.user_id),
        )
        if await cursor.fetchone() is None:
            raise HTTPException(404, "Conversation not found")

        await conn.execute(
            "INSERT INTO shared_conversations "
            "(share_token, conversation_id, owner_user_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            (share_token, conversation_id, api_key.user_id, time.time()),
        )
        await conn.commit()

    base = request.headers.get("origin") or M6_BASE_URL
    share_url = f"{base}/shared/{share_token}"

    return {"share_token": share_token, "share_url": share_url}


@router.delete("/api/v1/conversations/{conversation_id}/share")
async def revoke_share(
    conversation_id: str,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """
    DELETE /api/v1/conversations/:id/share — Revoke all share links for a conversation.

    WHAT: Deletes all share tokens for this conversation. Existing links
          return 404 immediately after revocation.

    WHY: Users may want to stop sharing a conversation without deleting it.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "DELETE FROM shared_conversations "
            "WHERE conversation_id = ? AND owner_user_id = ?",
            (conversation_id, api_key.user_id),
        )
        await conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(404, "No active share links found for this conversation")

    return {"revoked": True, "conversation_id": conversation_id}


@router.get("/api/v1/shared/{share_token}")
async def get_shared_conversation(share_token: str):
    """
    GET /api/v1/shared/:token — View a shared conversation (no auth required).

    WHAT: Public read-only endpoint. Anyone with the link can view the
          conversation. Increments view counter.

    WHY: Share links are designed to be sent to colleagues who may not
         have an account on the system.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_shared_table(conn)

        cursor = await conn.execute(
            "SELECT conversation_id, owner_user_id, expires_at "
            "FROM shared_conversations WHERE share_token = ?",
            (share_token,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(404, "Share link not found or has been removed")

        conv_id, owner_user_id, expires_at = row

        # Check expiry
        if expires_at and time.time() > expires_at:
            await conn.execute(
                "DELETE FROM shared_conversations WHERE share_token = ?",
                (share_token,),
            )
            await conn.commit()
            raise HTTPException(410, "Share link has expired")

        # Increment view count
        await conn.execute(
            "UPDATE shared_conversations SET view_count = view_count + 1 "
            "WHERE share_token = ?",
            (share_token,),
        )
        await conn.commit()

    # Fetch messages (read-only, no user ownership check needed)
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT role, content, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv_id,),
        )
        messages = [
            {"role": r[0], "content": r[1], "created_at": r[2]}
            async for r in cursor
        ]

    return {"conversation_id": conv_id, "messages": messages}


# ---------------------------------------------------------------------------
# Pin route
# ---------------------------------------------------------------------------


@router.patch("/api/v1/conversations/{conversation_id}/pin")
async def pin_conversation(
    conversation_id: str,
    body: PinRequest,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """
    PATCH /api/v1/conversations/:id/pin — Toggle pin status.

    WHAT: Sets or unsets the is_pinned flag. Pinned conversations appear
          at the top of the user's conversation list.

    WHY: Users pin frequently-used conversations for quick access.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_pinned_column(conn)

        cursor = await conn.execute(
            "UPDATE conversations SET is_pinned = ?, updated_at = ? "
            "WHERE conversation_id = ? AND user_id = ?",
            (1 if body.is_pinned else 0, time.time(), conversation_id, api_key.user_id),
        )
        await conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(404, "Conversation not found")

    return {"conversation_id": conversation_id, "is_pinned": body.is_pinned}


# ---------------------------------------------------------------------------
# Account deletion route
# ---------------------------------------------------------------------------


@router.delete("/auth/account")
async def delete_account(
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """
    DELETE /auth/account — Permanently delete the authenticated user's account.

    WHAT: Cascade-deletes ALL user data:
          - API keys (api_keys table)
          - OAuth links (oauth_accounts table)
          - Conversations + messages
          - Shared links
          - Password reset tokens

    WHY: GDPR compliance and user autonomy. Users must be able to delete
         their own data. This operation is IRREVERSIBLE.

    Security: Requires valid API key. Only affects the authenticated user.
              The API key used for this request becomes invalid after deletion.
    """
    user_id = api_key.user_id
    async with aiosqlite.connect(DB_PATH) as conn:
        # Verify user exists
        cursor = await conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(404, "Account not found")

        # Delete in dependency order (foreign key cascade is manual for SQLite)
        await conn.execute(
            "DELETE FROM shared_conversations WHERE owner_user_id = ?",
            (user_id,),
        )
        # Delete messages for user's conversations
        await conn.execute("""
            DELETE FROM messages WHERE conversation_id IN (
                SELECT conversation_id FROM conversations WHERE user_id = ?
            )
        """, (user_id,))
        await conn.execute(
            "DELETE FROM conversations WHERE user_id = ?", (user_id,)
        )
        await conn.execute(
            "DELETE FROM api_keys WHERE user_id = ?", (user_id,)
        )
        await conn.execute(
            "DELETE FROM oauth_accounts WHERE user_id = ?", (user_id,)
        )
        await conn.execute(
            "DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,)
        )
        await conn.execute(
            "DELETE FROM users WHERE user_id = ?", (user_id,)
        )
        await conn.commit()

    return {"deleted": True, "user_id": user_id}


# ---------------------------------------------------------------------------
# Avatar upload
# ---------------------------------------------------------------------------

AVATAR_DIR = __import__("os").environ.get("AVATAR_DIR", "./data/avatars")
AVATAR_MAX_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/api/v1/user/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    request: Request = None,
    api_key: APIKey = Depends(get_api_key),
):
    """
    POST /api/v1/user/avatar — Upload a profile avatar image.

    WHAT: Saves the uploaded image (PNG/JPG, max 5MB) to the avatars
          directory, named by user_id. Overwrites any previous avatar.

    WHY: M6 Profile settings has a file selector for avatars. Previously
         it only console.log'd the file. This endpoint makes it functional.
    """
    suffix = (file.filename or "avatar.png").rsplit(".", 1)[-1].lower()
    if suffix not in ("png", "jpg", "jpeg", "gif", "webp"):
        raise HTTPException(400, "Only PNG, JPG, GIF, or WebP images are allowed")

    content = await file.read()
    if len(content) > AVATAR_MAX_SIZE:
        raise HTTPException(413, f"Avatar too large. Maximum: {AVATAR_MAX_SIZE // (1024*1024)}MB")

    import os as _os
    _os.makedirs(AVATAR_DIR, exist_ok=True)
    avatar_path = _os.path.join(AVATAR_DIR, f"{api_key.user_id}.{suffix}")
    with open(avatar_path, "wb") as f:
        f.write(content)

    avatar_url = f"/avatars/{api_key.user_id}.{suffix}"
    return {"avatar_url": avatar_url}


# ---------------------------------------------------------------------------
# Projects routes
# ---------------------------------------------------------------------------


@router.post("/api/v1/projects")
async def create_project(
    body: ProjectCreate,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """POST /api/v1/projects — Create a new project."""
    project_id = _generate_id()
    now = time.time()

    if not body.name.strip():
        raise HTTPException(400, "Project name cannot be empty")

    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_projects_table(conn)
        await conn.execute(
            "INSERT INTO projects (project_id, user_id, name, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, api_key.user_id, body.name.strip(), body.description.strip(), now, now),
        )
        await conn.commit()

    return {"project_id": project_id, "name": body.name.strip(), "description": body.description.strip()}


@router.get("/api/v1/projects")
async def list_projects(
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """GET /api/v1/projects — List user's projects with conversation counts."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_projects_table(conn)
        cursor = await conn.execute("""
            SELECT p.project_id, p.name, p.description, p.created_at, p.updated_at,
                   COUNT(pc.conversation_id) as conv_count
            FROM projects p
            LEFT JOIN project_conversations pc ON p.project_id = pc.project_id
            WHERE p.user_id = ?
            GROUP BY p.project_id
            ORDER BY p.updated_at DESC
        """, (api_key.user_id,))
        return [
            {"project_id": r[0], "name": r[1], "description": r[2],
             "created_at": r[3], "updated_at": r[4], "conversation_count": r[5]}
            async for r in cursor
        ]


@router.post("/api/v1/projects/{project_id}/conversations")
async def move_conversation_to_project(
    project_id: str,
    body: MoveConversationRequest,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """POST /api/v1/projects/:id/conversations — Move a conversation into a project."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_projects_table(conn)

        # Verify project ownership
        cursor = await conn.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, api_key.user_id),
        )
        if await cursor.fetchone() is None:
            raise HTTPException(404, "Project not found")

        # Verify conversation ownership
        cursor = await conn.execute(
            "SELECT 1 FROM conversations WHERE conversation_id = ? AND user_id = ?",
            (body.conversation_id, api_key.user_id),
        )
        if await cursor.fetchone() is None:
            raise HTTPException(404, "Conversation not found")

        # Upsert (move or remap)
        await conn.execute(
            "INSERT OR REPLACE INTO project_conversations (project_id, conversation_id, added_at) "
            "VALUES (?, ?, ?)",
            (project_id, body.conversation_id, time.time()),
        )
        await conn.commit()

    return {"project_id": project_id, "conversation_id": body.conversation_id}


@router.delete("/api/v1/projects/{project_id}")
async def delete_project(
    project_id: str,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """DELETE /api/v1/projects/:id — Delete a project (does not delete conversations)."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_projects_table(conn)

        cursor = await conn.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?",
            (project_id, api_key.user_id),
        )
        if await cursor.fetchone() is None:
            raise HTTPException(404, "Project not found")

        await conn.execute("DELETE FROM project_conversations WHERE project_id = ?", (project_id,))
        await conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        await conn.commit()

    return {"deleted": True}
