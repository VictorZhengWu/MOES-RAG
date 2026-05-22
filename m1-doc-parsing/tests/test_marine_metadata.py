# -*- coding: utf-8 -*-
"""
Unit tests for marine_metadata.py -- automatic metadata extraction from
offshore engineering documents.

WHY: Offshore documents (rules, certificates, specifications) embed domain-
specific metadata in unstructured text. Manual extraction is error-prone and
slow. The MarineMetadata extractor automates recognition of classification
societies, regulation names, version years, chapter/section references, and
document language -- the 5 fields that downstream M3 retrieval and M5 QA
modules depend on for filtering and routing.

Test coverage:
  - classification_society: 10 member societies + IMO/IACS + aliases + false positives
  - regulation_name: filename-based and formula-based name generation
  - version_year: 19xx/20xx years, multiple years, no year
  - chapter_section: Pt./Ch. format, Part/Section format, CJK, Chapter, paragraph sign
  - language: English, Chinese, Korean, Japanese, Norwegian
  - full extraction: combined all-fields extraction on realistic document text
  - default values: empty text produces sensible defaults
"""

import pytest

from m1_parser.enrichments.marine_metadata import (
    MarineMetadata,
    extract_classification_society,
    extract_regulation_name,
    extract_version_year,
    extract_chapter_section,
    extract_language,
    extract_marine_metadata,
)


# ===========================================================================
# 1. classification_society -- parametrized per-society tests
# ===========================================================================

_SOCIETY_CASES = [
    # (text, expected_abbreviation)
    # DNV -- the dominant society in offshore
    ("This document is issued by DNV for offshore structures.", "DNV"),
    ("DNV rules for classification of ships", "DNV"),
    # ABS
    ("ABS rules for building and classing mobile offshore units", "ABS"),
    ("Per ABS steel vessel rules 2024", "ABS"),
    # CCS (China Classification Society)
    ("CCS guidelines for offshore platforms in South China Sea", "CCS"),
    ("符合 CCS 规范要求的海洋平台设计", "CCS"),
    # LR (Lloyd's Register -- full name alias)
    ("Lloyd's Register rules for naval ships", "LR"),
    ("LR classification notes for fatigue analysis", "LR"),
    # BV (Bureau Veritas)
    ("Bureau Veritas marine & offshore rules", "BV"),
    ("BV NR 445 rules for offshore units", "BV"),
    # NK (Nippon Kaiji Kyokai / ClassNK)
    ("Nippon Kaiji Kyokai rules for container carriers", "NK"),
    ("NK guidelines for ship structural strength", "NK"),
    # RINA
    ("RINA rules for pleasure yachts", "RINA"),
    ("Registro Italiano Navale classification for cargo ships", "RINA"),
    # KR (Korean Register)
    ("KR rules for steel barges", "KR"),
    ("Korean Register of shipping guidance notes", "KR"),
    # IMO -- international regulatory body
    ("IMO resolution MSC.267(85) adoption of the FTP code", "IMO"),
    ("IMO MARPOL Annex VI regulation 13", "IMO"),
    # IACS -- industry umbrella association
    ("IACS unified requirements UR W33 for welding", "IACS"),
    ("IACS common structural rules for bulk carriers", "IACS"),
]


@pytest.mark.parametrize("text,expected", _SOCIETY_CASES)
def test_extract_classification_society(text, expected):
    """
    WHAT: extract_classification_society() must recognise each registered
    society's abbreviation, and also handle common long-form aliases
    (e.g. "Lloyd's Register" -> "LR", "Bureau Veritas" -> "BV",
    "Registro Italiano Navale" -> "RINA", "Korean Register" -> "KR").

    WHY: Downstream modules (M3, M5) need the standard abbreviation for
    filtering and faceted search, not the varied long-form names found
    in raw documents.
    """
    assert extract_classification_society(text) == expected


def test_extract_classification_society_no_match():
    """
    WHAT: extract_classification_society() MUST return "Unknown" when no
    registered society is found in the text.

    WHY: A silent None return would cause NullPointer-style errors in
    downstream pipelines. "Unknown" is an explicit sentinel value.
    """
    result = extract_classification_society(
        "This is a general engineering textbook about fluid dynamics."
    )
    assert result == "Unknown"


def test_extract_classification_society_false_positive_guard():
    """
    WHAT: extract_classification_society() MUST NOT match short abbreviations
    that appear as part of common English words (e.g. "abs" in "absolute").

    WHY: \b word-boundary anchors prevent substring false positives, but
    we must also ensure the extracted token is truly a standalone society
    reference and not a coincidental substring.
    """
    result = extract_classification_society(
        "The absolute pressure measurement system uses precision sensors."
    )
    assert result == "Unknown"


# ===========================================================================
# 2. regulation_name -- filename + formula extraction
# ===========================================================================

