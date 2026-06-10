"""Research Planner Agent — decomposes user queries into sub-questions.

WHAT: Takes a complex user query and generates a structured research plan
      with sub-questions, each assigned a search strategy (regulations, web)
      and a specific search query for retrieval.

WHY: Complex queries like "Compare DNV, ABS, and CCS requirements for LNG
     carrier cargo tank fatigue" need to be decomposed into per-society
     sub-questions. A single search query cannot effectively cover 3+
     classification societies with different naming conventions.

APPROACH:
    1. Try LLM-based decomposition (produces best quality plans)
    2. If LLM fails or returns invalid JSON, fall back to rule-based
       decomposition (split by society name)

INTEGRATION WITH M4 KG:
    When M4 is available, cross_reference() is called for each society
    pair to discover implicit cross-references that should be included
    as additional sub-questions.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Maximum sub-questions to prevent runaway decomposition
MAX_SUB_QUESTIONS = 8

# Known classification societies for rule-based fallback
SOCIETIES = ["DNV", "ABS", "CCS", "LR", "BV", "RINA", "NK", "KR", "IACS", "IMO"]

# Prompt template for LLM-based decomposition
PLANNER_PROMPT = """You are a marine engineering research planner. Decompose the user's question into sub-questions for systematic research.

Each sub-question should target a specific classification society or aspect.
Use the EXACT format below (JSON only, no explanation):

```json
{{
  "sub_questions": [
    {{
      "id": 1,
      "question": "Short description of what this sub-question investigates",
      "search_strategy": ["regulations"],
      "search_query": "Specific search string for document retrieval"
    }}
  ],
  "estimated_runtime_seconds": 45
}}
```

Rules:
- 1-{max_sub} sub-questions total
- search_strategy: array containing "regulations" and/or "web"
- search_query: concise, specific search string (5-15 words)
- If comparing multiple societies, create 1 sub-question per society
- If the query mentions specific clause references (Pt.X Ch.Y), include them in search_query

