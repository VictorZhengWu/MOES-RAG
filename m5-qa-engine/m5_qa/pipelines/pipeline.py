"""
M5 QA Engine — Pipeline RAG (Pro Tier).

WHAT: Implements the full-featured RAG pipeline with parallel M3+M4 retrieval,
      context fusion, token-budgeted prompt building, LLM generation, and
      citation building with attachment filtering.

WHY: Pro-tier users have 8K context windows and access to the knowledge graph
     (M4). Running M3 and M4 in parallel reduces latency, and the fused context
     provides richer answers. Citations are attached to filter only the sources
     actually referenced in the LLM's answer.

Pipeline flow:
  1. Parallel retrieval (M3 + M4 via asyncio.gather)
  2. Token budget allocation (allocate_budget)
  3. Context fusion (fuse_context) + graph-as-text formatting
  4. Prompt building (get_prompt + fill_template)
  5. LLM generation (LLMClient.complete)
  6. Citation building (build_citations + attach_citations)
"""

from m5_qa.context.citation_builder import build_citations, attach_citations
from m5_qa.context.fusion import fuse_context
from m5_qa.context.token_budget import allocate_budget


async def execute_pipeline(
    query: str,
    llm_client,           # LLMClient instance
    retriever,            # RetrievalClient instance
    prompt_manager,       # PromptManager instance
    tier: str = "pro",
    kg_depth: int = 3,
) -> dict:
    """
    WHAT: Execute the full RAG pipeline with parallel M3+M4 retrieval.

    WHY: Pro-tier users expect richer, graph-enhanced answers. Running M3
         and M4 in parallel via asyncio.gather cuts latency to the max of
         the two calls rather than their sum, while the fused context
         gives the LLM both semantic matches and structural relationships.

    Args:
        query: The user's natural language question.
        llm_client: An LLMClient instance for LLM generation.
        retriever: A RetrievalClient instance supporting parallel_retrieve.
        prompt_manager: A PromptManager instance for prompt templates.
        tier: User tier string ("basic", "pro", "enterprise"). Defaults to "pro".
        kg_depth: Depth for M4 knowledge graph BFS traversal. Defaults to 3.

    Returns:
        dict with keys:
          - "answer" (str): The LLM-generated answer text.
          - "citations" (list[Citation]): Only citations actually referenced
            in the answer (via [1], [2] markers).
    """
    # Step 1: Parallel retrieval from M3 (semantic) and M4 (knowledge graph).
    # asyncio.gather is handled inside parallel_retrieve for encapsulated
    # error handling — if M4 fails, M3 results are still returned.
    ctx = await retriever.parallel_retrieve(query, kg_depth=kg_depth)

    # Step 2: Allocate token budget based on user tier and query length.
    budget = allocate_budget(tier, query)
    context_text = fuse_context(ctx, budget.retrieval_limit)

    # Step 3: Format graph entities as human-readable text for the prompt.
    # If M4 returned no graph data (unavailable or empty), provide a clear
    # placeholder so the LLM knows it should not fabricate relationships.
    if ctx.graph is not None and ctx.graph.entities:
        graph_text = "\n".join(
            f"- {e.name} ({e.entity_type})"
            for e in ctx.graph.entities[:20]
        )
    else:
        graph_text = "(no graph insights)"

    # Step 4: Build the system prompt with both retrieved context and
    # knowledge graph data.
    system_template = await prompt_manager.get_prompt("system_en", "en")
    system_prompt = prompt_manager.fill_template(
        system_template,
        retrieved_context=context_text,
        graph_context=graph_text,
    )

    # Step 5: Generate the answer via LLM.
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]
    response = await llm_client.complete(messages)
    answer = response["choices"][0]["message"]["content"]

    # Step 6: Build citations from retrieved chunks, then filter to only
    # those actually referenced in the answer via [1], [2] markers.
    # This prevents the UI from showing unused sources.
    citations = build_citations(ctx.chunks)
    used_citations = attach_citations(answer, citations)

    return {"answer": answer, "citations": used_citations}
