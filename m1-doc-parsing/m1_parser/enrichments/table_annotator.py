# -*- coding: utf-8 -*-
"""
Header-to-Cell annotation for complex tables.

WHY: Offshore engineering tables (e.g., DNV Pt.4 Ch.8 Table 1 -- scantling
formulas) use multi-level headers with row-span and col-span. A naive table
parse loses the header hierarchy, making it impossible to answer questions
like "What is the minimum plate thickness for frame spacing > 3m in ice class
PC4?" The annotator reconnects each data cell to its row and column headers,
enabling precise chunk-level metadata.

The current implementation provides the annotation skeleton. Full header
parsing and cell association logic will be implemented once the Docling
table enrichment pipeline is integrated (dependent on 00060-05 converter.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HeaderInfo:
    """
    Metadata about a table header cell.

    WHAT: captures the header text, its level in the header hierarchy
    (0 = top-level, 1 = sub-header, etc.), and any colspan/rowspan info.

    WHY: multi-level headers are common in classification society rule
    tables. Without hierarchy information, "minimum thickness" cannot
    be associated with the correct sub-rule context.
    """

    # WHAT: the header text content (e.g., "Frame spacing (m)")
    text: str

    # WHAT: hierarchy level -- 0 is the topmost header row
    level: int = 0

    # WHAT: for multi-column headers, how many columns this header spans
    colspan: int = 1

    # WHAT: for multi-row headers, how many rows this header spans
    rowspan: int = 1


@dataclass
class CellAnnotation:
    """
    The result of annotating a single data cell with its header context.

    WHAT: connects a table data cell (identified by row/col position)
    to its row header(s), column header(s), and the full header path
    from root to the specific sub-header.

    WHY: the header_path string enables precise chunk metadata for the
    vector database -- a chunk can carry "DNV Pt.4 Ch.8 > Table 1 >
    Plating > Minimum thickness" as context, dramatically improving
    retrieval relevance for specific technical questions.
    """

    # WHAT: 0-based row index of this data cell in the table body
    row: int

    # WHAT: 0-based column index of this data cell in the table body
    col: int

    # WHAT: the cell's text content (e.g., "12.5" for a thickness value)
    cell_text: str

    # WHAT: row headers that apply to this cell (left-side labels)
    row_headers: list[str] = field(default_factory=list)

    # WHAT: column headers that apply to this cell (top-side labels)
    col_headers: list[str] = field(default_factory=list)

    # WHAT: full hierarchical header path from root to leaf
    # Example: "Plating / Minimum thickness / Ice class PC4"
    header_path: str = ""


def extract_headers(
    markdown_table: str,
) -> tuple[list[HeaderInfo], list[list[str]]]:
    """
    Extract header metadata and data rows from a Markdown table.

    WHAT: parses a pipe-delimited Markdown table, identifies the header
    section (rows above the separator line), and returns structured
    HeaderInfo objects plus the data rows.

    Args:
        markdown_table: A Markdown table string with pipe-delimited
            columns and a separator row (e.g., "|---|---|").

    Returns:
        A tuple of (headers, data_rows) where:
          - headers: list of HeaderInfo for each header cell
          - data_rows: list of rows, each row is a list of cell text strings

    NOTE: Skeleton implementation. Currently parses only single-line
    headers. Multi-level header detection (rowspan analysis) will be
    added when the Docling enrichment pipeline provides cell-level
    bounding box data.
    """
    lines = [line.strip() for line in markdown_table.strip().split("\n") if line.strip()]

    if len(lines) < 2:
        return [], []

    headers: list[HeaderInfo] = []
    data_rows: list[list[str]] = []
    past_header = False
    past_separator = False

    for line in lines:
        # Detect the separator row (e.g., "|---|---|")
        # WHY: Markdown tables use a line of dashes with optional colons
        # to separate headers from data and indicate alignment
        if _is_separator_row(line):
            past_separator = True
            past_header = True
            continue

        cells = _split_table_row(line)

        if not past_header:
            # This is a header row
            for col_idx, cell in enumerate(cells):
                headers.append(HeaderInfo(
                    text=cell.strip(),
                    level=0,
                    colspan=1,
                    rowspan=1,
                ))
        elif past_separator:
            # This is a data row
            data_rows.append([c.strip() for c in cells])

    return headers, data_rows


def annotate_header_to_cell(
    markdown_table: str,
) -> list[CellAnnotation]:
    """
    Annotate each data cell with its associated row and column headers.

    WHAT: for each data cell in the table, determines which row header
    (first column cell in that row) and which column header (corresponding
    column header from the header row) apply, then builds the full
    header path string.

    WHY: this annotation enables precise chunking -- when a chunk contains
    "12.5 mm" from a table cell, the header metadata tells the retriever
    that this value is "Minimum thickness for ice class PC4" rather than
    just a random number in a table.

    Args:
        markdown_table: A Markdown table string.

    Returns:
        List of CellAnnotation objects, one per data cell.

    NOTE: Skeleton implementation. Full implementation will handle
    multi-level headers, merged cells, and hierarchical header paths.
    """
    headers, data_rows = extract_headers(markdown_table)

    if not headers or not data_rows:
        return []

    annotations: list[CellAnnotation] = []

    for row_idx, row in enumerate(data_rows):
        # Determine row header: first column is typically the row label
        # WHY: offshore engineering tables follow the convention of
        # row labels in the leftmost column (e.g., "Ice class PC4")
        row_header = row[0] if row else ""

        for col_idx, cell_text in enumerate(row):
            # Determine column header for this cell position
            col_header = ""
            if col_idx < len(headers):
                col_header = headers[col_idx].text

            # Build the header path
            # WHY: colon-separated path format is compact and
            # human-readable in chunk metadata
            path_parts: list[str] = []
            if col_header:
                path_parts.append(col_header)
            if row_header and col_idx > 0:
                # Only add row header for non-label columns
                # (col 0 IS the row header, don't self-reference)
                path_parts.append(row_header)

            header_path = " / ".join(path_parts) if path_parts else cell_text

            row_headers = [row_header] if row_header and col_idx > 0 else []
            col_headers = [col_header] if col_header else []

            annotations.append(CellAnnotation(
                row=row_idx,
                col=col_idx,
                cell_text=cell_text,
                row_headers=row_headers,
                col_headers=col_headers,
                header_path=header_path,
            ))

    return annotations


# ===========================================================================
# Internal helpers
# ===========================================================================


def _is_separator_row(line: str) -> bool:
    """
    Check if a table row is the Markdown separator line.

    WHAT: returns True if the line consists entirely of |, -, :, and
    whitespace characters, with at least one dash.

    WHY: the separator line is the structural marker between headers
    and data in Markdown tables. Detecting it correctly is essential
    for accurate header extraction.
    """
    cleaned = line.replace("|", "").replace("-", "").replace(":", "").strip()
    has_dash = "-" in line
    return len(cleaned) == 0 and has_dash


def _split_table_row(line: str) -> list[str]:
    """
    Split a Markdown table row into individual cells.

    WHAT: strips leading/trailing pipe characters, then splits on
    the remaining pipe separators. Each cell is returned as-is
    (whitespace is preserved for the caller to strip as needed).

    WHY: Markdown table rows start and end with |, making a simple
    split("|") produce empty strings at both ends. This helper
    handles that common edge case.
    """
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return stripped.split("|")
