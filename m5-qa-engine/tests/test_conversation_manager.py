"""
Tests for M5 QA Engine — Conversation Manager (manager.py).

WHAT: Integration-style unit tests for ConversationManager — verifying
      CRUD operations on conversations, messages, and quota consumption
      using a temporary SQLite database per test.

WHY: The conversation manager is the persistence layer for M5's chat
     history and quota tracking. These tests ensure data integrity
     across all three tables (conversations, messages, quotas).
"""

import pytest
import tempfile
import os

from contracts.qa_engine import Message
from m5_qa.conversation.manager import ConversationManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def manager():
    """
    WHAT: Creates a ConversationManager backed by a temporary SQLite database.
    WHY: Each test gets an isolated DB so tests don't interfere with each other.
         The temp file is automatically cleaned up when the test finishes.
    """
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_m5_qa_")
    os.close(fd)  # Close the file descriptor, we only need the path
    mgr = ConversationManager(db_path=path)
    yield mgr
    # Clean up the temp file
    try:
        os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Tests: Conversations CRUD
# ---------------------------------------------------------------------------

class TestCreateAndList:
    """Tests for create_conversation() and list_conversations()."""

    @pytest.mark.asyncio
    async def test_create_and_list(self, manager):
        """
        WHAT: Create 2 conversations for the same user, then list them.
              Expect both to appear in the listing, ordered by most recent first.
        WHY: This is the core conversation lifecycle — users need to see
             all their past conversations in the sidebar.
        """
        # Create two conversations
        conv1_id = await manager.create_conversation("user001", title="Chat about DNV rules")
        conv2_id = await manager.create_conversation("user001", title="Chat about ABS standards")

        assert conv1_id != conv2_id, "Conversation IDs must be unique"

        # List conversations for this user
        convos = await manager.list_conversations("user001")
        assert len(convos) == 2

        # Most recently created should be first
        assert convos[0].conversation_id == conv2_id
        assert convos[0].title == "Chat about ABS standards"
        assert convos[1].conversation_id == conv1_id
        assert convos[1].title == "Chat about DNV rules"

        # Message counts should be 0 for new conversations
        assert convos[0].message_count == 0
        assert convos[1].message_count == 0


class TestAddAndGetMessages:
    """Tests for add_message() and get_messages()."""

    @pytest.mark.asyncio
    async def test_add_and_get_messages(self, manager):
        """
        WHAT: Add messages to a conversation, then retrieve them.
              Verify messages are returned in chronological order.
        WHY: Chat history retrieval must return messages in the correct
             order so the LLM sees the conversation as it happened.
        """
        # Create a conversation first
        conv_id = await manager.create_conversation("user001", title="Test chat")

        # Add messages
        msg1 = await manager.add_message(conv_id, "user", "What is DNV-OS-C101?")
        msg2 = await manager.add_message(conv_id, "assistant", "DNV-OS-C101 is the standard for...")

        # Returned Message objects have role+content (not message_id — that's internal DB state)
        assert msg1.role == "user"
        assert msg2.role == "assistant"
        assert msg1.content != msg2.content

        # Retrieve messages
        messages = await manager.get_messages(conv_id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "What is DNV-OS-C101?"
        assert messages[1].role == "assistant"
        assert "DNV-OS-C101" in messages[1].content


class TestDeleteConversation:
    """Tests for delete_conversation()."""

    @pytest.mark.asyncio
    async def test_delete_conversation(self, manager):
        """
        WHAT: Create a conversation, then delete it. Verify it no longer
              appears in the listing.
        WHY: Users need to be able to remove conversations they no longer
             want, and the deletion must be reflected immediately.
        """
        conv_id = await manager.create_conversation("user001", title="To be deleted")

        # Verify it exists initially
        convos_before = await manager.list_conversations("user001")
        assert len(convos_before) == 1

        # Delete it
        deleted = await manager.delete_conversation(conv_id)
        assert deleted is True

        # Verify it no longer appears
        convos_after = await manager.list_conversations("user001")
        assert len(convos_after) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, manager):
        """
        WHAT: Attempt to delete a conversation ID that doesn't exist.
        WHY: Graceful handling of invalid IDs — should return False,
             not crash.
        """
        deleted = await manager.delete_conversation("nonexistent_id")
        assert deleted is False


class TestQuotaConsume:
    """Tests for quota management via consume_premium()."""

    @pytest.mark.asyncio
    async def test_quota_consume(self, manager):
        """
        WHAT: Consume premium quota 3 times successfully, 4th time fails.
        WHY: Basic tier users get 3 premium queries per day. The 4th
             attempt should be rejected to enforce fair usage.
        """
        user_id = "test_user"
        date = "2026-06-03"

        # First 3 consumes should succeed (Basic tier = 3 per day)
        assert await manager.consume_premium(user_id, date) is True
        assert await manager.consume_premium(user_id, date) is True
        assert await manager.consume_premium(user_id, date) is True

        # 4th consume should fail — quota exhausted
        assert await manager.consume_premium(user_id, date) is False

        # Verify the quota count in the DB
        quota = await manager.get_quota(user_id, date)
        assert quota["premium_used"] == 3
        assert quota["tier"] == "basic"
