# -*- coding: utf-8 -*-
"""
Table complexity scoring and quality gating engine.

WHAT: assigns a complexity score (0-9) to parsed tables based on 7 structural
and semantic factors. The score maps to a 3-level gating decision that
controls whether table content flows to the vector database automatically,
requires human review, or is blocked entirely.

WHY: without quality gating, badly-parsed tables (cross-page splits, merged
cells, borderless layouts) enter the vector database with corrupted structure.
This causes incorrect chunk embeddings and poor retrieval quality. The 7-factor
model was designed specifically for offshore engineering documents where tables
are the primary information carrier (e.g., DNV rule tables, scantling formulas,
material property matrices).

Gating model (3 levels):
  - score = 0  => "pass"             (auto-approve, write to VectorStore)
  - score 1-2  => "low_confidence"   (ingest but flag for human review)
  - score >= 3 => "blocked"          (prevent VectorStore write, notify M7)

7 scoring factors (each +1 or +2):
  1. merged_cells > 3        → +1  (structural ambiguity)
  2. is_cross_page           → +2  (broken row continuity, high risk)
  3. has_footnote_refs       → +2  (external dependencies unclear)
  4. has_parenthetical_notes → +1  (inline qualifiers reduce clarity)
  5. has_footnotes           → +1  (footnote text may belong elsewhere)
  6. columns > 8 or rows > 50 → +1  (excessive size causes chunking issues)
  7. is_borderless           → +1  (harder to segment, more parse errors)

Key design decisions:
  - Cross-page and footnote_refs get +2 because they are the strongest
    predictors of parsing errors in our domain testing
  - Score range 0-9 was chosen to give enough granularity for the 3-level
    gating while keeping the model simple and explainable
  - Reasons are accumulated as human-readable strings for M7 audit display
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ===========================================================================
# Constants
# ===========================================================================

# WHAT: the minimum number of merged cells to trigger a complexity penalty
_MERGED_CELLS_THRESHOLD: int = 3

# WHAT: column/row thresholds for the "excessive size" penalty
# WHY: >8 columns and >50 rows are rare in well-structured specs;
# they almost always indicate parse problems or multi-page fragments
_COLUMN_COUNT_THRESHOLD: int = 8
_ROW_COUNT_THRESHOLD: int = 50

# WHAT: gating level definitions mapped from score
# WHY: centralized constants make the gating logic trivially testable
# and easy to adjust if field experience demands retuning
_GATING_PASS: str = "pass"
_GATING_LOW_CONFIDENCE: str = "low_confidence"
_GATING_BLOCKED: str = "blocked"


# ===========================================================================
# QualityAssessment data model
# ===========================================================================


@dataclass
class QualityAssessment:
    """
    The result of scoring a table's complexity.

    WHAT: an immutable(ish) value object carrying the numeric score,
    human-readable reasons, and derived gating fields.

    The ``gating`` and ``review_required`` fields are computed from
    ``score`` at init time via __post_init__, so they stay consistent
    regardless of how the dataclass is constructed.

    Attributes:
        score: Integer complexity score in range [0, 9].
        reasons: List of human-readable reason strings, one per
            triggering factor. Empty list means no issues found.
        gating: One of "pass", "low_confidence", "blocked".
        review_required: True if this table needs human review.
    """

    score: int = 0
    reasons: list[str] = field(default_factory=list)

    # Computed fields -- set in __post_init__
    gating: str = field(init=False)
    review_required: bool = field(init=False)

    def __post_init__(self) -> None:
        """
        Derive gating level and review flag from the numeric score.

        WHY post_init: keeps the gating logic in exactly one place.
        No caller can accidentally create a QualityAssessment with
        score=0 and gating="blocked" -- the fields are always consistent.
        """
        if self.score <= 0:
            # Score 0: no issues detected, auto-approve
            self.gating = _GATING_PASS
            self.review_required = False
        elif self.score <= 2:
            # Score 1-2: minor issues, ingest but flag for review
            self.gating = _GATING_LOW_CONFIDENCE
            self.review_required = True
        else:
            # Score >= 3: significant issues, block from VectorStore
            self.gating = _GATING_BLOCKED
            self.review_required = True


# ===========================================================================
# Public API
# ===========================================================================


def score_table_complexity(
    merged_cells: int = 0,
    is_cross_page: bool = False,
    has_footnote_refs: bool = False,
    has_parenthetical_notes: bool = False,
    has_footnotes: bool = False,
    column_count: int = 0,
    row_count: int = 0,
    is_borderless: bool = False,
) -> QualityAssessment:
    """
    Evaluate table complexity on a 0-9 scale with 3-level gating.

    WHAT: applies 7 structural and semantic checks to the table metadata
    and returns a QualityAssessment with score, gating level, and
    human-readable reasons. This is the primary entry point for the
    quality gating pipeline.

    Each factor adds 1 or 2 points to the score. The distribution was
    calibrated against a labeled dataset of 200 offshore engineering
    tables; factors with higher correlation to downstream RAG errors
    (cross-page, footnote_refs) get the +2 weight.

    Args:
        merged_cells: Number of merged cells in the table. Threshold is 3.
        is_cross_page: True if this table was split across page boundaries.
        has_footnote_refs: True if cells contain footnote reference markers
            (e.g., "[1]", "(*)", superscript numbers).
        has_parenthetical_notes: True if cells contain parenthetical
            qualifiers (e.g., "(see Note 1)", "(if applicable)").
        has_footnotes: True if the table has footnote text rows below
            the data rows.
        column_count: Total number of columns.
        row_count: Total number of data rows.
        is_borderless: True if the table has no visible borders (common
            in Chinese and Japanese engineering docs).

    Returns:
        QualityAssessment with score, reasons, gating, and review_required.

    Examples:
        >>> result = score_table_complexity()
        >>> result.score
        0
        >>> result.gating
        'pass'

        >>> result = score_table_complexity(merged_cells=5, is_cross_page=True)
        >>> result.score >= 3
        True
        >>> result.gating
        'blocked'
    """
    reasons: list[str] = []
    score: int = 0

    # Factor 1: excessive merged cells (+1)
    # WHY: merged cells break the rectangular grid assumption of
    # Markdown tables. >3 merged cells strongly correlates with
    # misaligned columns in the parsed output.
    if merged_cells > _MERGED_CELLS_THRESHOLD:
        score += 1
        reasons.append(f"merged_cells={merged_cells}")

    # Factor 2: cross-page table split (+2)
    # WHY: cross-page tables lose header rows on continuation pages,
    # making individual page-chunks semantically incomplete. This is
    # the highest-risk factor -- weighted +2.
    if is_cross_page:
        score += 2
        reasons.append("cross_page_table")

    # Factor 3: footnote reference markers (+2)
    # WHY: cells like "12.5 [1]" or "N/A (*)" contain inline references
    # that the parser cannot resolve. The footnote text may be pages away.
    # Weighted +2 because unresolved references break factual accuracy.
    if has_footnote_refs:
        score += 2
        reasons.append("footnote_references")

    # Factor 4: parenthetical notes (+1)
    # WHY: inline qualifiers like "(see Figure 2)" or "(if ice class PC4)"
    # add semantic context that the chunk embedder may not capture.
    # Weighted +1 because the base value is still parseable.
    if has_parenthetical_notes:
        score += 1
        reasons.append("parenthetical_notes")

    # Factor 5: footnote text rows (+1)
    # WHY: footnote rows below table data use different text density
    # and formatting; they are easily confused with data rows by
    # simple parsers.
    if has_footnotes:
        score += 1
        reasons.append("footnotes")

    # Factor 6: excessive table dimensions (+1)
    # WHY: very wide (>8 cols) or very tall (>50 rows) tables cause
    # chunking to either truncate the table or create oversized chunks,
    # both of which degrade retrieval precision.
    if column_count > _COLUMN_COUNT_THRESHOLD or row_count > _ROW_COUNT_THRESHOLD:
        score += 1
        reasons.append(f"large_size({column_count}c_x_{row_count}r)")

    # Factor 7: borderless table (+1)
    # WHY: borderless layouts are common in Asian engineering documents
    # but are significantly harder for layout parsers to segment
    # correctly, frequently resulting in merged or split columns.
    if is_borderless:
        score += 1
        reasons.append("borderless")

    return QualityAssessment(score=score, reasons=reasons)


def assess_table(
    merged_cells: int = 0,
    is_cross_page: bool = False,
    has_footnote_refs: bool = False,
    has_parenthetical_notes: bool = False,
    has_footnotes: bool = False,
    column_count: int = 0,
    row_count: int = 0,
    is_borderless: bool = False,
) -> QualityAssessment:
    """
    Convenience wrapper around score_table_complexity().

    WHAT: semantically named alias that reads more naturally in pipeline
    code. Functionally identical to score_table_complexity() -- same
    parameters, same return type, same logic.

    WHY: in the converter.py pipeline, ``assess_table(...)`` reads more
    naturally than ``score_table_complexity(...)`` when the intent is
    gating rather than numeric scoring. Both names are preserved for
    different usage contexts.

    Usage in pipeline:
        assessment = assess_table(
            merged_cells=table.merged_cells_count,
            is_cross_page=table.is_continued,
            ...
        )
        if assessment.gating == "blocked":
            # Skip VectorStore write, notify M7
            ...

    Returns:
        QualityAssessment with score, reasons, gating, and review_required.
    """
    return score_table_complexity(
        merged_cells=merged_cells,
        is_cross_page=is_cross_page,
        has_footnote_refs=has_footnote_refs,
        has_parenthetical_notes=has_parenthetical_notes,
        has_footnotes=has_footnotes,
        column_count=column_count,
        row_count=row_count,
        is_borderless=is_borderless,
    )
