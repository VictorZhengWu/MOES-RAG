"""
M5 QA Engine — Simple RAG Pipeline (Basic Tier).

WHAT: Implements the simplest RAG pipeline: M3 semantic retrieval only,
      token-budgeted context, prompt filling, LLM generation, and citation
      building. Designed for Basic-tier users with 4K context windows.

WHY: Basic-tier users have the smallest context window (4K tokens) and are
     unlikely to have M4 knowledge graph access. This pipeline keeps things
     fast and lean: one retrieval call, no graph traversal, no citation
     attachment filtering (citations are built but not attached for Basic
     tier — they are still returned for optional display).

Pipeline flow:
  1. M3 retrieval (simple_retrieve)
  2. Token budget allocation (allocate_budget)
  3. Context fusion (fuse_context)
  4. Prompt building (get_prompt + fill_template)
  5. LLM generation (LLMClient.complete)
  6. Citation building (build_citations)
"""

from m5_qa.context.citation_builder import build_citations
from m5_qa.context.fusion import fuse_context
from m5_qa.context.token_budget import allocate_budget


async def execute_simple(
    query: str,
    llm_client,           # LLMClient instance
    retriever,            # RetrievalClient instance
    prompt_manager,       # PromptManager instance
    tier: str = "basic",
) -> dict:
    """
    WHAT: Execute the simple RAG pipeline — M3 retrieval only, then context
          formatting, prompt building, LLM generation, and citation building.

    WHY: This is the entry point for Basic-tier users who need fast answers
         with minimal latency and context overhead. It uses only M3 semantic
         search (no knowledge graph) and keeps the context within 4K tokens.

    Args:
        query: The user's natural language question.
        llm_client: An LLMClient instance for LLM generation.
        retriever: A RetrievalClient instance for M3/M4 retrieval.
        prompt_manager: A PromptManager instance for prompt templates.
        tier: User tier string ("basic", "pro", "enterprise"). Defaults to "basic".

    Returns:
        dict with keys:
          - "answer" (str): The LLM-generated answer text.
          - "citations" (list[Citation]): Source citations for traceability.
    """
    # Step 1: Retrieve context from M3 semantic search only.
    # M4 graph traversal is skipped for simple mode — Basic tier users
    # have limited context windows and graph data would add overhead.
    ctx = await retriever.simple_retrieve(query)

    # Step 2: Allocate token budget based on user tier and query length.
    # The retrieval_limit determines how many chunks can fit in the prompt.
    budget = allocate_budget(tier, query)
    context_text = fuse_context(ctx, budget.retrieval_limit)

    # Step 3: Build the system prompt by fetching the template and filling
    # in the retrieved context. Graph context is explicitly marked as not
    # available — the LLM should not fabricate graph-based relationships.
    system_template = await prompt_manager.get_prompt("system_en", "en")
    system_prompt = prompt_manager.fill_template(
        system_template,
        retrieved_context=context_text,
        graph_context="(not available in simple mode)",
    )

    # Step 4: Generate the answer via LLM.
    # Messages follow the standard chat format: system prompt first,
    # then the user's query.
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]
    response = await llm_client.complete(messages)
    answer = response["choices"][0]["message"]["content"]

    # Step 5: Build citations from the retrieved chunks for traceability.
    # Citations are returned even in simple mode so the frontend can
    # optionally display source references.
    citations = build_citations(ctx.chunks)

    return {"answer": answer, "citations": citations}
