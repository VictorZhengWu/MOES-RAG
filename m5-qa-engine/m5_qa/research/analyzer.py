"""Analysis Agent — cross-referencing and conflict detection.

WHAT: Analyzes retrieved results from regulations and web agents:
      Step 1: Regex-based numerical requirement extraction
      Step 2: LLM-driven conflict detection + version diff + case correlation

WHY: Rule-based extraction provides numerical precision (regex doesn't
     hallucinate numbers), while LLM provides semantic understanding
     (why ABS requires 1.67 vs DNV 1.50 — different design philosophies).

DESIGN: Two-step process.
     Step 1 runs always (zero LLM cost, sub-millisecond).
     Step 2 runs if LLM is available and results contain conflicts.

OUTPUT: AnalysisResult dataclass with conflicts, version_diffs,
        case_correlations, and key_findings.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Multi-language numerical requirement extraction patterns
# Format: (param_group, value) tuples
_REQUIREMENT_PATTERNS = [
    # Chinese: 强度 ≥ 1.5× 载荷, 板厚 ≥ 12mm
    re.compile(
        r"(强度|板厚|系数|间距|温度|压力|速度|厚度|距离|高度)"
        r"\s*[≥≤⩾⩼>=<]+\s*([\d.]+)",
    ),
    # English: strength >= 1.67, thickness minimum 12 mm, factor shall be >= 1.67
    re.compile(
        r"(strength|thickness|factor|spacing|temperature|pressure|velocity"
        r"|distance|height|depth)"
        r".*?(?:>=|≤|>=|<=|minimum|maximum|not less than|not more than)\s*"
        r"([\d.]+)",
        re.IGNORECASE,
    ),
    # DNV-style: not less than 12 mm, minimum 1.5
    re.compile(
        r"(?:not\s+less\s+than|minimum|at\s+least)\s+([\d.]+)\s*"
        r"(mm|MPa|kN|m|cm|°C|deg)?",
        re.IGNORECASE,
    ),
]

# Society name aliases (normalize to standard names)
_SOCIETY_ALIASES = {
    "dnv": "DNV", "abs": "ABS", "ccs": "CCS", "lr": "LR",
    "bv": "BV", "rina": "RINA", "nk": "NK", "kr": "KR",
    "iacs": "IACS", "imo": "IMO",
}


@dataclass
class AnalysisResult:
    """Structured analysis output from the Analysis Agent.

    Attributes:
        conflicts: List of detected conflicts between regulations.
        version_diffs: Differences between regulation versions.
        case_correlations: Relevant real-world cases found.
        key_findings: Top-level conclusions.
        confidence: Overall confidence (0.0-1.0).
    """
    conflicts: list[dict] = field(default_factory=list)
    version_diffs: list[dict] = field(default_factory=list)
    case_correlations: list[dict] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    confidence: float = 0.5


def extract_requirements(chunks: list[dict]) -> dict[str, dict[str, float]]:
    """Extract numerical requirements from chunk text using regex.

    Args:
        chunks: List of dicts with keys: text, metadata (may have 'society')

    Returns:
        Dict mapping parameter name → {society: float_value}
        Example: {"强度系数": {"DNV": 1.5, "ABS": 1.67}}

    WHY regex first: avoids LLM hallucinating wrong numbers. Regex
         extraction is deterministic and sub-millisecond for 50 chunks.
    """
    requirements: dict[str, dict[str, float]] = {}

    for chunk in chunks:
        text = chunk.get("text", "")
        meta = chunk.get("metadata", {}) or {}
        society_raw = meta.get("society", "unknown")
        society = _SOCIETY_ALIASES.get(society_raw.lower(), society_raw)

        for pattern in _REQUIREMENT_PATTERNS:
            for match in pattern.finditer(text):
                groups = match.groups()
                if len(groups) >= 2:
                    param = groups[0].strip().lower() if groups[0] else "unknown"
                    value_str = groups[1]
                elif len(groups) == 1:
                    # DNV "not less than" pattern: only one group
                    param = "requirement"
                    value_str = groups[0]
                else:
                    continue

                try:
                    value = float(value_str)
                except (ValueError, TypeError):
                    continue

                # Normalize parameter name
                param_cn = _normalize_param(param)

                if param_cn not in requirements:
                    requirements[param_cn] = {}
                requirements[param_cn][society] = value

    return requirements


def _normalize_param(param: str) -> str:
    """Normalize parameter names to a common form for comparison."""
    param_lower = param.lower()
    mapping = {
        "strength": "强度", "thickness": "板厚", "factor": "系数",
        "spacing": "间距", "temperature": "温度", "pressure": "压力",
        "velocity": "速度", "distance": "距离", "height": "高度", "深度": "距离",
    }
    return mapping.get(param_lower, param_lower)


def detect_conflicts(requirements: dict[str, dict[str, float]]) -> list[dict]:
    """Detect conflicts between societies for the same parameter.

    A conflict exists when ≥2 societies specify different numerical
    values for the same parameter.

    Args:
        requirements: Output from extract_requirements().

    Returns:
        List of conflict dicts: {parameter, society_a, value_a,
                                 society_b, value_b, difference_pct,
                                 severity}
    """
    conflicts = []

    for param, society_values in requirements.items():
        if len(society_values) < 2:
            continue

        societies = list(society_values.keys())
        # Compare each pair of societies
        for i in range(len(societies)):
            for j in range(i + 1, len(societies)):
                s_a, s_b = societies[i], societies[j]
                try:
                    v_a = float(society_values[s_a])
                    v_b = float(society_values[s_b])
                except (ValueError, TypeError):
                    continue

                if abs(v_a - v_b) < 0.001:
                    continue  # Same value → no conflict

                diff_pct = round(abs(v_a - v_b) / max(v_a, v_b) * 100, 1)
                severity = "warning" if diff_pct >= 10 else "info"

                conflicts.append({
                    "parameter": param,
                    "society_a": s_a,
                    "value_a": v_a,
                    "society_b": s_b,
                    "value_b": v_b,
                    "difference_pct": diff_pct,
                    "severity": severity,
                    "recommendation": (
                        f"{s_b} requires {diff_pct}% {'higher' if v_b > v_a else 'lower'} "
                        f"value for {param}. Use the stricter requirement if dual-class."
                    ),
                })

    return conflicts


async def analyze(
    query: str,
    regulation_results: list[dict],
    web_results: list[dict],
    llm_client=None,
    m4_engine=None,
) -> AnalysisResult:
    """Full analysis pipeline: extract + detect + LLM deep analysis.

    Args:
        query: Original user query.
        regulation_results: Output from Agent_Regulations.
        web_results: Output from Agent_Web.
        llm_client: Optional M5 LLMClient for deep analysis.
        m4_engine: Optional M4 KG engine for cross-reference lookups.

    Returns:
        AnalysisResult with conflicts, findings, and confidence.
    """
    # Step 1: Rule-based extraction (always runs, free)
    all_results = regulation_results + [
        {"text": r.get("snippet", r.get("text", "")),
         "source": "web",
         "metadata": {}}
        for r in web_results
    ]
    requirements = extract_requirements(all_results)
    conflicts = detect_conflicts(requirements)

    result = AnalysisResult(conflicts=conflicts)

    if not conflicts:
        result.key_findings = ["No numerical conflicts detected between regulations."]
        result.confidence = 0.7
        return result

    # Step 2: LLM deep analysis (only if conflicts found + LLM available)
    if llm_client:
        try:
            llm_result = await _llm_deep_analysis(
                query, conflicts, regulation_results[:10], web_results[:5],
                llm_client,
            )
            result.key_findings = llm_result.get("key_findings", result.key_findings)
            result.version_diffs = llm_result.get("version_diffs", [])
            result.case_correlations = llm_result.get("case_correlations", [])
            result.confidence = 0.85
        except Exception as e:
            logger.warning("LLM deep analysis failed: %s", e)
            # Use rule-based key findings as fallback
            result.key_findings = [
                f"Conflict: {c['society_a']} requires {c['value_a']} vs "
                f"{c['society_b']} requires {c['value_b']} "
                f"for {c['parameter']} ({c['difference_pct']}% difference)"
                for c in conflicts[:5]
            ]
    else:
        # No LLM — use rule-based summary
        result.key_findings = [
            f"Conflict: {c['society_a']} requires {c['value_a']} vs "
            f"{c['society_b']} requires {c['value_b']} "
            f"for {c['parameter']} ({c['difference_pct']}% difference)"
            for c in conflicts[:5]
        ]

    # Step 3: M4 KG cross-reference enrichment (best-effort)
    if m4_engine and conflicts:
        try:
            for conflict in conflicts[:2]:  # Only enrich top 2 conflicts
                refs = await m4_engine.cross_reference(
                    source_clause="",
                    source_society=conflict["society_a"],
                    target_society=conflict["society_b"],
                )
                if refs:
                    conflict["kg_cross_refs"] = len(refs)
        except Exception:
            pass

    return result


async def _llm_deep_analysis(
    query: str,
    conflicts: list[dict],
    reg_results: list[dict],
    web_results: list[dict],
    llm_client,
) -> dict:
    """Call LLM for semantic analysis of detected conflicts.

    WHY LLM: Regex can detect that DNV says 1.5 and ABS says 1.67,
         but only LLM can explain WHY — different design philosophies,
         different vessel type assumptions, different safety factors.
    """
    conflicts_text = "\n".join(
        f"- {c['parameter']}: {c['society_a']}={c['value_a']} vs "
        f"{c['society_b']}={c['value_b']} ({c['difference_pct']}% diff)"
        for c in conflicts[:5]
    )

    reg_text = "\n".join(
        f"[{r.get('source', '?')}] {r.get('text', '')[:200]}"
        for r in reg_results[:5]
    )

    web_text = "\n".join(
        f"[web] {r.get('title', '')}: {r.get('snippet', '')[:200]}"
        for r in web_results[:3]
    )

    prompt = f"""You are a marine engineering expert analyzing regulation conflicts.

Original question: {query}

Detected conflicts:
{conflicts_text}

Relevant regulation excerpts:
{reg_text}

Web search results:
{web_text}

Return a JSON object with:
1. "key_findings": list of 3-5 key findings (one sentence each, include numerical values)
2. "version_diffs": list of version differences found (empty if none)
3. "case_correlations": list of real-world cases related to these regulations (empty if none)

JSON only, no explanation."""

    messages = [{"role": "user", "content": prompt}]
    response = await llm_client.complete(
        messages, temperature=0.3, max_tokens=800,
    )

    content = response["choices"][0]["message"]["content"]
    # Extract JSON from response (may be inside ```json fence)
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
    if json_match:
        content = json_match.group(1).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM analysis JSON, using raw text")
        return {"key_findings": [content[:200]], "version_diffs": [], "case_correlations": []}