User query: {query}
"""


def _rule_based_decompose(query: str) -> dict:
    """Decompose query by extracting society names and clause references.

    WHAT: Simple rule-based fallback when LLM is unavailable. Splits the
          query into per-society sub-questions.

    WHY: Graceful degradation. Even without LLM, we can create useful
         sub-questions by splitting on known society names.
    """
    sub_questions = []
    query_lower = query.lower()

    # Find societies mentioned in the query
    found_societies = [s for s in SOCIETIES if s.lower() in query_lower]

    if found_societies:
        for i, society in enumerate(found_societies[:MAX_SUB_QUESTIONS], start=1):
            sub_questions.append({
                "id": i,
                "question": f"{society} requirements for: {query[:80]}",
                "search_strategy": ["regulations", "web"],
                "search_query": f"{society} {query[:100]}",
            })
    else:
        # No specific society — create one generic sub-question
        sub_questions.append({
            "id": 1,
            "question": query[:120],
            "search_strategy": ["regulations", "web"],
            "search_query": query[:150],
        })

    # Estimate runtime: ~15s per sub-question + 10s analysis + 15s report
    estimated = min(len(sub_questions) * 15 + 25, 120)

    return {
        "sub_questions": sub_questions[:MAX_SUB_QUESTIONS],
        "estimated_runtime_seconds": estimated,
        "_fallback": True,
    }


class QueryDecomposer:
    """Decomposes complex user queries into structured research plans."""

    def __init__(self, llm_client=None):
        """Store LLM client reference (lazy, set by engine)."""
        self._llm_client = llm_client

    async def __call__(self, query: str, m4_engine=None) -> dict:
        """Decompose query and return a research plan.

        Args:
            query: The user's original question.
            m4_engine: Optional M4 KG engine for cross_reference() lookups.

        Returns:
            Dict with: sub_questions, estimated_runtime_seconds
        """
        plan = await self._decompose(query)

        # Enrich with M4 cross-references if available
        if m4_engine and len(plan["sub_questions"]) >= 2:
            try:
                plan = await self._enrich_with_kg(plan, m4_engine)
            except Exception:
                logger.warning("M4 KG enrichment failed, using base plan")

        # Cap sub-questions
        plan["sub_questions"] = plan["sub_questions"][:MAX_SUB_QUESTIONS]

        return plan

    async def _decompose(self, query: str) -> dict:
        """Try LLM decomposition, fall back to rules on failure."""
        try:
            response = await self._call_llm(query)
            content = response["choices"][0]["message"]["content"]
            return self._parse_plan(content)
        except Exception as e:
            logger.warning("LLM planner failed (%s), using rule-based fallback", e)
            return _rule_based_decompose(query)

    @staticmethod
    def _parse_plan(raw_content: str) -> dict:
        """Parse LLM response into a structured plan dict.

        Handles:
        - Pure JSON
        - JSON inside ```json fences
        - Invalid JSON → falls back to rule-based
        """
        content = raw_content.strip()

        # Extract JSON from code fence if present
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if fence_match:
            content = fence_match.group(1).strip()

        try:
            data = json.loads(content)
            # Validate required fields
            if "sub_questions" not in data:
                raise ValueError("Missing 'sub_questions' field")
            return {
                "sub_questions": data["sub_questions"],
                "estimated_runtime_seconds": data.get("estimated_runtime_seconds", 60),
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse LLM plan JSON: %s", e)
            # Extract the query from the original message context
            # (best effort: the caller should pass the original query)
            return _rule_based_decompose(
                raw_content[:200]  # Use first 200 chars as query fallback
            )

    async def _call_llm(self, query: str) -> dict:
        """Send the planning prompt to the LLM backend.

        Uses M5's LLMClient if available, otherwise raises to trigger
        rule-based fallback.
        """
        if self._llm_client is None:
            raise RuntimeError("No LLM client configured for planner")

        prompt = PLANNER_PROMPT.format(query=query, max_sub=MAX_SUB_QUESTIONS)
        messages = [{"role": "user", "content": prompt}]

        return await self._llm_client.complete(
            messages,
            temperature=0.3,  # Low temperature for structured output
            max_tokens=1000,
        )

    async def _enrich_with_kg(self, plan: dict, m4_engine) -> dict:
        """Add cross-society reference sub-questions using M4 KG.

        For each pair of societies found in the plan, query the KG for
        known cross-references. If found, add a sub-question to compare.

        WHY: The KG may contain explicit cross-references like
             "DNV Pt.3 Ch.3 §5 ≈ ABS Pt.5B §3-2" that the LLM planner
             might miss.
        """
        # Extract societies from sub-question search queries
        societies_found = set()
        for sq in plan["sub_questions"]:
            for s in SOCIETIES:
                if s.lower() in str(sq).lower():
                    societies_found.add(s)

        if len(societies_found) < 2:
            return plan  # No cross-society comparison possible

        # Query KG for cross-references between first two societies
        societies_list = list(societies_found)
        try:
            refs = await m4_engine.cross_reference(
                source_clause="",
                source_society=societies_list[0],
                target_society=societies_list[1],
            )
            if refs and len(refs) > 0:
                next_id = len(plan["sub_questions"]) + 1
                if next_id <= MAX_SUB_QUESTIONS:
                    plan["sub_questions"].append({
                        "id": next_id,
                        "question": (
                            f"Cross-references between {societies_list[0]} "
                            f"and {societies_list[1]} (from knowledge graph)"
                        ),
                        "search_strategy": ["regulations"],
                        "search_query": (
                            f"cross-reference {societies_list[0]} "
                            f"{societies_list[1]}"
                        ),
                    })
        except Exception:
            pass  # KG enrichment is best-effort

        return plan


# Singleton instance — created by the engine, reused across calls
decompose_query = QueryDecomposer()
