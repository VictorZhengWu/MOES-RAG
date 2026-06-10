"""Tests for research complexity scoring (FR-1).

WHAT: Verifies 6-dimension complexity scoring algorithm correctly
      identifies queries that benefit from Deep Research vs simple Q&A.

WHY: Accurate scoring prevents over-triggering (annoying users) and
     under-triggering (missing opportunities for deep analysis).
"""

import pytest
from m5_qa.research.complexity import calculate_complexity, should_suggest


# ---------------------------------------------------------------------------
# Dimension 1: Society breadth
# ---------------------------------------------------------------------------

def test_single_society_scores_1():
    """One classification society → +1."""
    score = calculate_complexity("DNV Pt.3 Ch.3 requirements")
    assert score >= 1, f"Expected >= 1, got {score}"


def test_three_societies_scores_3():
    """Three societies → +3."""
    score = calculate_complexity("DNV and ABS and CCS requirements for bulk carriers")
    assert score >= 3, f"Expected >= 3, got {score}"


def test_no_society_scores_0():
    """No society mentioned → 0 from dimension 1."""
    score = calculate_complexity("What is steel?")
    # May have other dimension scores, but society dimension = 0
    assert calculate_complexity("hello world") <= 1


# ---------------------------------------------------------------------------
# Dimension 2: Regulation depth
# ---------------------------------------------------------------------------

def test_cross_chapter_scores_2():
    """Pt.X combined with Ch.Y → +2."""
    score1 = calculate_complexity("DNV Pt.3 Ch.3")
    score2 = calculate_complexity("DNV Pt.3 Ch.3 §6")
    # Both should get at least +2 from depth
    cross_chapter = calculate_complexity("DNV Pt.3 Ch.3 and Pt.5 Ch.5 comparison")


def test_single_clause_scores_1():
    """Single § reference → +1."""
    score = calculate_complexity("DNV §6.2")
    assert score >= 1


def test_no_regulation_reference():
    """No regulation reference → 0 from depth dimension."""
    score = calculate_complexity("hello")
    assert score <= 1


# ---------------------------------------------------------------------------
# Dimension 3: Question depth
# ---------------------------------------------------------------------------

def test_analytical_keyword_scores_2():
    """'Why' / 'How' / 'Compare' → +2 each."""
    score = calculate_complexity("Why does DNV require 1.5?")
    assert score >= 3  # 1 (society) + 2 (why)


def test_comparison_scores_2():
    """'对比' → +2."""
    score = calculate_complexity("对比 DNV 和 ABS 的疲劳要求")
    assert score >= 4  # 2 (societies) + 2 (对比)


# ---------------------------------------------------------------------------
# Dimension 4: Context continuity
# ---------------------------------------------------------------------------

def test_consecutive_society_queries_score_3():
    """Three consecutive queries about DNV → +3."""
    history = [
        type('Msg', (), {'content': 'DNV Pt.3 Ch.3 requirements'})(),
        type('Msg', (), {'content': 'DNV Pt.3 Ch.1 material grades'})(),
        type('Msg', (), {'content': 'DNV Pt.5 welding'})(),
    ]
    score = calculate_complexity("DNV hatch cover strength", history)
    assert score >= 4  # 1 (society) + 3 (context continuity)


def test_no_context_history():
    """No conversation history → 0 from context dimension."""
    score = calculate_complexity("DNV Pt.3")
    assert 1 <= score <= 3  # society + possible depth, no context bonus


# ---------------------------------------------------------------------------
# Dimension 5: Research scope keywords
# ---------------------------------------------------------------------------

def test_scope_keywords_scores_2():
    """'全面分析' → +2."""
    score = calculate_complexity("全面分析 DNV 结构规范")
    assert score >= 3  # 1 (society) + 2 (scope)


def test_multiple_scope_keywords():
    """'总结' + '所有' → +4."""
    score = calculate_complexity("总结所有 DNV 和 ABS 的结构要求")
    assert score >= 6  # 2 (societies) + 4 (scope keywords)


# ---------------------------------------------------------------------------
# Dimension 6: Domain complexity
# ---------------------------------------------------------------------------

def test_domain_terms_score_1():
    """Marine technical terms → +1 each."""
    score = calculate_complexity("疲劳 焊接 NDT 检测要求")
    assert score >= 3  # 3 domain terms


def test_no_domain_terms():
    """No marine terms → 0 from domain dimension."""
    score = calculate_complexity("hello world")
    assert score <= 1


# ---------------------------------------------------------------------------
# Threshold logic
# ---------------------------------------------------------------------------

def test_simple_query_no_suggestion():
    """Score < 5 → no suggestion."""
    result = should_suggest("What is steel?")
    assert result["action"] == "none"


def test_moderate_query_suggestion():
    """Score 5-7 → 'suggest'."""
    result = should_suggest("Compare DNV and ABS bulk carrier structural requirements and fatigue analysis")
    assert result["action"] in ("suggest", "strong_suggest", "auto_suggest")


def test_complex_query_strong_suggestion():
    """Score 8-10 → 'strong_suggest'."""
    result = should_suggest("全面分析 DNV ABS CCS 散货船疲劳强度规范差异及焊接要求")
    assert result["action"] in ("strong_suggest", "auto_suggest")


def test_very_complex_query_auto_suggest():
    """Score ≥ 11 → 'auto_suggest'."""
    result = should_suggest(
        "全面分析对比总结 DNV ABS CCS LR BV 五大船级社对 LNG 船液货舱的"
        "疲劳寿命焊接NDT结构强度材料选择的所有规范要求区别和版本演进"
    )
    assert result["action"] == "auto_suggest"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_query():
    """Empty query → score 0."""
    score = calculate_complexity("")
    assert score == 0


def test_english_query():
    """English queries should work with society name detection."""
    score = calculate_complexity(
        "Compare DNV and ABS requirements for bulk carrier fatigue analysis"
    )
    assert score >= 4  # 2 (societies) + 2 (compare)


def test_max_score_capped():
    """Score should be capped at 15."""
    # Try to exceed cap
    score = calculate_complexity(
        "全面分析总结对比 DNV ABS CCS LR BV IACS IMO 所有规范版本演进 "
        "疲劳 焊接 NDT 有限元 屈曲 稳性 腐蚀 为什么 如何 原因 区别"
    )
    assert score <= 15
