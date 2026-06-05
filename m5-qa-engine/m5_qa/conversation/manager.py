"""
M5 QA Engine — Conversation Manager.

WHAT: SQLite-backed persistence for M5's conversation history, messages,
      and premium quota tracking. Uses aiosqlite for async I/O and manages
      three tables: conversations, messages, quotas.

WHY: M5 manages its own SQLite database (not through M2's RelationalDB)
     because conversation management is M5-specific business logic. M2 is
     a storage abstraction layer that should remain unaware of M5's schema
     and usage patterns. The quotas table tracks per-user daily premium
     usage to enforce tier-based fair-use limits.
"""

from __future__ import annotations

import json
import time
import uuid

import aiosqlite

from contracts.qa_engine import Message, ConversationSummary


# Tier-based daily premium quota limits.
# Basic users get 3 premium uses per day, Pro users get 10,
# and Enterprise users have unlimited (-1) premium access.
TIER_QUOTA_LIMITS: dict[str, int] = {
    "basic": 3,
    "pro": 10,
    "enterprise": -1,  # unlimited
}


class ConversationManager:
    """
    WHAT: Manages conversations, messages, and quotas in M5's SQLite database.

    Three tables:
      - conversations: Metadata for each chat conversation.
      - messages: Individual messages within a conversation, with optional
        citations stored as JSON.
      - quotas: Per-user, per-date premium quota tracking with tier-aware limits.

    IDs are generated as uuid4().hex[:12] (12 hex chars — compact but unique).
    Timestamps are Unix epoch floats (from time.time()) for simplicity.

    WHY: Conversation state must persist across sessions and survive server
         restarts. SQLite is chosen for personal/single-server deployments
         (no external database dependency). The quotas table supports
         tier-based fair usage enforcement — Basic users are capped at
         3 premium queries per day, Pro at 10, Enterprise unlimited.
    """

    def __init__(self, db_path: str = "./data/m5_qa.db"):
        """
        WHAT: Initialize the conversation manager with a database path.

        Args:
            db_path: Path to the SQLite database file. Defaults to
                     ./data/m5_qa.db as configured in QAConfig.
        """
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_tables(self, conn: aiosqlite.Connection) -> None:
        """
        WHAT: Create the three M5 tables if they don't already exist.

        WHY: Called at the start of every public method to guarantee the
             schema is present regardless of initialization order. Using
             CREATE TABLE IF NOT EXISTS makes this idempotent and safe
             to call repeatedly.

        Tables:
          - conversations: Core chat session metadata.
          - messages: Individual messages linked to a conversation.
            citations_json stores the Citation list as a JSON string
            for schema flexibility (no fixed citation schema in SQLite).
          - quotas: Per-user daily premium usage tracker. PRIMARY KEY
            on (user_id, date) ensures one row per user per day.
        """
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at REAL,
                updated_at REAL
            );
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations_json TEXT,
                created_at REAL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
            );
            CREATE TABLE IF NOT EXISTS quotas (
                user_id TEXT NOT NULL,
                date TEXT NOT NULL,
                tier TEXT NOT NULL,
                premium_used INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, date)
            );
        """)
        await conn.commit()

    @staticmethod
    def _generate_id() -> str:
        """
        WHAT: Generate a compact unique ID using uuid4.

        WHY: 12 hex chars from UUID v4 gives ~2.8e14 possible values,
             which is sufficient for a single-server deployment while
             keeping IDs short and URL-friendly.
        """
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _row_to_message(row: tuple) -> Message:
        """
        WHAT: Convert a messages table row to a Message dataclass.

        The row format from SQLite is:
          (message_id, conversation_id, role, content, citations_json, created_at)

        Args:
            row: A tuple from the messages table query.

        Returns:
            A Message dataclass with role and content populated.
        """
        return Message(role=row[2], content=row[3])

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def create_conversation(
        self, user_id: str, title: str = "New Chat"
    ) -> str:
        """
        WHAT: Create a new conversation and return its ID.

        Args:
            user_id: The owning user's identifier.
            title: Human-readable conversation title. Defaults to "New Chat".

        Returns:
            The generated conversation_id (12-char hex string).
        """
        conversation_id = self._generate_id()
        now = time.time()

        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)
            await conn.execute(
                """INSERT INTO conversations
                   (conversation_id, user_id, title, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (conversation_id, user_id, title, now, now),
            )
            await conn.commit()

        return conversation_id

    async def list_conversations(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[ConversationSummary]:
        """
        WHAT: List a user's conversations, newest first, with message counts.

        The message_count is computed via a LEFT JOIN + COUNT subquery so
        each summary row includes the number of messages in that conversation.

        Args:
            user_id: The user whose conversations to list.
            limit: Max number of conversations to return (default 50).
            offset: Pagination offset (default 0).

        Returns:
            A list of ConversationSummary objects, ordered by updated_at DESC.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)
            # Use LEFT JOIN to include message count even for empty conversations
            cursor = await conn.execute(
                """SELECT
                       c.conversation_id,
                       c.title,
                       c.created_at,
                       c.updated_at,
                       COUNT(m.message_id) AS message_count
                   FROM conversations c
                   LEFT JOIN messages m ON c.conversation_id = m.conversation_id
                   WHERE c.user_id = ?
                   GROUP BY c.conversation_id
                   ORDER BY c.updated_at DESC
                   LIMIT ? OFFSET ?""",
                (user_id, limit, offset),
            )
            rows = await cursor.fetchall()

        return [
            ConversationSummary(
                conversation_id=row[0],
                title=row[1],
                created_at=str(row[2]),   # Unix timestamp as string
                updated_at=str(row[3]),   # Unix timestamp as string
                message_count=row[4],
            )
            for row in rows
        ]

    async def get_conversation(self, conversation_id: str) -> list[Message]:
        """
        WHAT: Retrieve all messages for a conversation in chronological order.

        Args:
            conversation_id: The conversation to fetch messages for.

        Returns:
            A list of Message objects ordered by created_at (oldest first).
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)
            cursor = await conn.execute(
                """SELECT message_id, conversation_id, role, content,
                          citations_json, created_at
                   FROM messages
                   WHERE conversation_id = ?
                   ORDER BY created_at ASC""",
                (conversation_id,),
            )
            rows = await cursor.fetchall()

        return [self._row_to_message(row) for row in rows]

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        WHAT: Delete a conversation and all its messages (cascading).

        WHY: We manually delete messages first because SQLite's FOREIGN KEY
             with default PRAGMA settings does NOT enforce cascading deletes.
             The explicit DELETE ensures orphaned messages don't accumulate.

        Args:
            conversation_id: The conversation to delete.

        Returns:
            True if a conversation was deleted, False if it didn't exist.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)
            # Delete messages first (child rows), then the conversation (parent row)
            await conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            cursor = await conn.execute(
                "DELETE FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def rename_conversation(self, conversation_id: str, title: str) -> bool:
        """
        WHAT: Rename a conversation (update its title and updated_at timestamp).

        WHY: M6 frontend provides an inline rename feature (right-click → Rename).
             This endpoint persists the new title so it survives page reload.

        Returns:
            True if the conversation was found and renamed, False if not found.
        """
        now = time.time()
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)
            cursor = await conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? "
                "WHERE conversation_id = ?",
                (title, now, conversation_id),
            )
            await conn.commit()
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        citations: list | None = None,
    ) -> Message:
        """
        WHAT: Append a message to a conversation.

        Also updates the conversation's updated_at timestamp so the
        conversation list stays sorted correctly.

        Args:
            conversation_id: The conversation to add the message to.
            role: Message role ("user", "assistant", or "system").
            content: The message text content.
            citations: Optional list of citation dicts, stored as JSON.

        Returns:
            The created Message object.
        """
        message_id = self._generate_id()
        now = time.time()
        citations_json = json.dumps(citations) if citations else None

        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)
            await conn.execute(
                """INSERT INTO messages
                   (message_id, conversation_id, role, content, citations_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (message_id, conversation_id, role, content, citations_json, now),
            )
            # Update the conversation's updated_at so it sorts to the top
            await conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                (now, conversation_id),
            )
            await conn.commit()

        return Message(role=role, content=content)

    async def get_messages(
        self, conversation_id: str, limit: int = 50
    ) -> list[Message]:
        """
        WHAT: Retrieve the most recent messages for a conversation.

        This is for display purposes — returns at most `limit` messages
        in chronological order. For full history retrieval, use
        get_conversation() which has no limit.

        Args:
            conversation_id: The conversation to fetch messages for.
            limit: Max number of recent messages to return (default 50).

        Returns:
            A list of Message objects ordered by created_at (oldest first).
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)
            # Get the most recent messages by selecting the last N rows
            # in chronological order. We use a subquery to get the latest
            # `limit` message IDs, then select those in ASC order.
            cursor = await conn.execute(
                """SELECT message_id, conversation_id, role, content,
                          citations_json, created_at
                   FROM messages
                   WHERE conversation_id = ?
                   ORDER BY created_at ASC
                   LIMIT ?""",
                (conversation_id, limit),
            )
            rows = await cursor.fetchall()

        return [self._row_to_message(row) for row in rows]

    # ------------------------------------------------------------------
    # Quotas
    # ------------------------------------------------------------------

    async def get_quota(self, user_id: str, date: str) -> dict:
        """
        WHAT: Retrieve the quota record for a user on a given date.

        If no record exists, returns a default dict indicating no usage
        for the basic tier (the default for new users).

        Args:
            user_id: The user identifier.
            date: Date string in "YYYY-MM-DD" format.

        Returns:
            A dict with keys: user_id, date, tier, premium_used.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)
            cursor = await conn.execute(
                "SELECT user_id, date, tier, premium_used FROM quotas WHERE user_id = ? AND date = ?",
                (user_id, date),
            )
            row = await cursor.fetchone()

        if row is None:
            return {
                "user_id": user_id,
                "date": date,
                "tier": "basic",
                "premium_used": 0,
            }

        return {
            "user_id": row[0],
            "date": row[1],
            "tier": row[2],
            "premium_used": row[3],
        }

    async def consume_premium(self, user_id: str, date: str) -> bool:
        """
        WHAT: Attempt to consume one premium query for a user on a given date.
              Returns True if quota was available, False if exhausted.

        The quota limit depends on the user's tier:
          - basic: 3 per day
          - pro: 10 per day
          - enterprise: unlimited (always returns True)

        If no quota row exists for (user_id, date), a new row is created
        with tier "basic" and premium_used = 0 before attempting consumption.
        This means first-time users default to Basic tier with 3 premium/day.

        WHY: Premium queries (Self-RAG mode, Deep Research) consume more
             resources and must be rate-limited. The per-day-per-user model
             is simple to understand and enforce.

        Args:
            user_id: The user identifier.
            date: Date string in "YYYY-MM-DD" format.

        Returns:
            True if the premium query is allowed, False if the quota is exhausted.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_tables(conn)

            # Fetch current quota state
            cursor = await conn.execute(
                "SELECT tier, premium_used FROM quotas WHERE user_id = ? AND date = ?",
                (user_id, date),
            )
            row = await cursor.fetchone()

            if row is None:
                # No quota row yet — create one with default basic tier
                tier = "basic"
                premium_used = 0
                await conn.execute(
                    "INSERT INTO quotas (user_id, date, tier, premium_used) VALUES (?, ?, ?, ?)",
                    (user_id, date, tier, premium_used),
                )
            else:
                tier, premium_used = row

            # Check tier limit
            limit = TIER_QUOTA_LIMITS.get(tier, 3)

            if limit == -1:
                # Enterprise tier: unlimited premium queries
                await conn.execute(
                    "UPDATE quotas SET premium_used = premium_used + 1 WHERE user_id = ? AND date = ?",
                    (user_id, date),
                )
                await conn.commit()
                return True

            if premium_used >= limit:
                # Quota exhausted
                return False

            # Increment premium_used and grant access
            await conn.execute(
                "UPDATE quotas SET premium_used = premium_used + 1 WHERE user_id = ? AND date = ?",
                (user_id, date),
            )
            await conn.commit()
            return True
