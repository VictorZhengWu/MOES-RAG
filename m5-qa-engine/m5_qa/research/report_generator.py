"""Report Generator — produces the final 7-section Deep Research report.

WHAT: Takes the original query, all retrieval results, and the analysis
      output, and generates a structured Markdown report via LLM. Falls
      back to a template-based report if LLM is unavailable.

WHY: The report is the primary deliverable of Deep Research. It must be
     structured, citation-backed, and readable by both engineers and
     non-technical stakeholders. The 7-section template ensures consistency
     across all research topics.

SECTIONS:
    §1 Executive Summary — 1-page overview
    §2 Comparison Matrix — multi-society regulation comparison table
    §3 Technical Recommendations — recommended/alternative/discouraged
    §4 Inspection Checklist — design/construction/operation checkpoints
    §5 Risk Matrix — risk item | probability | consequence | mitigation
    §6 Reference Trace — each conclusion linked to source clauses
    §7 Limitations — AI uncertainty + areas needing human review
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

REPORT_TEMPLATE = """# Deep Research Report

## §1 Executive Summary

[1-page summary of the research question, methodology, and key findings]

## §2 Regulation Comparison Matrix

| Requirement | {societies} |
|-------------|{separators}|
| [parameter] | [values] |

## §3 Technical Recommendations

### Recommended Approach
### Alternative Approaches
### Approaches Not Recommended

## §4 Inspection Checklist

### Design Phase
- [ ]
### Construction Phase
- [ ]
### Operation Phase
- [ ]

## §5 Risk Matrix

| Risk Item | Probability | Consequence | Mitigation |
|-----------|------------|-------------|------------|
| | | | |

## §6 Reference Trace

- [1] [Society] [Clause] ([Year])
- [2] ...

## §7 Limitations and Open Questions

-
"""


async def generate_report(
    query: str,
    regulation_results: list[dict],
    web_results: list[dict],
    analysis,
    llm_client=None,
) -> str:
    """Generate the full 7-section Deep Research report.

    Args:
        query: Original user question.
        regulation_results: Output from Agent_Regulations.
        web_results: Output from Agent_Web.
        analysis: AnalysisResult from analyzer.analyze() (may be None).
        llm_client: Optional M5 LLMClient. Falls back to template if None.

    Returns:
        Markdown string of the complete report.
    """
    # Build conflict summary for prompt
    conflicts_text = "No conflicts detected."
    confidence = "medium"
    if analysis:
        if analysis.conflicts:
            conflicts_text = "\n".join(
                f"- {c.get('parameter', '?')}: {c.get('society_a', '?')}={c.get('value_a', '?')} "
                f"vs {c.get('society_b', '?')}={c.get('value_b', '?')} "
                f"({c.get('difference_pct', '?')}% difference)"
                for c in analysis.conflicts[:5]
            )
        confidence = getattr(analysis, 'confidence', 'medium')
        if hasattr(confidence, 'real'):  # float check
            confidence = "high" if confidence >= 0.8 else "medium"

    # Try LLM report generation
    if llm_client:
        try:
            prompt = _build_report_prompt(query, regulation_results, web_results, conflicts_text)
            response = await llm_client.complete(
                [{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=3000,
            )
            content = response["choices"][0]["message"]["content"]
            if content and len(content.strip()) > 200:
                return content.strip()
        except Exception as e:
            logger.warning("LLM report generation failed: %s", e)

    # Fallback: template-based report
    return _build_fallback_report(query, regulation_results, web_results, conflicts_text, confidence)


def _build_report_prompt(
    query: str,
    regulation_results: list[dict],
    web_results: list[dict],
    conflicts_text: str,
) -> str:
    """Build the prompt for LLM report generation."""
    reg_text = "\n\n".join(
        f"[{r.get('source', '?')}] {r.get('text', '')[:300]}"
        for r in regulation_results[:8]
    ) or "No regulation results found."

    web_text = "\n\n".join(
        f"[{r.get('source', '?')}] {r.get('title', '')}: {r.get('snippet', '')[:200]}"
        for r in web_results[:3]
    ) or "No web results found."

    return f"""Generate a professional Deep Research report for a marine engineering query.

Query: {query}

Regulation Findings:
{reg_text}

Web Search Findings:
{web_text}

Detected Cross-Society Conflicts:
{conflicts_text}

Report Structure (exactly 7 sections, Markdown format):

# Deep Research Report: [Topic]

## 1. Executive Summary
[3-5 sentences covering: what was researched, key findings, confidence level (see analysis above)]

## 2. Regulation Comparison Matrix
[Table with columns: Requirement | Society1 | Society2 | Society3 | Notes]
[Use numerical values from the regulation findings above]

## 3. Technical Recommendations
- **Recommended**: [primary recommendation based on latest/most conservative regulation]
- **Alternative**: [viable alternative if cost/availability constraints exist]
- **Not Recommended**: [approaches that don't meet requirements]

## 4. Inspection Checklist
- **Design Phase**: [2-3 verification items]
- **Construction Phase**: [2-3 inspection items]
- **Operation Phase**: [2-3 monitoring items]

## 5. Risk Matrix
| Risk Item | Probability | Consequence | Mitigation |
|-----------|------------|-------------|------------|
[2-4 risk items based on findings]

## 6. Reference Trace
[List each cited regulation with full clause reference: [N] Society Part.Chapter.§Section (Year)]
[Include URL for web sources]

## 7. Limitations and Open Questions
[2-3 items the AI is uncertain about, recommend human verification]

Markdown only. No preamble, no closing remarks."""


def _build_fallback_report(
    query: str,
    regulation_results: list[dict],
    web_results: list[dict],
    conflicts_text: str,
    confidence: str,
) -> str:
    """Build a template-based report when LLM is unavailable.

    WHY fallback: Deep Research must always produce something useful,
         even if the LLM backend is down. The template report provides
         all retrieved facts in a structured format so the user can
         make their own analysis.
    """
    reg_items = "\n".join(
        f"- [{r.get('source', '?')}] {r.get('text', '')[:300]}"
        for r in regulation_results[:10]
    ) or "- No regulation results available."

    web_items = "\n".join(
        f"- [{r.get('title', 'N/A')}]({r.get('url', '#')}) — {r.get('snippet', '')[:200]}"
        for r in web_results[:5]
    ) or "- No web results available."

    return f"""# Deep Research Report: {query[:120]}

> **Confidence**: {confidence} (auto-generated — LLM unavailable, showing raw findings)

---

## 1. Regulation Findings

{reg_items}

---

## 2. Web Search Results

{web_items}

---

## 3. Cross-Society Conflicts

{conflicts_text}

---

## 4. Reference Sources

Count: {len(regulation_results)} regulation excerpts, {len(web_results)} web results.

---
*This report was auto-generated without LLM assistance. Raw findings are shown above.*
"""