def test_extract_regulation_name_from_filename():
    """
    WHAT: extract_regulation_name() MUST derive a human-readable name from
    the source filename when available.

    WHY: The filename is often the most reliable metadata because it is
    assigned by the original author, not inferred from text.
    """
    name = extract_regulation_name(
        text="DNV-ST-N001 rules for offshore structures.",
        filename="/documents/DNV-ST-N001_2024.pdf",
    )
    assert "DNV-ST-N001" in name


def test_extract_regulation_name_from_formula_in_text():
    """
    WHAT: When no filename is provided, extract_regulation_name() MUST fall
    back to extracting the most prominent regulation identifier from the
    document text (e.g. the first line or title).

    WHY: Standalone documents may lack filename context (e.g. when parsed
    from a byte stream). The text-based fallback ensures we always have a
    meaningful name for the document.
    """
    name = extract_regulation_name(
        text="ABS Rules for Building and Classing Mobile Offshore Drilling Units 2024",
        filename=None,
    )
    # Should extract a meaningful portion of the text as the name
    assert len(name) > 5
    assert "ABS" in name or "Rules" in name


# ===========================================================================
# 3. version_year -- parametrized year extraction
# ===========================================================================

_YEAR_CASES = [
    # 20xx years (modern)
    ("DNV-ST-N001 Edition 2024", "2024"),
    ("ABS MODU Rules 2023 update", "2023"),
    ("CCS offshore guidelines 2019", "2019"),
    # 19xx years (legacy)
    ("IMO Resolution A.749(18) 1997", "1997"),
    ("LR rules 1994 edition", "1994"),
    # No year
    ("General engineering principles and design philosophy", None),
    # Future-proof: reject 18xx/21xx not matching 19xx/20xx
    ("Historical document from 1895", None),
]


@pytest.mark.parametrize("text,expected", _YEAR_CASES)
def test_extract_version_year(text, expected):
    """
    WHAT: extract_version_year() MUST extract 4-digit years in the range
    19xx-20xx using the regex pattern (20\\d{2}|19\\d{2}).

    WHY: Offshore rules are versioned by year (e.g. "DNV-ST-N001 2024").
    Years outside 19xx/20xx are excluded because they are likely noise
    (e.g. measurement values, random numbers).
    """
    assert extract_version_year(text) == expected


def test_extract_version_year_first_when_multiple():
    """
    WHAT: When multiple year-like patterns exist, extract_version_year() MUST
    return the first one (leftmost match in the text).

    WHY: The first year reference usually denotes the primary publication or
    revision date. Later years in citations or references are secondary.
    """
    result = extract_version_year("First published 2020, revised 2023, amended 2025")
    assert result == "2020"


# ===========================================================================
# 4. chapter_section -- parametrized structural reference tests
# ===========================================================================

_CHAPTER_CASES = [
    # Pt./Ch. format (DNV / IACS conventions)
    ("Pt.3 Ch.2 Fatigue and Fracture", "Pt.3 Ch.2"),
    ("See Pt.4 Ch.3 Sec.5 for details", "Pt.4 Ch.3"),
    # Part / Section format (ABS / LR conventions)
    ("Part 3 Section 2-1 Hull Structures", "Part 3 Section 2-1"),
    ("Refer to Part 5A Section 3-2 for mooring", "Part 5A Section 3-2"),
    # Chinese chapter references
    ("第 3 章 船体结构设计", "第 3 章"),
    ("按照第12章的要求", "第12章"),
    # English Chapter format
    ("Chapter 5 Structural Analysis", "Chapter 5"),
    ("as described in Chapter 10", "Chapter 10"),
    # Paragraph sign (legal/regulatory conventions)
    ("§ 3.1 General provisions", "§ 3.1"),
    ("The requirements of § 2.4 apply", "§ 2.4"),
    # No match
    ("General introduction to marine engineering", None),
]


@pytest.mark.parametrize("text,expected", _CHAPTER_CASES)
def test_extract_chapter_section(text, expected):
    """
    WHAT: extract_chapter_section() MUST recognise 5 structural reference
    conventions used in offshore documents:

      1. Pt./Ch. format      (DNV, IACS)
      2. Part X Section Y-Z  (ABS, LR)
      3. Chinese "第 X 章"   (CCS, Chinese documents)
      4. English "Chapter X" (generic English)
      5. Paragraph sign §    (legal/regulatory annexes)

    WHY: The chapter/section reference is the primary structural metadata
    for navigating a regulation document. It is the key index that downstream
    retrieval (M3) uses for section-level search and citation linking.
    """
    assert extract_chapter_section(text) == expected


# ===========================================================================
# 5. language -- langdetect-based extraction
# ===========================================================================

_LANG_CASES = [
    # English -- the primary language of international offshore rules
    (
        "These rules for classification of ships apply to all newbuildings.",
        "en",
    ),
    # Chinese -- CCS and Chinese shipyard documents
    (
        "本规范适用于船长不小于90米的钢质海船的结构设计。",
        "zh-cn",
    ),
    # Korean -- KR and Korean shipyard documents
    (
        "이 규정은 선박의 구조 강도 평가에 적용된다.",
        "ko",
    ),
    # Japanese -- NK and Japanese shipyard documents
    (
        "この規則は船舶の構造設計に適用される。",
        "ja",
    ),
    # Norwegian -- DNV origin, Nordic owner documents
    (
        "Disse reglene gjelder for klassifisering av skip og flyttbare innretninger.",
        "no",
    ),
]


