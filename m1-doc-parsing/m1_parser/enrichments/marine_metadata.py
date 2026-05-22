# -*- coding: utf-8 -*-
"""
Marine & Offshore metadata extraction from parsed document text.

WHAT: Extracts 5 structured metadata fields from unstructured offshore
engineering document text:

  1. classification_society -- DNV, ABS, CCS, LR, BV, NK, RINA, KR, IMO, IACS
  2. regulation_name        -- derived from filename or document title
  3. version_year           -- 4-digit year (19xx-20xx) from the document
  4. chapter_section        -- structural reference (Pt./Ch., Part/Section, etc.)
  5. language               -- langdetect-based language classification

WHY: Downstream RAG modules (M3 retrieval, M5 QA) need structured metadata
for filtering, faceted search, citation linking, and language routing. Without
this extraction, all documents are in an undifferentiated pool with no way to
filter by "only DNV rules from 2024 about hull structures" during retrieval.

Key decisions:
  - Regex-based classification society matching (word-boundary-anchored) rather
    than NLP NER, because the 10-society closed set is small and regex is both
    fast and deterministic. No GPU or model loading required.
  - langdetect for language classification rather than fasttext-langdetect
    because langdetect is a pure-Python library with zero model-download
    dependency, making it suitable for air-gapped deployment environments.
  - Dataclass return type (MarineMetadata) rather than dict for type safety
    and IDE autocomplete support in downstream consumers.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from langdetect import DetectorFactory, detect, LangDetectException

# ---------------------------------------------------------------------------
# Ensure deterministic language detection across runs
# ---------------------------------------------------------------------------
DetectorFactory.seed = 0


# ===========================================================================
# Data model
# ===========================================================================


@dataclass
class MarineMetadata:
    """
    Structured metadata extracted from an offshore engineering document.

    WHAT: Immutable container for the 5 extraction fields. All fields are
    strings with explicit sentinel values ("Unknown", "unknown", None) so
    that consumers never encounter a bare None for required fields.

    WHY: Downstream modules (M2 storage writer, M3 retrieval filter, M5 QA
    router) depend on stable attribute names and types. A dataclass with
    frozen=False (default) allows incremental field population by the
    extraction pipeline, while the explicit field annotations serve as
    self-documenting API contracts.
    """

    classification_society: str = "Unknown"
    regulation_name: str = "Unknown"
    version_year: str | None = None
    chapter_section: str | None = None
    language: str = "unknown"


# ===========================================================================
# Classification society regex patterns
# ===========================================================================

# WHAT: (regex_pattern, standard_abbreviation) pairs for the 10 IACS member
# societies plus IMO (regulatory) and IACS (industry umbrella).
#
# WHY tuples: two-element tuples are simpler than OrderedDict for a small
# fixed list. Each pattern includes \b word-boundary anchors to prevent
# substring false positives (e.g. "ABS" matching inside "ABSOLUTE").
# Long-form aliases are OR'd with the abbreviation pattern so that
# "Lloyd's Register" maps to "LR" just like the bare "LR" pattern does.

_SOCIETY_PATTERNS: list[tuple[str, str]] = [
    (r"\bDNV\b", "DNV"),
    (r"\bABS\b", "ABS"),
    (r"\bCCS\b", "CCS"),
    (r"\bLR\b|Lloyd'?s\s+Register", "LR"),
    (r"\bBV\b|Bureau\s+Veritas", "BV"),
    (r"\bNK\b|Nippon\s+Kaiji\s+Kyokai", "NK"),
    (r"\bRINA\b|Registro\s+Italiano\s+Navale", "RINA"),
    (r"\bKR\b|Korean\s+Register", "KR"),
    (r"\bIMO\b", "IMO"),
    (r"\bIACS\b", "IACS"),
]


# ===========================================================================
# Version year regex
# ===========================================================================

# WHAT: matches a 4-digit year in the range 1900-2099.
# WHY the range constraint: years outside 1900-2099 are almost certainly
# not publication years (e.g. "1800" could be a measurement value;
# "2105" is not a realistic regulation year yet). The constraint also
# prevents false matches against random 4-digit numbers in tables.
_YEAR_PATTERN: re.Pattern = re.compile(r"(20\d{2}|19\d{2})")


# ===========================================================================
# Chapter/section structural reference regex
# ===========================================================================

# WHAT: matches 5 structural reference conventions found in offshore docs:
#   1. "Pt.3 Ch.2" format (DNV, IACS) -- abbreviated Latin
#   2. "Part 3 Section 2-1" format (ABS, LR) -- full English
#   3. "第 3 章" format (CCS, Chinese documents) -- CJK
#   4. "Chapter 5" format (generic English)
#   5. "§ 3.1" format (legal/regulatory paragraph sign)
#
# WHY the multi-branch alternation: offshore documents use different
# structural notation depending on the classification society and language.
# A single combined regex with named alternation groups is faster than
# five separate regex searches and avoids priority-ordering logic.
_CHAPTER_PATTERN: re.Pattern = re.compile(
    r"(Pt\.?\s*\d+(\s*Ch\.?\s*\d+)?)"
    r"|(Part\s+\d+[A-Z]?\s*Section\s*[\d-]+)"
    r"|(第\s*\d+\s*章)"
    r"|(Chapter\s+\d+)"
    r"|(§\s*[\d.]+)"
)


# ===========================================================================
# Extraction functions
# ===========================================================================


def extract_classification_society(text: str) -> str:
    """
    Extract the classification society abbreviation from document text.

    WHAT: Scans the input text against _SOCIETY_PATTERNS in order. Returns
    the abbreviation of the first matching society. If no society is found,
    returns the sentinel string "Unknown".

    The matching is case-sensitive and uses \b word boundaries to prevent
    substring false positives (e.g. "ABS" inside "absolute").

    WHY ordered scanning: the first match in document flow is usually the
    issuing body at the top of the document. If a document references
    multiple societies (e.g. "ABS" in the header and "DNV" in a footnote),
    the first match is the primary one.

    Args:
        text: Raw or parsed document text to scan.

    Returns:
        Standard society abbreviation (e.g. "DNV", "ABS") or "Unknown".
    """
    for pattern, abbreviation in _SOCIETY_PATTERNS:
        if re.search(pattern, text):
            return abbreviation
    return "Unknown"


def extract_regulation_name(
    text: str,
    filename: str | None = None,
) -> str:
    """
    Derive a human-readable regulation name from filename and/or text.

    WHAT:
      1. If 'filename' is provided, extract its basename (without extension)
         as the regulation name. This is the most reliable name source.
      2. Otherwise, use the first non-empty line of 'text' (up to 120 chars)
         as a fallback title.
      3. If both are missing/empty, return "Unknown".

    WHY two-tier fallback: filenames are assigned by authors and are
    reliable. Text title extraction is an imperfect heuristic but serves
    as a reasonable last resort for byte-stream inputs.

    Args:
        text: Document body text (used only if filename is None/empty).
        filename: Optional source file path (e.g. "/docs/DNV-ST-N001.pdf").

    Returns:
        A human-readable regulation name string.
    """
    if filename:
        # Extract basename and strip the extension for a clean name
        basename: str = os.path.basename(filename)
        # os.path.splitext returns ('DNV-ST-N001_2024', '.pdf')
        name_without_ext, _ = os.path.splitext(basename)
        if name_without_ext:
            return name_without_ext

    # Fallback: use the first non-empty line of text as the title
    if text:
        first_line: str = text.strip().split("\n", 1)[0].strip()
        if first_line:
            # Truncate to a reasonable length for display
            return first_line[:120]

    return "Unknown"


def extract_version_year(text: str) -> str | None:
    """
    Extract the version/publication year from document text.

    WHAT: Searches for the first occurrence of a 4-digit year in the range
    1900-2099 using _YEAR_PATTERN. Returns the matched year as a string,
    or None if no year is found.

    WHY first-match semantics: documents like "Published 2020, revised 2023"
    should return "2020" (the primary publication date), not the latest
    revision. The first year reference is the original publication year.

    Args:
        text: Document text to scan.

    Returns:
        4-digit year string (e.g. "2024") or None.
    """
    match: re.Match | None = _YEAR_PATTERN.search(text)
    if match:
        return match.group(0)
    return None


def extract_chapter_section(text: str) -> str | None:
    """
    Extract the chapter/section structural reference from document text.

    WHAT: Searches for any of 5 structural reference conventions using
    _CHAPTER_PATTERN. Returns the matched reference string, or None if
    no structural reference is found.

    Recognised conventions:
      - Pt.3 Ch.2          (DNV / IACS abbreviated format)
      - Part 3 Section 2-1 (ABS / LR full English format)
      - 第 3 章            (Chinese chapter references)
      - Chapter 5          (generic English chapter)
      - § 3.1              (legal/regulatory paragraph sign)

    WHY: The chapter/section is the primary structural key for navigating
    regulation documents. It is used by M3 retrieval for section-level
    search filtering and by M5 QA for citation linking in answers.

    Args:
        text: Document text to scan.

    Returns:
        Matched structural reference string or None.
    """
    match: re.Match | None = _CHAPTER_PATTERN.search(text)
    if match:
        # Return the full match, stripping trailing whitespace
        return match.group(0).strip()
    return None


def extract_language(text: str) -> str:
    """
    Detect the primary language of the document text using langdetect.

    WHAT: Uses the langdetect library to classify text language. Returns
    a language code string (e.g. "en", "zh-cn", "ko", "ja", "no") or the
    sentinel "unknown" if detection fails.

    WHY langdetect: it is a pure-Python library with no model download
    requirement, making it suitable for air-gapped deployments. The
    DetectorFactory.seed = 0 ensures deterministic results across runs.

    The language code is normalised: langdetect returns "zh-cn" for
    simplified Chinese, which matches the i18n language codes used by
    the M6/M7 web UI. Other common offshore language codes ("en", "ko",
    "ja", "no") are returned as-is.

    Args:
        text: Document text to classify.

    Returns:
        ISO language code string (e.g. "en", "zh-cn") or "unknown".
    """
    try:
        return detect(text)
    except LangDetectException:
        # LangDetectException is raised when:
        #   - text is too short (< ~20 chars)
        #   - text contains no recognisable features
        #   - langdetect internal error
        return "unknown"


# ===========================================================================
# Combined extraction
# ===========================================================================


def extract_marine_metadata(
    text: str,
    filename: str | None = None,
) -> MarineMetadata:
    """
    Extract all 5 metadata fields from an offshore engineering document.

    WHAT: Orchestrates the five individual extractor functions and returns
    a fully populated MarineMetadata dataclass. Each extractor is called
    independently on the full text; there is no cross-extractor dependency.

    WHY combined function: downstream callers (M2 storage writer, M3
    retrieval indexer) need all 5 fields as a single structured object.
    Calling extract_marine_metadata() once is simpler and less error-prone
    than calling 5 individual functions and assembling the result manually.

    Args:
        text: Full document text (after parsing/conversion).
        filename: Optional source filename for regulation_name extraction.

    Returns:
        A fully populated MarineMetadata dataclass. All string fields
        have explicit sentinel values ("Unknown" / "unknown") when no
        data is found. version_year and chapter_section are None when
        not detected.
    """
    return MarineMetadata(
        classification_society=extract_classification_society(text),
        regulation_name=extract_regulation_name(text, filename),
        version_year=extract_version_year(text),
        chapter_section=extract_chapter_section(text),
        language=extract_language(text),
    )
