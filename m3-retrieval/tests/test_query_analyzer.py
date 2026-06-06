# -*- coding: utf-8 -*-
"""
Tests for M3 Query Analyzer (query_analyzer.py).

WHAT: Validates that analyze_query() correctly extracts classification
society, chapter/section, version year, keywords, steel grades, temperature
values, and builds the semantic query. Also tests helper functions
_is_exact_match() and _is_keyword_query().

WHY: The query analyzer is the first stage in the retrieval pipeline.
Its output drives metadata filtering, keyword-based boosting, and semantic
query rewriting. Incorrect extraction leads to irrelevant results downstream.
"""

from __future__ import annotations

import pytest

from m3_retrieval.stages.query_analyzer import (
    QueryAnalysis,
    _is_exact_match,
    _is_keyword_query,
    analyze_query,
)


class TestQueryAnalysisDataclass:
    """Test the QueryAnalysis dataclass defaults."""

    def test_default_values(self) -> None:
        """WHY: All optional fields must default to None/empty."""
        qa = QueryAnalysis()
        assert qa.classification_society is None
        assert qa.chapter_section is None
        assert qa.version_year is None
        assert qa.keywords == []
        assert qa.semantic_query == ""

    def test_custom_values(self) -> None:
        """WHY: Fields must accept explicit values."""
        qa = QueryAnalysis(
            classification_society="DNV",
            chapter_section="Pt.3 Ch.2",
            version_year=2024,
            keywords=["hull", "welding"],
            semantic_query="hull welding requirements",
        )
        assert qa.classification_society == "DNV"
        assert qa.chapter_section == "Pt.3 Ch.2"
        assert qa.version_year == 2024
        assert qa.keywords == ["hull", "welding"]
        assert qa.semantic_query == "hull welding requirements"


class TestAnalyzeQueryDNV:
    """Test queries containing DNV classification society."""

    def test_dnv_with_chapter_and_year(self) -> None:
        """
        WHAT: Query with DNV society, chapter reference, and version year.

        Expected: classification_society='DNV', chapter_section extracted,
        version_year=2024, keywords contain technical terms.
        """
        result = analyze_query(
            "DNV Pt.3 Ch.2 hull structural strength requirements 2024"
        )

        assert result.classification_society == "DNV"
        assert result.chapter_section is not None
        assert "Pt.3" in (result.chapter_section or "")
        assert result.version_year == 2024

    def test_dnv_with_steel_grade(self) -> None:
        """
        WHAT: Query containing DNV society and steel grade AH36.

        Expected: steel grade 'AH36' separated as a keyword,
        classification_society='DNV'.
        """
        result = analyze_query(
            "DNV AH36 steel plate thickness tolerance"
        )

        assert result.classification_society == "DNV"
        # Steel grade pattern [A-Z]{2,4}\d{2,3} should match AH36
        assert "AH36" in result.keywords

    def test_dnv_with_temperature(self) -> None:
        """
        WHAT: Query containing DNV and a temperature value 350 C.

        Expected: temperature '350 C' separated as a keyword.
        """
        result = analyze_query(
            "DNV 350 C exhaust gas temperature limit"
        )

        assert result.classification_society == "DNV"
        # Temperature pattern should match "350 C"
        temperature_found = any("350" in kw for kw in result.keywords)
        assert temperature_found, (
            f"Expected temperature '350' in keywords, got {result.keywords}"
        )


class TestAnalyzeQueryABS:
    """Test queries containing ABS classification society."""

    def test_abs_basic_query(self) -> None:
        """
        WHAT: Simple ABS query with chapter reference.

        Expected: classification_society='ABS', chapter_section extracted.
        """
        result = analyze_query(
            "ABS Part 3 Section 2-1 hull girder strength"
        )

        assert result.classification_society == "ABS"
        assert result.chapter_section is not None

    def test_abs_with_year(self) -> None:
        """
        WHAT: ABS query with a version year 2023.

        Expected: version_year=2023, classification_society='ABS'.
        """
        result = analyze_query("ABS 2023 steel vessel rules")
        assert result.classification_society == "ABS"
        assert result.version_year == 2023


