"""
M5 QA Engine — Self-RAG Pipeline (Enterprise Tier).

WHAT: Implements an iterative retrieval pipeline that evaluates retrieval
      quality via M3 chunk scores and re-queries with synonym expansion
      when scores are insufficient. Designed for Enterprise-tier users
      with 16K context windows.

WHY: Enterprise users need the highest answer quality. Self-RAG adds a
     quality feedback loop: if the best retrieved chunks have low confidence
     scores, the query is expanded with domain synonyms and re-retrieved.
     This increases the chance of finding relevant documents for obscure
     or poorly-phrased queries.

     Phase 1 simplified version: uses M3 retrieval scores directly as the
     quality signal — no separate evaluator LLM or citation verifier.

Pipeline flow:
  1. Retrieve (M3+M4 parallel)
  2. Check best chunk score >= threshold
     -> YES: break, use this context
     -> NO:  expand query with synonyms, re-retrieve (up to max_iterations)
  3. Use best retrieval result (highest score across all iterations)
  4. Token budget + context fusion + prompt + LLM + citations

Synonym dictionary: Domain-specific term expansion for marine/offshore
engineering queries. Covers common terminology variations found in
classification society regulations.
"""

# Domain-specific synonym dictionary for marine/offshore engineering.
# WHAT: Maps canonical terms to their common variations found in regulations.
# WHY: Different classification societies (DNV, ABS, CCS, etc.) use slightly
#      different terminology for the same concepts. Synonym expansion helps
#      bridge these terminology gaps during retrieval.
SYNONYMS = {
    "welding": ["weld", "fusion", "joining"],
    "preheat": ["pre-heat", "heating"],
    "thickness": ["plate thickness", "material thickness"],
    "requirement": ["criteria", "specification", "standard"],
}

from m5_qa.context.citation_builder import build_citations, attach_citations
from m5_qa.context.fusion import fuse_context
from m5_qa.context.token_budget import allocate_budget


async def execute_self_rag(
    query: str,
    llm_client,           # LLMClient instance
    retriever,            # RetrievalClient instance
    prompt_manager,       # PromptManager instance
    tier: str = "enterprise",
    kg_depth: int = 5,
    max_iterations: int = 3,
    score_threshold: float = 0.5,
) -> dict:
    """
    WHAT: Execute the Self-RAG pipeline with iterative retrieval and quality
          checking via M3 chunk scores.

    WHY: Enterprise users demand the highest answer accuracy. Self-RAG adds
         a retrieval quality feedback loop: if the best chunks have low
         confidence, the query is expanded with synonyms and re-retrieved.
         Phase 1 uses M3 scores directly — no separate evaluator LLM.

    Args:
        query: The user's natural language question.
        llm_client: An LLMClient instance for generation.
        retriever: A RetrievalClient instance for M3+M4 retrieval.
        prompt_manager: A PromptManager instance for prompt templates.
        tier: User tier string. Defaults to "enterprise".
        kg_depth: Depth for M4 graph BFS traversal. Defaults to 5.
        max_iterations: Maximum retrieval/rewrite cycles. Defaults to 3.
        score_threshold: Minimum M3 chunk score to stop iterating. Defaults to 0.5.

    Returns:
        dict with keys:
          - "answer" (str): The LLM-generated answer.
          - "citations" (list[Citation]): Citations referenced in the answer.
          - "iterations" (int): Number of retrieval iterations executed.
          - "best_score" (float): Highest chunk score across all iterations.
    """
    best_ctx = None
    best_score = 0.0
    current_query = query

    # Iterative retrieval loop: expand and re-retrieve until either
    # the score threshold is met or max_iterations is exhausted.
    for iteration in range(max_iterations):
        # Step 1: Retrieve from M3+M4 in parallel
        ctx = await retriever.parallel_retrieve(current_query, kg_depth=kg_depth)

        # Step 2: Evaluate quality using the best M3 chunk score.
        # This is the Phase 1 simplified approach — a dedicated evaluator
        # LLM and citation verifier will be added in Phase 2/3.
        top_score = max((c.score for c in ctx.chunks), default=0.0)
        if top_score > best_score:
            best_score = top_score
            best_ctx = ctx

        # Step 3: If score is sufficient, stop iterating.
        # No need for further query expansion — the retrieval is good enough.
        if top_score >= score_threshold:
            break

        # Step 4: Expand query with synonyms for the next iteration.
        # This broadens the search to catch alternative terminology used
        # by different classification societies or document sources.
        current_query = _expand_query(current_query, iteration)

    # Use the best retrieval result found across all iterations.
    # Even if we never hit the threshold, the highest-scoring context
    # is better than nothing.
    ctx = best_ctx

    # --- Token budget and context fusion (same as pipeline mode) ---
    budget = allocate_budget(tier, current_query)
    context_text = fuse_context(ctx, budget.retrieval_limit)

    # --- Graph formatting ---
    if ctx.graph is not None and ctx.graph.entities:
        graph_text = "\n".join(
            f"- {e.name} ({e.entity_type})"
            for e in ctx.graph.entities[:20]
        )
    else:
        graph_text = "(no graph insights)"

    # --- Prompt building ---
    system_template = await prompt_manager.get_prompt("system_en", "en")
    system_prompt = prompt_manager.fill_template(
        system_template,
        retrieved_context=context_text,
        graph_context=graph_text,
    )

    # --- LLM generation ---
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]
    response = await llm_client.complete(messages)
    answer = response["choices"][0]["message"]["content"]

    # --- Citations ---
    citations = build_citations(ctx.chunks)
    used_citations = attach_citations(answer, citations)

    return {
        "answer": answer,
        "citations": used_citations,
        "iterations": iteration + 1,
        "best_score": best_score,
    }


def _expand_query(query: str, iteration: int) -> str:
    """
    WHAT: Expand a query by appending the Nth synonym for each matched
          canonical term in the SYNONYMS dictionary.

    WHY: When initial retrieval fails to find high-quality matches, query
         expansion broadens the search to cover alternative terminology.
         The iteration index selects which synonym to use for each term,
         ensuring each re-retrieval uses a different expansion.

         This is a simple, deterministic approach — no LLM-based query
         rewriting, no embeddings. It covers the most common terminology
         variations in marine/offshore engineering regulations (e.g.,
         "preheat" vs "pre-heat", "welding" vs "fusion joining").

    Args:
        query: The original query string to expand.
        iteration: The current Self-RAG iteration index (0-based). Used to
                   select which synonym to append for each matched term.

    Returns:
        The expanded query string with synonyms appended. If no known terms
        are found in the query, returns the original query unchanged.
    """
    expanded = query
    for base, synonyms in SYNONYMS.items():
        if base in query.lower() and iteration < len(synonyms):
            # Append the synonym as an additional search term.
            # We keep the original query intact and add the synonym
            # — this way the retriever sees both the original intent
            # and the alternative phrasing.
            expanded += f" {synonyms[iteration]}"
    return expanded
