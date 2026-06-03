"""
M5 QA Engine — Context Fusion.

WHAT: Fuses M3 retrieved chunks and M4 knowledge graph data into a single
      formatted context string for the LLM prompt. Respects token budget
      to prevent context window overflow.

WHY: The LLM prompt has a finite context window (4K/8K/16K tokens).
     Retrieved chunks from M3 and graph entities/relations from M4 must
     be merged into a single coherent text block that:
     - Fits within the allocated retrieval token budget
     - Preserves the highest-scoring chunks (first-come, first-serve)
     - Formats graph data as human-readable descriptions
     This module is the last step before the context enters the prompt template.
"""

from __future__ import annotations

from .retriever import RetrievalContext


def estimate_tokens(text: str) -> int:
    """
    WHAT: Rough token count estimation using the 1 token ~ 4 characters heuristic.

    WHY: Accurate token counting requires the model-specific tokenizer, which
         may not be available at runtime (especially for local models via Ollama
         or vLLM). This heuristic is sufficient for budget planning — the goal
         is to prevent severe overflow, not byte-perfect counting.

    Args:
        text: The input text string to estimate tokens for.

    Returns:
        Estimated token count (minimum 1, to avoid division-by-zero).
    """
    return max(1, len(text) // 4)


def fuse_context(
    retrieval_ctx: RetrievalContext, max_retrieval_tokens: int
) -> str:
    """
    WHAT: Merge M3 chunks and M4 graph data into a single context string
          bounded by max_retrieval_tokens.

    WHY: The LLM prompt builder needs a single text block containing all
         retrieved context. This function:
         1. Formats M3 chunks as "[Source X] text" blocks under "Document Context"
         2. Formats M4 entities/relations under "Knowledge Graph"
         3. Truncates chunks to fit within the token budget (chunks are assumed
            to be pre-sorted by relevance score from M3)

    Args:
        retrieval_ctx: The merged retrieval results from RetrievalClient.
        max_retrieval_tokens: Maximum token budget for the retrieval portion
            of the context (from TokenBudget.retrieval_limit).

    Returns:
        A formatted string with document context and/or knowledge graph sections,
        separated by blank lines. Returns empty string if no content.
    """
    parts: list[str] = []
    token_budget = max_retrieval_tokens

    # --- Step 1: Format M3 semantic search chunks ---
    # Chunks are added in order (highest score first) until the token
    # budget is exhausted. Each chunk is prefixed with its citation
    # so the LLM can reference sources in its answer.
    chunk_texts: list[str] = []
    tokens_used = 0
    for sc in retrieval_ctx.chunks:
        # Build the formatted text for this chunk
        formatted = f"[Source {sc.citation}] {sc.chunk.text}"
        t = estimate_tokens(formatted)
        # Stop adding chunks once we exceed the budget
        if tokens_used + t > token_budget:
            break
        chunk_texts.append(formatted)
        tokens_used += t

    if chunk_texts:
        parts.append("## Document Context\n" + "\n\n".join(chunk_texts))

    # --- Step 2: Format M4 knowledge graph ---
    # Graph entities and relations are formatted as bullet-point lists.
    # Limits are applied to prevent the graph section from dominating
    # the context: max 20 entities, max 10 relations.
    if retrieval_ctx.graph and retrieval_ctx.graph.entities:
        # Format entities: "- EntityName (entity_type)"
        entities_desc = "\n".join(
            f"- {e.name} ({e.entity_type})"
            for e in retrieval_ctx.graph.entities[:20]
        )

        # Format relations: "- source_id -> relation_type -> target_id"
        relations_list = retrieval_ctx.graph.relations or []
        relations_desc = "\n".join(
            f"- {r.source_entity_id} -> {r.relation_type} -> {r.target_entity_id}"
            for r in relations_list[:10]
        )

        parts.append("## Knowledge Graph\n### Entities\n" + entities_desc)
        if relations_desc:
            parts.append("### Relations\n" + relations_desc)

    # Join all sections with double newlines for clean prompt formatting
    return "\n\n".join(parts)
