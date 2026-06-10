"""Research complexity scoring — determines if a query needs Deep Research.

WHAT: 6-dimension scoring algorithm that evaluates whether a user query
      would benefit from multi-agent deep research vs simple Q&A.

WHY: Prevents over-triggering (annoying users with suggestions for simple
     queries) and under-triggering (missing complex queries that need
     multi-regulation cross-referencing).

DIMENSIONS:
    1. Society breadth — how many classification societies are involved
    2. Regulation depth — cross-chapter vs single-clause references
    3. Question depth — analytical question words (why, how, compare)
    4. Context continuity — consecutive queries about the same society
    5. Research scope — keywords signalling comprehensive analysis
    6. Domain complexity — marine-specific technical terms
"""

import re
from typing import Optional


# Known classification societies (case-insensitive matching)
SOCIETIES = [
    "DNV", "ABS", "CCS", "LR", "BV", "RINA", "NK", "KR", "IACS", "IMO",
]

# Analytical question keywords — each adds 2 points
DEEP_QUESTION_WORDS_CN = ["为什么", "如何", "原因", "区别", "对比", "分析"]
DEEP_QUESTION_WORDS_EN = ["why", "how", "cause", "difference", "compare", "analysis"]

# Research scope keywords — each adds 2 points
SCOPE_KEYWORDS_CN = ["全面分析", "总结", "所有", "完整", "系统", "综述"]
SCOPE_KEYWORDS_EN = [
    "comprehensive", "summary", "all", "complete", "systematic", "overview",
]

# Marine domain technical terms — each adds 1 point
DOMAIN_TERMS_CN = ["疲劳", "焊接", "NDT", "有限元", "屈曲", "稳性", "腐蚀"]
DOMAIN_TERMS_EN = [
    "fatigue", "welding", "ndt", "finite element", "buckling",
    "stability", "corrosion",
]


def calculate_complexity(
    query: str,
    conversation_history: Optional[list] = None,
) -> int:
    """Score a query's complexity from 0-15 across 6 dimensions.

    Args:
        query: The user's question text.
        conversation_history: Optional list of previous messages for
                              context continuity scoring. Each message
                              should have a .content string attribute.

    Returns:
        Integer score from 0 to 15 (capped).
    """
    score = 0
    query_lower = query.lower()

    # Dimension 1: Society breadth (+1 per unique society)
    found_societies = {s for s in SOCIETIES if s.lower() in query_lower}
    score += len(found_societies)

    # Dimension 2: Regulation depth
    # Cross Part+Chapter: "Pt.X ... Ch.Y" → +2
    if re.search(r"Pt\.\s*\d+.*Ch\.\s*\d+", query, re.IGNORECASE):
        score += 2
    # Single clause: "Pt.X", "Ch.X", or "§X" → +1
    elif re.search(r"(?:Pt\.|Ch\.|§)\s*\d", query, re.IGNORECASE):
        score += 1

    # Dimension 3: Question depth (+2 per analytical keyword)
    for word in DEEP_QUESTION_WORDS_CN:
        if word in query:
            score += 2
    for word in DEEP_QUESTION_WORDS_EN:
        if re.search(rf"\b{word}\b", query_lower):
            score += 2

    # Dimension 4: Context continuity (+3 if last 3 messages all
    #              reference at least one classification society)
    if conversation_history and len(conversation_history) >= 3:
        last_3 = conversation_history[-3:]
        all_have_society = all(
            any(s.lower() in getattr(m, 'content', '').lower()
                for s in SOCIETIES)
            for m in last_3
        )
        if all_have_society:
            score += 3

    # Dimension 5: Research scope keywords (+2 each)
    for word in SCOPE_KEYWORDS_CN:
        if word in query:
            score += 2
    for word in SCOPE_KEYWORDS_EN:
        if re.search(rf"\b{word}\b", query_lower):
            score += 2

    # Dimension 6: Domain complexity (+1 per marine term)
    for term in DOMAIN_TERMS_CN:
        if term in query:
            score += 1
    for term in DOMAIN_TERMS_EN:
        if re.search(rf"\b{term}\b", query_lower):
            score += 1

    return min(score, 15)


def should_suggest(
    query: str,
    conversation_history: Optional[list] = None,
) -> dict:
    """Determine if Deep Research should be suggested for this query.

    Args:
        query: The user's question text.
        conversation_history: Optional conversation context.

    Returns:
        Dict with keys:
            action: "none" | "suggest" | "strong_suggest" | "auto_suggest"
            score: integer complexity score
            message: human-readable suggestion (if action != "none")
    """
    score = calculate_complexity(query, conversation_history)

    if score >= 11:
        return {
            "action": "auto_suggest",
            "score": score,
            "message": (
                f"This query (complexity {score}/15) involves multiple "
                f"classification societies and requires deep analysis. "
                f"Deep Research is recommended."
            ),
        }
    elif score >= 8:
        return {
            "action": "strong_suggest",
            "score": score,
            "message": (
                f"This query requires cross-referencing ({score}/15). "
                f"Deep Research can provide a structured analysis."
            ),
        }
    elif score >= 5:
        return {
            "action": "suggest",
            "score": score,
            "message": (
                f"Deep Research may help with this query ({score}/15)."
            ),
        }
    else:
        return {"action": "none", "score": score}
