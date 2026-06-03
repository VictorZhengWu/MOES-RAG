"""
Tests for M5 QA Engine — Citation Builder (citation_builder.py).

WHAT: Unit tests for build_citations(), attach_citations(), and format_citation_text().
WHY: Verify that citation extraction deduplicates by (source_doc, section),
     attaches only referenced citations, and formats human-readable output.
"""

import pytest

from contracts.document import Chunk, DocumentMetadata, Domain
from contracts.qa_engine import Citation
from contracts.retrieval import ScoredChunk

from m5_qa.context.citation_builder import (
    attach_citations,
    build_citations,
    format_citation_text,
)


# ---------------------------------------------------------------------------
# Helper: create a minimal ScoredChunk fixture
# ---------------------------------------------------------------------------

def _make_chunk(
    chunk_id: str = "c001",
    text: str = "This is a test chunk with regulation content about steel grades.",
    source_filename: str = "dnv_pt2_ch1.pdf",
    regulation_name: str = "DNV Rules Pt.2 Ch.1",
    chapter_section: str | None = "Pt.2 Ch.1 Sec.3",
) -> ScoredChunk:
    """Create a ScoredChunk with minimal metadata for citation testing."""
    meta = DocumentMetadata(
        source_filename=source_filename,
        regulation_name=regulation_name,
        chapter_section=chapter_section,
    )
    chunk = Chunk(
        chunk_id=chunk_id,
        text=text,
        metadata=meta,
        chunk_type="clause",
    )
    return ScoredChunk(
        chunk=chunk,
        score=0.95,
        source="dense",
        citation="DNV Rules Pt.2 Ch.1, Pt.2 Ch.1 Sec.3",
    )


# ---------------------------------------------------------------------------
# Tests: build_citations
# ---------------------------------------------------------------------------

class TestBuildCitations:
    """Tests for build_citations() — extract and deduplicate citations from chunks."""

    def test_build_citations_single(self):
        """
        WHAT: 1 chunk → 1 citation.
        WHY: A single retrieved chunk should produce exactly one Citation
             with the correct index, source_doc, section, and excerpt.
        """
        chunks = [_make_chunk()]
        result = build_citations(chunks)

        assert len(result) == 1
        c = result[0]
        assert c.index == 1
        assert c.source_doc == "dnv_pt2_ch1.pdf"
        assert c.section == "DNV Rules Pt.2 Ch.1"
        assert c.clause_id == "Pt.2 Ch.1 Sec.3"
        assert len(c.excerpt) > 0
        # excerpt should be first 200 chars of chunk text
        assert c.excerpt == chunks[0].chunk.text[:200]

    def test_build_citations_dedup(self):
        """
        WHAT: 2 chunks from same source → 1 citation.
        WHY: Multiple chunks from the same (source_filename, regulation_name)
             pair should be deduplicated into a single Citation.
        """
        chunks = [
            _make_chunk(chunk_id="c001", text="First chunk about steel."),
            _make_chunk(chunk_id="c002", text="Second chunk about welding."),
        ]
        result = build_citations(chunks)

        assert len(result) == 1, (
            "Same (source_doc, section) pair should produce only 1 citation"
        )
        assert result[0].index == 1
        assert result[0].source_doc == "dnv_pt2_ch1.pdf"


# ---------------------------------------------------------------------------
# Tests: attach_citations
# ---------------------------------------------------------------------------

class TestAttachCitations:
    """Tests for attach_citations() — filter to only referenced citations."""

    def test_attach_citations(self):
        """
        WHAT: Only [1] and [3] referenced, [2] unused → returns 2 citations.
        WHY: Citations should only be attached if the answer text contains
             their index marker (e.g., [1], [3]). Unused citations are excluded.
        """
        citations = [
            Citation(index=1, source_doc="doc_a.pdf", section="Sec A"),
            Citation(index=2, source_doc="doc_b.pdf", section="Sec B"),
            Citation(index=3, source_doc="doc_c.pdf", section="Sec C"),
        ]
        answer = "According to [1] and [3], the steel grade must meet the requirements."
        result = attach_citations(answer, citations)

        assert len(result) == 2
        indices = {c.index for c in result}
        assert indices == {1, 3}
        # Verify [2] is excluded
        assert 2 not in indices


# ---------------------------------------------------------------------------
# Tests: format_citation_text
# ---------------------------------------------------------------------------

class TestFormatCitationText:
    """Tests for format_citation_text() — human-readable citation output."""

    def test_format_citation_text(self):
        """
        WHAT: Formatted output has section headers and citation markers.
        WHY: The citation block must include a "## Sources" header and
             each citation formatted as [N] source_doc, section — excerpt.
        """
        citations = [
            Citation(
                index=1,
                source_doc="dnv_pt2_ch1.pdf",
                section="DNV Rules Pt.2 Ch.1",
                clause_id="Pt.2 Ch.1 Sec.3",
                excerpt="This regulation specifies the minimum yield strength...",
            ),
        ]
        result = format_citation_text(citations)

        assert "## Sources" in result
        assert "[1]" in result
        assert "dnv_pt2_ch1.pdf" in result
        assert "DNV Rules Pt.2 Ch.1" in result
        assert "Pt.2 Ch.1 Sec.3" in result