@pytest.mark.parametrize("text,expected", _LANG_CASES)
def test_extract_language_parametrized(text, expected):
    """
    WHAT: extract_language() MUST use langdetect to classify the primary
    language of the document text.

    WHY: The Marine & Offshore Expert System supports 5 languages (en, zh-cn,
    ko, ja, no). Language metadata is required for:
      - Routing queries to the correct-language QA model
      - Filtering search results by language preference
      - Selecting the right i18n resource bundle for UI display
    """
    assert extract_language(text) == expected


def test_extract_language_short_text_fallback():
    """
    WHAT: extract_language() MUST return "unknown" when the input text has
    no recognisable linguistic features (e.g. empty string).

    WHY: langdetect raises LangDetectException on text with no features.
    We must handle this gracefully rather than propagating the exception up
    to the caller. "unknown" is the explicit sentinel for unclassifiable text.
    """
    result = extract_language("")
    assert result == "unknown"


# ===========================================================================
# 6. Full extraction -- realistic offshore document text
# ===========================================================================

_REALISTIC_DNV_TEXT = (
    "DNV-ST-N001\n"
    "Maritime Operations\n"
    "Edition 2024\n\n"
    "Pt.3 Ch.2 Fatigue and Fracture Assessment\n\n"
    "This standard provides requirements for planning and execution of "
    "marine operations, including lifting, towing, and installation of "
    "offshore structures. The requirements in this standard are based on "
    "the principles of limit state design and risk-based methodology."
)

_REALISTIC_ABS_TEXT = (
    "ABS Rules for Building and Classing\n"
    "Mobile Offshore Drilling Units 2023\n\n"
    "Part 3 Section 2-1 Hull Structures and Arrangements\n\n"
    "These Rules apply to self-elevating drilling units, column-stabilized "
    "drilling units, and surface-type drilling units of the general design."
)


def test_extract_marine_metadata_dnv():
    """
    WHAT: extract_marine_metadata() MUST correctly extract all 5 metadata
    fields from a realistic DNV offshore standard document.

    WHY: This is the integration / full-extraction test. If individual
    extractors work but their combination breaks (e.g. due to mutual
    interference), this test catches it.
    """
    meta = extract_marine_metadata(
        text=_REALISTIC_DNV_TEXT,
        filename="/docs/DNV-ST-N001_2024.pdf",
    )
    assert meta.classification_society == "DNV"
    assert "DNV-ST-N001" in meta.regulation_name
    assert meta.version_year == "2024"
    assert meta.chapter_section == "Pt.3 Ch.2"
    assert meta.language == "en"


def test_extract_marine_metadata_abs():
    """
    WHAT: extract_marine_metadata() MUST correctly extract all 5 fields
    from a realistic ABS MODU rules document.
    """
    meta = extract_marine_metadata(
        text=_REALISTIC_ABS_TEXT,
        filename="/docs/ABS_MODU_Rules_2023.pdf",
    )
    assert meta.classification_society == "ABS"
    assert meta.version_year == "2023"
    assert meta.chapter_section == "Part 3 Section 2-1"
    assert meta.language == "en"


# ===========================================================================
# 7. Default values -- empty / minimal text
# ===========================================================================

def test_extract_marine_metadata_empty_text():
    """
    WHAT: extract_marine_metadata() MUST return sensible defaults when given
    empty or whitespace-only text.

    WHY: The extraction pipeline may receive empty documents (e.g. a PDF
    with only images and no extracted text). The caller must be able to
    consume the result without special-casing "None" for every field.
    """
    meta = extract_marine_metadata(text="", filename=None)
    assert meta.classification_society == "Unknown"
    assert meta.regulation_name == "Unknown"
    assert meta.version_year is None
    assert meta.chapter_section is None
    assert meta.language == "unknown"


def test_marine_metadata_dataclass_fields():
    """
    WHAT: MarineMetadata MUST be a dataclass with exactly 5 typed fields.

    WHY: Downstream code (M2 storage, M3 retrieval) reads these fields by
    attribute name. A missing field or wrong type would cause silent data
    corruption in the RAG pipeline.
    """
    meta = MarineMetadata(
        classification_society="DNV",
        regulation_name="DNV-ST-N001",
        version_year="2024",
        chapter_section="Pt.3 Ch.2",
        language="en",
    )
    assert meta.classification_society == "DNV"
    assert meta.regulation_name == "DNV-ST-N001"
    assert meta.version_year == "2024"
    assert meta.chapter_section == "Pt.3 Ch.2"
    assert meta.language == "en"
    # Verify field types
    assert isinstance(meta.classification_society, str)
    assert isinstance(meta.regulation_name, str)
    assert isinstance(meta.version_year, str)
    assert isinstance(meta.chapter_section, str)
    assert isinstance(meta.language, str)
