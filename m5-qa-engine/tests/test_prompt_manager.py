"""
Tests for M5 QA Engine -- Prompt Manager (prompt_manager.py).

WHAT: Unit tests for PromptManager -- a DB-backed prompt template store
      with multi-language fallback (requested lang -> en -> hardcoded default).

WHY: Each test uses a temp SQLite DB (tempfile.mkdtemp) to avoid affecting
     real data. Tests cover: English fetch, Chinese fallback, hardcoded
     default fallback, UPSERT semantics, template variable filling, and
     listing stored prompts.
"""

import pytest
import tempfile
import os

from m5_qa.generation.prompt_manager import PromptManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db_path():
    """
    WHAT: Create a temporary directory and return a unique db path in it.
    WHY: Each test gets its own isolated SQLite database, preventing
         cross-test contamination and avoiding writes to the real DB.
    """
    tmpdir = tempfile.mkdtemp(prefix="m5_test_prompts_")
    db_path = os.path.join(tmpdir, "test_m5_qa.db")
    yield db_path
    # Cleanup: remove the temp file and directory
    if os.path.exists(db_path):
        os.remove(db_path)
    os.rmdir(tmpdir)


@pytest.fixture
def manager(temp_db_path):
    """
    WHAT: Create a PromptManager instance wired to a temp DB.
    WHY: Tests use the actual aiosqlite-backed implementation, not mocks,
         to verify real DB behavior (UPSERT, SELECT, fallback logic).
    """
    return PromptManager(db_path=temp_db_path)


# ---------------------------------------------------------------------------
# 1. test_get_prompt_english -- store and retrieve English prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_prompt_english(manager):
    """
    WHAT: Store a prompt in English and retrieve it by prompt_id and language.
    WHY: The most basic happy-path: when the exact requested language exists
         in the DB, get_prompt must return it directly with no fallback.
    """
    # Store an English system prompt
    await manager.set_prompt(
        prompt_id="system",
        language="en",
        name="System Prompt",
        content="You are an expert assistant."
    )
    # Retrieve it by English language
    result = await manager.get_prompt("system", language="en")
    assert result == "You are an expert assistant."


# ---------------------------------------------------------------------------
# 2. test_get_prompt_chinese_fallback -- cn not stored, falls back to en
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_prompt_chinese_fallback(manager):
    """
    WHAT: Request a prompt in Chinese (cn) when only the English (en) version
          exists in the DB.
    WHY: The fallback chain is language -> en -> hardcoded default. If the
         requested language is missing but English exists, it must return
         the English template rather than the hardcoded default.
    """
    # Store only the English version
    await manager.set_prompt(
        prompt_id="system",
        language="en",
        name="System Prompt",
        content="Answer based on context."
    )
    # Request Chinese -- should fall back to English
    result = await manager.get_prompt("system", language="cn")
    assert result == "Answer based on context."


# ---------------------------------------------------------------------------
# 3. test_get_prompt_hardcoded_default -- nonexistent prompt falls back to code
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_prompt_hardcoded_default(manager):
    """
    WHAT: Request a prompt_id that does not exist in the DB at all.
    WHY: When neither the requested language nor English exists in the DB,
         get_prompt must return the hardcoded default from _DEFAULT_PROMPTS
         (or a placeholder). This ensures the system never returns None.
    """
    result = await manager.get_prompt("system_en", language="en")
    # The hardcoded default for system_en exists in _DEFAULT_PROMPTS
    assert "Marine & Offshore Engineering" in result
    assert "{retrieved_context}" in result


# ---------------------------------------------------------------------------
# 4. test_set_prompt_upsert -- insert then update, verify content changed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_prompt_upsert(manager):
    """
    WHAT: Call set_prompt twice with the same prompt_id + language --
          the second call must UPDATE the existing row, not create a duplicate.
    WHY: The UPSERT semantic (ON CONFLICT DO UPDATE) allows admin UI / API
         to simply "save" without needing separate insert vs. update logic.
    """
    # First insert
    await manager.set_prompt(
        prompt_id="greeting",
        language="en",
        name="Greeting",
        content="Hello"
    )
    # Second call with same prompt_id + language -- should update
    await manager.set_prompt(
        prompt_id="greeting",
        language="en",
        name="Greeting V2",
        content="Hello, world!"
    )
    result = await manager.get_prompt("greeting", language="en")
    # The content must reflect the UPDATE, not the original INSERT
    assert result == "Hello, world!"


# ---------------------------------------------------------------------------
# 5. test_fill_template -- replace {var1} and {var2} in template string
# ---------------------------------------------------------------------------

def test_fill_template():
    """
    WHAT: fill_template() replaces {variable} placeholders with provided values.
    WHY: Prompt templates contain placeholder variables like {retrieved_context}
         and {graph_context} that are filled at runtime before sending to the
         LLM. The method must correctly substitute all provided variables.
    """
    manager = PromptManager(db_path=":memory:")
    template = "Context: {retrieved_context}. Graph: {graph_context}."
    result = manager.fill_template(
        template,
        retrieved_context="Doc 1: Some text",
        graph_context="Entity: Ship, Relation: has_part"
    )
    expected = "Context: Doc 1: Some text. Graph: Entity: Ship, Relation: has_part."
    assert result == expected


# ---------------------------------------------------------------------------
# 6. test_list_prompts -- store 2 prompts, list returns both
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_prompts(manager):
    """
    WHAT: Store two prompts with different prompt_ids and verify list_prompts
          returns both entries with the correct fields.
    WHY: Admin UIs and management tools need to enumerate all stored templates.
         The returned list must contain prompt_id, language, and name fields.
    """
    await manager.set_prompt(
        prompt_id="system",
        language="en",
        name="System Prompt",
        content="You are an expert."
    )
    await manager.set_prompt(
        prompt_id="citation",
        language="en",
        name="Citation Prompt",
        content="Always cite sources."
    )
    prompts = await manager.list_prompts()
    assert len(prompts) == 2
    # Verify the returned structure has the expected keys
    assert {"prompt_id", "language", "name"}.issubset(set(prompts[0].keys()))
    prompt_ids = {p["prompt_id"] for p in prompts}
    assert prompt_ids == {"system", "citation"}
