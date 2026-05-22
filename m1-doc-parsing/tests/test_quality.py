# -*- coding: utf-8 -*-
"""
Unit tests for quality.py -- table complexity scoring and gating engine.

WHY: The quality gating engine is the final guardian before parsed content
enters the vector database. A wrong gating decision (blocking a simple table
or auto-passing a complex one) directly impacts downstream RAG accuracy.
These tests verify all 3 gating levels: auto-pass (0), low-confidence (1-2),
and blocked (3+).
"""

import pytest

from m1_parser.core.quality import (
    QualityAssessment,
    assess_table,
    score_table_complexity,
)


# ===========================================================================
# Test 1: Simple table auto-pass (score=0)
# ===========================================================================

def test_simple_table_auto_pass():
    """
    A clean, small table with no complexity factors MUST score 0 and auto-pass.

    WHY: Simple tables (no merged cells, no footnotes, small size, bordered)
    should flow through without any human intervention. Blocking them would
    create unnecessary review backlog.
    """
    result = score_table_complexity()
    assert result.score == 0, (
        f"Expected score=0 for default (simple) table, got {result.score}"
    )
    assert result.gating == "pass", (
        f"Expected gating='pass' for score=0, got '{result.gating}'"
    )
    assert result.review_required is False
    assert len(result.reasons) == 0


# ===========================================================================
# Test 2: Merged cells trigger low confidence (score=1-2)
# ===========================================================================

def test_merged_cells_low_confidence():
    """
    A table with 5 merged cells MUST score 1 and flag as low_confidence.

    WHY: Merged cells (>3 threshold) indicate structural complexity that may
    confuse the Markdown table representation. The content should be ingested
    but flagged for human review, not blocked outright.
    """
    result = score_table_complexity(merged_cells=5)
    assert result.score == 1, (
        f"Expected score=1 for merged_cells=5, got {result.score}"
    )
    assert result.gating == "low_confidence", (
        f"Expected gating='low_confidence' for score=1, got '{result.gating}'"
    )
    assert result.review_required is True
    assert any("merged_cells" in r for r in result.reasons), (
        f"Expected 'merged_cells' in review reasons, got {result.reasons}"
    )


# ===========================================================================
# Test 3: Cross-page table blocked (score >= 3)
# ===========================================================================

def test_cross_page_blocked():
    """
    A cross-page table with parenthetical notes MUST score >= 3 and be blocked.

    WHY: Cross-page tables (+2) often have broken row continuity and missing
    header repetition. Combined with parenthetical notes (+1), the score hits
    the blocking threshold (3). Writing such content to VectorStore without
    human review would produce incorrect chunk embeddings.
    """
    result = score_table_complexity(
        is_cross_page=True,
        has_parenthetical_notes=True,
    )
    assert result.score >= 3, (
        f"Expected score>=3 for cross_page + parenthetical, got {result.score}"
    )
    assert result.gating == "blocked", (
        f"Expected gating='blocked' for score>=3, got '{result.gating}'"
    )
    assert result.review_required is True
    assert any("cross_page" in r for r in result.reasons), (
        f"Expected 'cross_page' in review reasons, got {result.reasons}"
    )


# ===========================================================================
# Test 4: Multiple issues compound to blocked (score >= 3)
# ===========================================================================

def test_multiple_issues_blocked():
    """
    Multiple low-severity issues that compound MUST reach the blocking threshold.

    WHY: Individual factors may each add only +1, but the cumulative effect
    (borderless + footnotes + large size + merged cells + parenthetical) can
    reach score=4, triggering a block. This prevents complex but subtly
    problematic tables from slipping through.
    """
    result = score_table_complexity(
        merged_cells=4,          # +1 (exceeds threshold of 3)
        has_footnote_refs=False,
        has_parenthetical_notes=True,  # +1
        has_footnotes=True,      # +1
        column_count=10,         # +1 (exceeds 8 columns)
        row_count=20,            # stays under 50 row threshold
        is_borderless=True,      # +1
        is_cross_page=False,
    )
    assert result.score >= 3, (
        f"Expected score>=3 for multiple issues, got {result.score}"
    )
    assert result.gating == "blocked", (
        f"Expected gating='blocked' for score>=3, got '{result.gating}'"
    )
    assert result.review_required is True
    # Verify that multiple distinct reasons were recorded
    assert len(result.reasons) >= 3, (
        f"Expected at least 3 review reasons, got {len(result.reasons)}"
    )


# ===========================================================================
# Additional edge-case tests
# ===========================================================================

def test_borderless_table_low_confidence():
    """
    A borderless table alone MUST score 1 and flag low_confidence.

    WHY: Borderless tables are hard for parsers to segment correctly.
    A score of 1 correctly reflects "ingest but flag" rather than blocking.
    """
    result = score_table_complexity(is_borderless=True)
    assert result.score == 1
    assert result.gating == "low_confidence"


def test_large_table_low_confidence():
    """
    A table exceeding 50 rows MUST score 1 and flag low_confidence.

    WHY: Very large tables (>50 rows) may contain data-entry artifacts
    or header misalignment. Flagging rather than blocking is appropriate
    because the content is still valuable.
    """
    result = score_table_complexity(row_count=60)
    assert result.score == 1
    assert result.gating == "low_confidence"


def test_footnote_references_block_content():
    """
    Footnote references alone (+2) MUST NOT block -- the gating level
    should be low_confidence for score=2.

    WHY: Footnote references indicate external documentation links, not
    structural table issues. Score=2 is below the blocking threshold of 3.
    """
    result = score_table_complexity(has_footnote_refs=True)
    assert result.score == 2
    assert result.gating == "low_confidence"
    assert result.review_required is True


def test_assess_table_convenience():
    """
    The assess_table() convenience function MUST return the same result
    as calling score_table_complexity() directly with the same kwargs.

    WHY: assess_table() is a thin wrapper for readability in the pipeline.
    It must not alter the scoring logic.
    """
    direct = score_table_complexity(merged_cells=5, is_borderless=True)
    convenience = assess_table(merged_cells=5, is_borderless=True)
    assert convenience.score == direct.score
    assert convenience.gating == direct.gating
    assert convenience.reasons == direct.reasons


def test_mid_range_low_confidence():
    """
    Score=2 cases (cross_page alone or footnote_refs alone) MUST be
    low_confidence, not blocked, since they are at the boundary.

    WHY: Score=2 is the highest non-blocking score. It must correctly
    gate as low_confidence to avoid false blocking of borderline content.
    """
    # Cross-page alone (+2)
    result_cp = score_table_complexity(is_cross_page=True)
    assert result_cp.score == 2
    assert result_cp.gating == "low_confidence"

    # Footnote refs alone (+2)
    result_fr = score_table_complexity(has_footnote_refs=True)
    assert result_fr.score == 2
    assert result_fr.gating == "low_confidence"


# ===========================================================================
# QualityAssessment dataclass contract tests
# ===========================================================================

def test_quality_assessment_defaults():
    """
    A fresh QualityAssessment MUST default to score=0, pass gating,
    and empty reasons list.
    """
    qa = QualityAssessment()
    assert qa.score == 0
    assert qa.gating == "pass"
    assert qa.review_required is False
    assert qa.reasons == []


def test_quality_assessment_field_assignment():
    """
    QualityAssessment fields MUST be directly settable for programmatic use.
    """
    qa = QualityAssessment(
        score=4,
        reasons=["cross_page_table", "borderless", "footnotes"],
    )
    assert qa.score == 4
    assert qa.gating == "blocked"
    assert qa.review_required is True
    assert len(qa.reasons) == 3