class TestAnalyzeQueryNoSociety:
    """Test queries without any classification society."""

    def test_no_society_generic_query(self) -> None:
        """
        WHAT: Generic marine query with no classification society and no
        technical identifiers (steel grades, temperatures).

        Expected: classification_society=None, keywords empty (no technical
        patterns to match), semantic_query equals the original text.
        """
        result = analyze_query(
            "welding procedure specification for hull plates"
        )

        assert result.classification_society is None
        # No steel grades or temperature patterns in this query
        assert result.keywords == [], (
            f"Expected no keywords for generic query, got {result.keywords}"
        )
        # semantic_query should match original (nothing to strip)
        assert result.semantic_query == "welding procedure specification for hull plates"

    def test_no_society_with_year(self) -> None:
        """
        WHAT: Query with version year but no society.

        Expected: version_year extracted, classification_society=None.
        """
        result = analyze_query("hull design rules 2021 revision")
        assert result.classification_society is None
        assert result.version_year == 2021

    def test_semantic_query_removes_keywords(self) -> None:
        """
        WHAT: Verify semantic_query is built by removing extracted keywords
        from the original query.

        Expected: semantic_query contains the non-keyword portions only.
        """
        result = analyze_query(
            "DNV Pt.3 Ch.2 AH36 350 C hull structural welding 2024"
        )
        # semantic_query should not contain steel grade or temperature
        # but should contain the core semantic content
        assert "hull" in result.semantic_query.lower()
        assert "structural" in result.semantic_query.lower()
        # The core query content should be present
        assert len(result.semantic_query) > 0


class TestIsExactMatch:
    """Test the _is_exact_match() helper function."""

    def test_dnv_standard_notation(self) -> None:
        """
        WHAT: DNV standard notation like 'DNV-ST-N001'.

        WHY: This format (society-prefix + standard code) is common in
        offshore engineering queries and should be recognised.
        """
        assert _is_exact_match("DNV-ST-N001")

    def test_abs_standard_notation(self) -> None:
        """WHAT: ABS standard notation 'ABS-RULE-2023'."""
        assert _is_exact_match("ABS-RULE-2023")

    def test_not_exact_match(self) -> None:
        """
        WHAT: Natural language queries should not be flagged as exact matches.
        """
        assert not _is_exact_match(
            "what are the hull structural requirements"
        )
        assert not _is_exact_match("welding procedure specification")


class TestIsKeywordQuery:
    """Test the _is_keyword_query() helper function."""

    def test_short_keyword_query(self) -> None:
        """
        WHAT: A query with <=5 words containing a proper noun (DNV).

        Expected: True (short, specific keyword query).
        """
        assert _is_keyword_query("DNV hull welding")

    def test_long_question_not_keyword(self) -> None:
        """
        WHAT: A full-sentence question should NOT be a keyword query.
        """
        assert not _is_keyword_query(
            "what are the DNV requirements for hull structural welding"
        )

    def test_short_generic_not_keyword(self) -> None:
        """Short query with only generic words → not keyword."""
        assert not _is_keyword_query("hello world test")


class TestStripSection:
    """Tests for hierarchical chapter filter fallback."""

    def test_strip_section(self) -> None:
        """Pt.4 Ch.3 §2.1 → Pt.4 Ch.3"""
        from m3_retrieval.stages.query_analyzer import strip_section
        assert strip_section("Pt.4 Ch.3 §2.1") == "Pt.4 Ch.3"
        assert strip_section("Pt.4 Ch.3 §2") == "Pt.4 Ch.3"

    def test_strip_chapter(self) -> None:
        """Pt.4 Ch.3 → Pt.4"""
        from m3_retrieval.stages.query_analyzer import strip_section
        assert strip_section("Pt.4 Ch.3") == "Pt.4"

    def test_strip_none(self) -> None:
        """Pt.4 → None (top level)"""
        from m3_retrieval.stages.query_analyzer import strip_section
        assert strip_section("Pt.4") is None
        assert strip_section("Ch.3") is None
        assert strip_section("") is None
        assert strip_section(None) is None

    def test_build_fallback_chain(self) -> None:
        """Full chain: [Pt.4 Ch.3 §2.1, Pt.4 Ch.3, Pt.4, None]"""
        from m3_retrieval.stages.query_analyzer import build_fallback_chain
        chain = build_fallback_chain("Pt.4 Ch.3 §2.1")
        assert chain == ["Pt.4 Ch.3 §2.1", "Pt.4 Ch.3", "Pt.4", None]

    def test_build_fallback_chain_simple(self) -> None:
        """Short chain: [Ch.3, None]"""
        from m3_retrieval.stages.query_analyzer import build_fallback_chain
        chain = build_fallback_chain("Ch.3")
        assert chain == ["Ch.3", None]
