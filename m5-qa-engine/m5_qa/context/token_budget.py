"""
M5 QA Engine — Token Budget Manager.

WHAT: Defines TokenBudget for allocating context window tokens across
      retrieval, history, and generation stages. Provides tier-based
      allocation with dynamic query-length adjustment.

WHY: Context window is a scarce resource — especially for Basic tier users
     with 4K limits. Proper budgeting prevents one stage (e.g., retrieval)
     from starving another (e.g., generation), ensuring balanced answer quality
     across all tiers (Basic 4K, Pro 8K, Enterprise 16K).
"""

from dataclasses import dataclass


@dataclass
class TokenBudget:
    """
    WHAT: Token allocation across RAG pipeline stages.

    WHY: The RAG pipeline has three main token-consuming stages:
         1. Retrieval: chunks fed into the prompt as context
         2. History: prior conversation messages
         3. Generation: the LLM's response
         Each stage has a proportional share of the total context window.

    Attributes:
        total: Total context window size in tokens (e.g., 4000, 8000, 16000).
        retrieval_ratio: Fraction of total tokens allocated to retrieved context.
        history_ratio: Fraction of total tokens allocated to conversation history.
        generation_ratio: Fraction of total tokens allocated to LLM generation.
    """
    total: int              # Total context window size (e.g., 4000, 8000, 16000)
    retrieval_ratio: float  # Fraction for retrieved chunks (e.g., 0.30)
    history_ratio: float    # Fraction for conversation history (e.g., 0.20)
    generation_ratio: float # Fraction for LLM output (e.g., 0.50)

    @property
    def retrieval_limit(self) -> int:
        """
        WHAT: Maximum tokens for retrieved context chunks.
        WHY: Caps how much retrieved text is fed into the prompt
             to leave room for history and generation.
        """
        return int(self.total * self.retrieval_ratio)

    @property
    def history_limit(self) -> int:
        """
        WHAT: Maximum tokens for conversation history.
        WHY: Ensures history does not consume all available context,
             leaving space for retrieval and the current response.
        """
        return int(self.total * self.history_ratio)

    @property
    def generation_limit(self) -> int:
        """
        WHAT: Maximum tokens for the LLM's generated response.
        WHY: The generation budget should be large enough for substantial
             answers but bounded to stay within the total context window.
        """
        return int(self.total * self.generation_ratio)


def estimate_tokens(text: str) -> int:
    """
    WHAT: Rough token count estimation: 1 token ≈ 4 characters for English text.

    WHY: Accurate token counting requires the model's tokenizer, which may
         not be available (especially for local models via Ollama). This
         heuristic is sufficient for budget planning purposes.

    Args:
        text: The input text string to estimate tokens for.

    Returns:
        Estimated token count (minimum 1, to avoid division-by-zero).
    """
    return max(1, len(text) // 4)


def allocate_budget(tier: str, query: str = "") -> TokenBudget:
    """
    WHAT: Allocate token budget based on user tier with optional query-length factor.

    WHY: Different tiers have different context window sizes. Additionally,
         longer queries contain more search terms and benefit from larger
         retrieval budgets (up to 1.5x the base ratio), while shorter queries
         need less retrieval context and can allocate more to generation.

    Tier budgets:
        basic:      4000 total (30% retrieval, 20% history, 50% generation)
        pro:        8000 total (40% retrieval, 20% history, 40% generation)
        enterprise: 16000 total (50% retrieval, 20% history, 30% generation)

    Query-length factor:
        factor = clamp(query_len / 500, 0.5, 1.5)
        Longer queries → more retrieval budget
        Shorter queries → more generation budget

    Args:
        tier: User tier string ("basic", "pro", "enterprise").
        query: The user's query string for dynamic adjustment. Default empty.

    Returns:
        A TokenBudget with tier-appropriate and query-adjusted ratios.
    """
    # Base budgets per tier
    budgets = {
        "basic":      TokenBudget(4000,  0.30, 0.20, 0.50),
        "pro":        TokenBudget(8000,  0.40, 0.20, 0.40),
        "enterprise": TokenBudget(16000, 0.50, 0.20, 0.30),
    }
    budget = budgets.get(tier, budgets["basic"])

    # Skip dynamic adjustment when no query is provided
    # When query is empty, return base budget without adjustment
    if not query:
        return budget

    # Dynamic adjustment based on query length
    # factor ranges from 0.5 (very short query) to 1.5 (very long query)
    query_factor = max(0.5, min(len(query) / 500, 1.5))

    # Adjust retrieval ratio by query factor
    base_ret = budget.retrieval_ratio
    adjusted_ret = base_ret * query_factor

    # Recalculate generation ratio to keep total consistent:
    # total = retrieval + history + generation
    # generation = total - (retrieval) - (history)
    adjusted_gen = budget.total - int(budget.total * adjusted_ret) - budget.history_limit

    return TokenBudget(
        total=budget.total,
        retrieval_ratio=adjusted_ret,
        history_ratio=budget.history_ratio,
        generation_ratio=max(0.1, adjusted_gen / budget.total),
    )
