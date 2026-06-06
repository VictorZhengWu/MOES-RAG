# -*- coding: utf-8 -*-
"""
Query Analyzer — First stage of the M3 Retrieval pipeline.

WHAT: Analyzes a raw user query string and extracts structured metadata
(classification society, chapter/section, version year, keywords, steel
grades, temperature values) plus a cleaned semantic query for embedding.

The output is a QueryAnalysis dataclass that downstream retrieval stages
use for:
  - Metadata filtering (classification_society, chapter_section, version_year)
  - Keyword boosting (keywords list)
  - Semantic embedding (semantic_query string)

WHY: Raw user queries mix natural language with technical identifiers
(e.g. "DNV Pt.3 Ch.2 AH36 350 C hull welding 2024"). Feeding this
undifferentiated text to a semantic embedding model dilutes the signal.
By separating structured metadata from the semantic core, we can:
  1. Use deterministic regex for precise matching of codes and standards.
  2. Feed only the semantic portion to the embedding model for better
     retrieval quality.
  3. Combine both signals in the retrieval fusion stage.

Key design decisions:
  - Re-implements the M1 regex extraction patterns locally rather than
    importing from m1_parser. This keeps M3 independent per the module
    isolation rule (modules communicate only through contracts/).
  - Regex (not NER): the closed set of 10 classification societies and
    well-defined structural reference formats make regex both faster and
    more deterministic than NLP-based NER.
  - keyword list: extracted terms (steel grades, temperature values) are
    stored separately for BM25/sparse boosting. The semantic_query is the
    original text with these terms stripped, for dense embedding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# =============================================================================
# Data model
# =============================================================================


@dataclass
class QueryAnalysis:
    """
    Structured analysis of a user query for the retrieval pipeline.

    WHAT: Container for all metadata extracted from a raw query string.
    All fields except semantic_query are optional (None = not detected).

    WHY dataclass: provides typed, named fields for downstream consumers
    (query rewriting, filtering, boosting stages) with IDE autocomplete.
    """

    classification_society: str | None = None
    """Detected classification society abbreviation (e.g. 'DNV', 'ABS')."""

    chapter_section: str | None = None
    """Detected structural reference (e.g. 'Pt.3 Ch.2', 'Part 3 Section 2-1')."""

    version_year: int | None = None
    """Detected version/publication year (19xx-20xx)."""

    keywords: list[str] = field(default_factory=list)
    """Extracted technical keywords: steel grades, temperature values, etc."""

    semantic_query: str = ""
    """Cleaned query text for semantic embedding (original minus keywords)."""


# =============================================================================
# Regex patterns (re-implemented from M1 for module independence)
# =============================================================================

# WHAT: (pattern, abbreviation) pairs for 10 IACS member societies + IMO/IACS.
# WHY: word-boundary anchors prevent substring false positives (e.g. "ABS"
# matching inside "ABSOLUTE"). Ordered; first match wins.
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

# WHAT: matches 4-digit year in 1900-2099 range.
# WHY range: years outside this range are almost certainly not publication
# years (e.g. "1800" could be a measurement; "2105" is not realistic).
_YEAR_PATTERN: re.Pattern = re.compile(r"(20\d{2}|19\d{2})")

# WHAT: matches 5 structural reference conventions used in offshore docs:
#   Pt.3 Ch.2, Part 3 Section 2-1, 第 3 章, Chapter 5, § 3.1
# WHY combined alternation: one-pass scanning is faster than 5 separate regex.
_CHAPTER_PATTERN: re.Pattern = re.compile(
    r"(Pt\.?\s*\d+(\s*Ch\.?\s*\d+)?)"
    r"|(Part\s+\d+[A-Z]?\s*Section\s*[\d-]+)"
    r"|(第\s*\d+\s*章)"
    r"|(Chapter\s+\d+)"
    r"|(§\s*[\d.]+)"
)

# WHAT: matches steel grade identifiers like AH36, DH32, EH40, FH420.
# Pattern: 2-4 uppercase letters followed by 2-3 digits.
# WHY: steel grades are common in offshore queries and need precise matching.
_STEEL_GRADE_PATTERN: re.Pattern = re.compile(r"\b[A-Z]{2,4}\d{2,3}\b")

# WHAT: matches temperature values with optional degree symbol and C/F unit.
# Pattern: 2-4 digits, optional whitespace, optional degree symbol, C or F.
# WHY: temperature is a key parameter in exhaust/engine queries.
_TEMPERATURE_PATTERN: re.Pattern = re.compile(r"\d{2,4}\s*[°º]?\s*[CF]\b")


# =============================================================================
# Re-implemented extraction functions (from M1, for module independence)
# =============================================================================


def _extract_classification_society(text: str) -> str | None:
    """
    Extract classification society abbreviation from text.

    WHAT: Scans text against _SOCIETY_PATTERNS. Returns the abbreviation
    of the first match, or None if no society found.

    WHY local re-implementation: M3 must not import from M1's src/ per
    module isolation rules. The regex is small and deterministic.

    Args:
        text: Query or document text to scan.

    Returns:
        Society abbreviation (e.g. 'DNV', 'ABS') or None.
    """
    for pattern, abbreviation in _SOCIETY_PATTERNS:
        if re.search(pattern, text):
            return abbreviation
    return None


def _extract_chapter_section(text: str) -> str | None:
    """
    Extract chapter/section structural reference from text.

    WHAT: Searches for structural references (Pt./Ch., Part/Section, etc.).
    Returns the matched text or None.

    Recognises: Pt.3 Ch.2, Part 3 Section 2-1, 第 3 章, Chapter 5, § 3.1.

    Args:
        text: Query or document text to scan.

    Returns:
        Matched structural reference string or None.
    """
    match = _CHAPTER_PATTERN.search(text)
    if match:
        return match.group(0).strip()
    return None


def _extract_version_year(text: str) -> int | None:
    """
    Extract version/publication year from text.

    WHAT: Finds the first 4-digit year in [1900, 2099] and returns it as int.
    Returns None if no year found.

    Args:
        text: Query or document text to scan.

    Returns:
        4-digit year as integer, or None.
    """
    match = _YEAR_PATTERN.search(text)
    if match:
        return int(match.group(0))
    return None


def _extract_keywords(text: str) -> list[str]:
    """
    Extract technical keywords from query text.

    WHAT: Detects and collects:
      1. Steel grade identifiers (e.g. AH36, DH32, EH40) via _STEEL_GRADE_PATTERN
      2. Temperature values (e.g. 350 C, 1200 F) via _TEMPERATURE_PATTERN

    WHY: These technical identifiers have exact-match semantics. They should
    be used for precise BM25/sparse retrieval boosting, NOT for fuzzy
    semantic embedding matching. Separating them prevents the embedding
    model from confusing e.g. "AH36" with similar-looking terms.

    Args:
        text: The raw query text to scan.

    Returns:
        List of detected keyword strings, in order of first appearance.
    """
    keywords: list[str] = []
    seen: set[str] = set()

    # Extract steel grades (e.g. AH36, DH32)
    for match in _STEEL_GRADE_PATTERN.finditer(text):
        kw = match.group(0)
        if kw not in seen:
            keywords.append(kw)
            seen.add(kw)

    # Extract temperature values (e.g. 350 C, 1200 F)
    for match in _TEMPERATURE_PATTERN.finditer(text):
        kw = match.group(0).strip()
        if kw not in seen:
            keywords.append(kw)
            seen.add(kw)

    return keywords


# =============================================================================
# Helper functions
# =============================================================================


def _is_exact_match(query: str) -> bool:
    """
    Check whether the query looks like a regulation/standard identifier.

    WHAT: Recognises queries that are regulation document numbers rather
    than natural language questions. Pattern: uppercase-prefix + dash +
    alphanumeric code (e.g. 'DNV-ST-N001', 'ABS-RULE-2023', 'ISO-9001').

    WHY: Exact-match queries should bypass semantic embedding and go
    straight to metadata-based filtering for faster, more precise results.

    Args:
        query: The raw query string.

    Returns:
        True if the query matches a regulation identifier format.
    """
    # WHAT: matches patterns like DNV-ST-N001, ABS-RULE-2023, ISO-9001
    # Upper-case prefix (2-6 chars), dash, alphanumeric code
    pattern: re.Pattern = re.compile(r"^[A-Z]{2,6}-[A-Za-z0-9-]+$")
    return bool(pattern.match(query.strip()))


def _is_keyword_query(query: str) -> bool:
    """
    Check whether the query is a short keyword-based search.

    WHAT: A query is considered a keyword query if it has <=5 words AND
    contains at least one proper noun (detected as an uppercase word
    of 2+ characters).

    WHY: Short keyword queries benefit from BM25/sparse retrieval more
    than dense semantic retrieval. Identifying them allows the retrieval
    pipeline to adjust the fusion weighting in favour of sparse results.

    Args:
        query: The raw query string.

    Returns:
        True if the query is a short keyword query with proper nouns.
    """
    words: list[str] = query.strip().split()

    # Must be short (<= 5 words)
    if len(words) > 5:
        return False

    # Must contain at least one proper noun (all-uppercase word of 2+ chars)
    # This distinguishes "DNV hull welding" (keyword) from "hello world" (too
    # generic to be a meaningful keyword search).
    has_proper_noun: bool = any(
        w.isupper() and len(w) >= 2 for w in words
    )

    return has_proper_noun


# =============================================================================
# Main analysis function
# =============================================================================


def analyze_query(query: str) -> QueryAnalysis:
    """
    Analyze a raw user query and extract structured metadata.

    WHAT: The main entry point for query analysis. Applies extraction
    functions in sequence to produce a QueryAnalysis dataclass containing:
      - classification_society: the issuing body (if detected)
      - chapter_section: structural reference (if detected)
      - version_year: publication year (if detected)
      - keywords: technical terms (steel grades, temperatures, etc.)
      - semantic_query: cleaned text for embedding

    The semantic_query is built by removing the extracted keyword
    substrings from the original query, leaving only the natural
    language portion.

    WHY: This single function is the contract between the query input
    and the downstream pipeline stages. It transforms raw text into
    structured signals that each stage can consume independently.

    Args:
        query: The raw user query string.

    Returns:
        A QueryAnalysis dataclass with all detected metadata.
    """
    # Step 1: Extract classification society
    society = _extract_classification_society(query)

    # Step 2: Extract chapter/section reference
    chapter = _extract_chapter_section(query)

    # Step 3: Extract version year (as int, not str)
    year = _extract_version_year(query)

    # Step 4: Extract technical keywords (steel grades, temperatures)
    keywords = _extract_keywords(query)

    # Step 5: Build semantic query by removing keywords from the original text
    # WHY: The semantic embedding model should receive cleaned text without
    # technical codes that lack semantic meaning (e.g. "AH36" is a steel
    # grade code, not a word with contextual meaning).
    semantic_query = query
    for kw in keywords:
        # Remove the keyword and any surrounding whitespace artifacts
        semantic_query = semantic_query.replace(kw, "")
    # Collapse multiple spaces into one and strip
    semantic_query = re.sub(r"\s+", " ", semantic_query).strip()

    return QueryAnalysis(
        classification_society=society,
        chapter_section=chapter,
        version_year=year,
        keywords=keywords,
        semantic_query=semantic_query,
    )


def strip_section(chapter_section: str) -> str | None:
    """
    Strip the most specific part of a hierarchical chapter reference.

    WHAT: Removes the rightmost section/subsection from a chapter string
          to broaden the filter scope. Used by the hierarchical fallback
          in retrieval — if "Pt.4 Ch.3 §2.1" returns too few results,
          retry with "Pt.4 Ch.3", then "Pt.4", then None.

    WHY: Classification society documents have a tree structure. A query
         for "Ch.3 §2.1" that yields 0 results should not fail — it should
         fall back to the chapter level first. This is especially common
         when the section numbering in the user's query doesn't perfectly
         match the extracted metadata.

    Examples:
        "Pt.4 Ch.3 §2.1" → "Pt.4 Ch.3"
        "Pt.4 Ch.3"      → "Pt.4"
        "Ch.3 §2.1"      → "Ch.3"
        "Ch.3"           → None
        "Pt.4"           → None
    """
    if not chapter_section:
        return None

    import re

    # Try stripping a section (e.g., "§2.1" or "Section 2.1")
    # Pattern: §\d+(\.\d+)? optionally preceded by a space
    section_match = re.search(r"\s*§\s*\d+(?:\.\d+)?$", chapter_section)
    if section_match:
        stripped = chapter_section[:section_match.start()].strip()
        return stripped if stripped else None

    # Try stripping "Section X.Y" or "Sec. X.Y"
    section_match = re.search(r"\s*S(?:ec(?:tion)?)?\.?\s*\d+(?:\.\d+)?$", chapter_section, re.IGNORECASE)
    if section_match:
        stripped = chapter_section[:section_match.start()].strip()
        return stripped if stripped else None

    # Try stripping a chapter (e.g., "Ch.3" or "Chapter 3")
    # Only strip if there's something before it (i.e., a Part)
    chapter_match = re.search(r"\s*Ch(?:apter)?\.?\s*\d+$", chapter_section, re.IGNORECASE)
    if chapter_match and chapter_match.start() > 0:
        stripped = chapter_section[:chapter_match.start()].strip()
        return stripped if stripped else None

    # Try stripping "Pt.X" or "Part X"
    part_match = re.search(r"\s*P(?:t|art)\.?\s*\d+$", chapter_section, re.IGNORECASE)
    if part_match and chapter_section[:part_match.start()].strip():
        return chapter_section[:part_match.start()].strip()

    # Already at the top level
    return None


def build_fallback_chain(chapter_section: str) -> list[str | None]:
    """
    Build a list of progressively broader chapter filters for fallback retrieval.

    WHAT: Starting from the full chapter_section, repeatedly call strip_section()
          to generate [full, chapter, part, None] filter chain.

    WHY: The retrieval pipeline can iterate over this chain, trying each filter
         level until enough results are found. The last element (None) means
         "no chapter filter" — search the entire document corpus.
    """
    chain = [chapter_section]
    current = chapter_section
    while current:
        current = strip_section(current)
        if current:
            chain.append(current)
    chain.append(None)
    return chain
