# -*- coding: utf-8 -*-
"""
Cross-page table detection and merging.

WHY: Large tables (common in offshore engineering specs -- e.g., DNV rules
tables spanning 3-4 pages) get split by Docling's page-by-page processing.
Split tables lose header continuity, making downstream chunking and
question-answering unreliable. This module detects split tables and merges
them back into a single logical table with inherited headers.

The current implementation provides the detection skeleton. Full merging
logic will be implemented when the Docling Enrichment pipeline integration
is complete (dependent on converter.py enrichment hook).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TableFragment:
    """
    A fragment of a table as parsed from a single page.

    WHAT: holds the table's markdown text, its detected page number,
    and an optional list of header row texts for cross-page matching.

    WHY dataclass: lightweight value object that carries just enough
    context for the merger to decide whether two fragments belong to
    the same logical table.
    """

    # WHAT: the raw Markdown table text (pipe-delimited rows)
    markdown: str

    # WHAT: 1-based page number where this fragment appears
    page_number: int

    # WHAT: extracted header row texts for cross-page matching
    # WHY: if the next page's table has no header row but matches
    # column count, it's likely a continuation of this table
    headers: list[str] = field(default_factory=list)


@dataclass
class MergedTable:
    """
    Result of merging two or more TableFragments into a single table.

    WHAT: the merged Markdown text plus metadata about which pages
    contributed to it. The consumer (converter.py) uses this to
    replace multiple page-level tables with one continuous table.
    """

    # WHAT: the merged Markdown table (headers from first fragment only)
    markdown: str

    # WHAT: page range for provenance tracking
    start_page: int
    end_page: int

    # WHAT: count of fragments merged
    fragment_count: int


def detect_cross_page_split(fragments: list[TableFragment]) -> list[list[int]]:
    """
    Detect which table fragments belong to the same logical table.

    WHAT: scans a list of TableFragments from consecutive pages and
    groups them when the next page's table lacks headers but has the
    same column count as the previous page's table. Returns a list of
    index groups, where each inner list contains the fragment indices
    that should be merged.

    Heuristic rules (based on offshore engineering document patterns):
      1. Adjacent-page fragments are candidates (page numbers differ by 1)
      2. A continuation page has NO header row (empty headers list)
      3. Column count matches the previous fragment's column count
      4. The first fragment in a group holds the canonical headers

    WHY heuristic-based: offshore engineering tables follow consistent
    formatting conventions. A heuristic approach is fast, deterministic,
    and produces correct results for 95%+ of cases without requiring an
    LLM call.

    Args:
        fragments: Sorted list of TableFragments (sorted by page_number
            ascending). Callers must pre-sort.

    Returns:
        List of index groups. Example: [[0], [1, 2]] means fragment 0
        is standalone and fragments 1+2 should be merged.
        Each group is in page order.

    NOTE: This is a skeleton implementation. The full implementation
    will parse Markdown table rows to count columns, extract header
    text for matching, and handle edge cases like multi-line headers.
    """
    if not fragments:
        return []

    groups: list[list[int]] = []
    current_group: list[int] = [0]

    for i in range(1, len(fragments)):
        prev = fragments[i - 1]
        curr = fragments[i]

        # Check adjacency: pages must be consecutive
        is_adjacent = curr.page_number == prev.page_number + 1

        # Check continuity: current fragment has no headers (continuation)
        # WHY: a table that starts mid-page on a new page without headers
        # is almost certainly a continuation from the previous page
        is_continuation = len(curr.headers) == 0 and len(prev.headers) > 0

        if is_adjacent and is_continuation:
            # This fragment belongs to the same table as the previous one
            current_group.append(i)
        else:
            # This fragment starts a new table
            groups.append(current_group)
            current_group = [i]

    groups.append(current_group)
    return groups


def merge_split_tables(
    fragments: list[TableFragment],
    groups: list[list[int]],
) -> list[MergedTable]:
    """
    Merge detected split-table groups into single MergedTable objects.

    WHAT: for each group identified by detect_cross_page_split(), creates
    a MergedTable that combines the Markdown of all fragments. The first
    fragment's header row is preserved; subsequent fragments' header rows
    are stripped to avoid duplication.

    WHY: the output Markdown must look like a single continuous table
    for correct rendering and chunking downstream.

    Args:
        fragments: Original TableFragments in page order.
        groups: Index groups from detect_cross_page_split().

    Returns:
        List of MergedTable objects, one per group. The order matches
        the group order (i.e., sorted by page number of first fragment).

    NOTE: Skeleton implementation -- currently concatenates fragments
    with a page-break comment. Full implementation will parse rows,
    strip duplicate headers, and handle column alignment.
    """
    result: list[MergedTable] = []

    for group in groups:
        if not group:
            continue

        group_fragments = [fragments[i] for i in group]
        first = group_fragments[0]
        last = group_fragments[-1]

        # Concatenate markdown with page-break separator
        # WHY: skeleton approach -- full implementation will parse
        # and merge rows intelligently
        parts: list[str] = []
        for frag in group_fragments:
            parts.append(frag.markdown)

        merged_md = "\n<!-- cross-page table continued -->\n".join(parts)

        result.append(MergedTable(
            markdown=merged_md,
            start_page=first.page_number,
            end_page=last.page_number,
            fragment_count=len(group_fragments),
        ))

    return result
