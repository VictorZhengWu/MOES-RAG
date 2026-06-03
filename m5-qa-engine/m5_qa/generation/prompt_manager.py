"""
M5 QA Engine -- Prompt Manager (DB-stored templates).

WHAT: SQLite-backed storage for prompt templates with multi-language support
      and a fallback chain: requested language -> English -> hardcoded default.

WHY: Decouples prompt text from application code so templates can be updated
     via admin UI without redeploying the QA engine. Phase 3 will add version
     control and A/B testing capabilities on top of this foundation.
"""

import aiosqlite


# ---------------------------------------------------------------------------
# Hardcoded default prompts (fallback when DB has no entry)
# ---------------------------------------------------------------------------

# WHAT: Pre-defined system prompts in English and Chinese used as the final
#       fallback when no template exists in the SQLite database.
# WHY: These are the default templates for the Marine & Offshore domain.
#      Administrators can override them via set_prompt() without code changes.
_DEFAULT_PROMPTS = {
    "system_en": """You are a Marine & Offshore Engineering expert assistant.
Answer questions based STRICTLY on the provided context documents.
If the context does not contain sufficient information, say so.
Always cite the source regulation and clause when answering.

## Context Documents
{retrieved_context}

## Knowledge Graph Insights
{graph_context}

## Instructions
- Answer in the same language as the question
- Include specific technical values when available
- Cite sources using [number] format matching the citations list
- For regulatory questions, note the classification society and clause""",

    "system_cn": """您是一位船舶与海洋工程专家助手。
请严格根据提供的上下文文档回答问题。
如果上下文中没有足够信息，请如实说明。
回答时请始终引用来源规范和条款。

## 上下文文档
{retrieved_context}

## 知识图谱洞察
{graph_context}

## 指示
- 用与问题相同的语言回答
- 包含具体的数值信息（如有）
- 使用 [编号] 格式引用来源
- 对于规范问题，注明船级社和条款编号""",
}


def _get_default_prompt(prompt_id: str) -> str:
    """
    WHAT: Return the hardcoded default prompt text for the given prompt_id,
          or a placeholder string if the prompt_id is not recognized.
    WHY: This is the final fallback in the get_prompt chain (after DB
         language match and DB English match both fail). It guarantees
         get_prompt() never returns None.
    """
    return _DEFAULT_PROMPTS.get(
        prompt_id,
        f"[Prompt {prompt_id} not found]",
    )


# ---------------------------------------------------------------------------
# PromptManager
# ---------------------------------------------------------------------------

class PromptManager:
    """
    WHAT: DB-backed prompt template store.

    Stores prompt templates in a SQLite table (m5_prompts) with support for
    multiple languages. Provides a fallback chain:
      1. Exact language match in DB
      2. English ("en") match in DB
      3. Hardcoded default from _DEFAULT_PROMPTS

    WHY: Decouples prompt text from code -- templates can be updated via
         admin UI without redeploying. Phase 3 adds version control and
         A/B testing.
    """

    def __init__(self, db_path: str = "./data/m5_qa.db"):
        """
        WHAT: Initialize the prompt manager with a path to the SQLite DB.

        Args:
            db_path: Filesystem path to the SQLite database file.
                     Use ":memory:" for in-memory databases (testing).
                     Defaults to ./data/m5_qa.db for production use.
        """
        self._db_path = db_path

    async def _ensure_table(self, conn):
        """
        WHAT: Create the m5_prompts table if it does not already exist.
        WHY: Called before every DB operation to guarantee the schema
             is present regardless of deployment order.
        """
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS m5_prompts (
                prompt_id TEXT NOT NULL,
                language TEXT NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (prompt_id, language)
            )
        """)
        await conn.commit()

    async def get_prompt(self, prompt_id: str, language: str = "en") -> str:
        """
        WHAT: Fetch a prompt template with a language fallback chain:
              requested language -> English -> hardcoded default.

        Args:
            prompt_id: Unique identifier for the prompt (e.g. "system",
                       "citation", "greeting").
            language: Requested language code (e.g. "en", "cn", "ja").
                      Defaults to "en".

        Returns:
            The prompt template text. Never returns None -- the hardcoded
            default serves as the final fallback.

        WHY: The UI may request a prompt in any supported language. Rather
             than requiring every language to be populated, we fall back
             gracefully through progressively more generic templates.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_table(conn)

            # Step 1: Try the exact requested language
            cursor = await conn.execute(
                "SELECT content FROM m5_prompts WHERE prompt_id=? AND language=?",
                (prompt_id, language),
            )
            row = await cursor.fetchone()
            if row:
                return row[0]

            # Step 2: Fallback to English (if not already tried)
            if language != "en":
                cursor = await conn.execute(
                    "SELECT content FROM m5_prompts WHERE prompt_id=? AND language='en'",
                    (prompt_id,),
                )
                row = await cursor.fetchone()
                if row:
                    return row[0]

            # Step 3: Hardcoded default (final fallback)
            return _get_default_prompt(prompt_id)

    async def set_prompt(
        self,
        prompt_id: str,
        language: str,
        name: str,
        content: str,
    ) -> None:
        """
        WHAT: Insert or update a prompt template using UPSERT semantics.

        If a row with the same (prompt_id, language) already exists, its
        name and content are updated. Otherwise, a new row is inserted.

        Args:
            prompt_id: Unique identifier for the prompt.
            language: Language code (e.g. "en", "cn").
            name: Human-readable name for the prompt template.
            content: The full template text with optional {variables}.

        WHY: UPSERT simplifies the admin API -- callers don't need to
             check whether a template already exists before saving.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_table(conn)
            await conn.execute(
                """
                INSERT INTO m5_prompts (prompt_id, language, name, content)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(prompt_id, language) DO UPDATE SET
                    name=excluded.name, content=excluded.content
                """,
                (prompt_id, language, name, content),
            )
            await conn.commit()

    async def list_prompts(self) -> list[dict]:
        """
        WHAT: List all stored prompt templates ordered by prompt_id
              and language.

        Returns:
            A list of dicts, each with keys: prompt_id, language, name.
            The content field is excluded to keep the listing lightweight.

        WHY: Admin UIs and debugging tools need to enumerate available
             templates without loading full content.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_table(conn)
            cursor = await conn.execute(
                "SELECT prompt_id, language, name FROM m5_prompts "
                "ORDER BY prompt_id, language"
            )
            return [
                {"prompt_id": r[0], "language": r[1], "name": r[2]}
                async for r in cursor
            ]

    def fill_template(self, template: str, **variables) -> str:
        """
        WHAT: Replace {variable} placeholders in a template string with
              the provided keyword argument values.

        Args:
            template: The template string containing {key} placeholders.
            **variables: Keyword arguments mapping placeholder names to
                         their replacement values.

        Returns:
            The template with all matching placeholders replaced.

        WHY: Prompt templates use variables like {retrieved_context} and
             {graph_context} that are filled at query time with actual
             retrieved data. This is the simplest possible substitution
             mechanism -- str.replace() is sufficient and avoids pulling
             in a template engine dependency.
        """
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result
