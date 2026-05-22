# -*- coding: utf-8 -*-
"""
Standalone CLI for M1 document parsing engine.

Provides ``m1-parser`` command with subcommands for interactive
development and CI/CD pipeline use. No dependency on M6 or M7.

Usage::

    m1-parser convert input.pdf --backend docling --output ./out/
    m1-parser convert *.docx --backend docling --format json

WHY argparse subcommands: allows future expansion (e.g., ``serve`` for
web server, ``batch`` for file-list input, ``info`` for hardware info)
without breaking the existing CLI contract.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# WHY lazy import: the converter pulls in backends (docling, etc.) which
# have heavy dependencies. Importing at the top level would make even
# ``m1-parser --help`` slow. Deferring the import to inside the handler
# keeps --help instant.
from m1_parser.core.config import (
    SUPPORTED_BACKENDS,
    OCR_ENGINE_PRIORITY,
    VLM_PRESETS,
)

logger = logging.getLogger(__name__)

# Output formats supported by the serializer
_OUTPUT_FORMATS = ["md", "json", "html"]


# ===========================================================================
# Argument parser construction
# ===========================================================================


def build_parser() -> argparse.ArgumentParser:
    """
    Build the full argparse parser tree for m1-parser.

    WHAT: creates the root parser (description + global options) and
    registers all subcommands with their specific argument groups.

    WHY separate function from main(): makes the parser testable in
    isolation without invoking sys.exit(). Tests can call build_parser()
    and inspect the parser's configuration directly.

    Returns:
        Configured ArgumentParser, ready for parse_args().
    """
    parser = argparse.ArgumentParser(
        prog="m1-parser",
        description=(
            "M1 Document Parsing Engine -- Convert PDF, Office, and image "
            "files into structured Markdown with marine/offshore domain metadata."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  m1-parser convert spec.pdf --backend docling --output ./out/\n"
            "  m1-parser convert *.docx --format json\n"
            "  m1-parser convert scan.png --ocr easyocr --vlm paddleocr_vl\n"
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands (use '<command> --help' for details)",
    )

    # Subcommand: convert
    _add_convert_subparser(subparsers)

    return parser


def _add_convert_subparser(subparsers: argparse._SubParsersAction) -> None:
    """
    Register the ``convert`` subcommand with its arguments.

    WHAT: adds the convert subparser with positional INPUT argument and
    optional --backend/--ocr/--output/--format/--vlm flags.

    WHY subcommand design: future commands (serve, info, batch) will each
    have their own argument sets. Keeping convert as a subcommand avoids
    flag conflicts between modes.
    """
    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert document(s) to structured Markdown",
        description=(
            "Convert one or more document files to structured Markdown "
            "with metadata extraction and quality scoring."
        ),
    )

    # Positional: input file(s)
    convert_parser.add_argument(
        "input",
        nargs="+",
        metavar="INPUT",
        help="One or more document files to convert (PDF, DOCX, XLSX, image, etc.)",
    )

    # Optional: parsing backend
    convert_parser.add_argument(
        "--backend",
        choices=SUPPORTED_BACKENDS,
        default="docling",
        help=(
            "Parsing backend to use. 'docling' handles all formats; "
            "'marker' and 'mineru' are PDF/image only. "
            "(default: %(default)s)"
        ),
    )

    # Optional: OCR engine (used when parsing scanned PDFs or images)
    convert_parser.add_argument(
        "--ocr",
        choices=OCR_ENGINE_PRIORITY,
        default="easyocr",
        dest="ocr_engine",
        help=(
            "OCR engine for scanned documents. Preference: paddleocr > "
            "suryaocr > easyocr > tesseract. (default: %(default)s)"
        ),
    )

    # Optional: output directory
    convert_parser.add_argument(
        "--output",
        default="./output",
        help=(
            "Directory to write output files. Each document gets a "
            "subdirectory named by its doc_id. (default: %(default)s)"
        ),
    )

    # Optional: output format(s)
    convert_parser.add_argument(
        "--format",
        choices=_OUTPUT_FORMATS,
        default="md",
        dest="output_format",
        help="Output format: md (Markdown), json, or html. (default: %(default)s)",
    )

    # Optional: VLM preset (for vision-language model enhanced parsing)
    convert_parser.add_argument(
        "--vlm",
        choices=VLM_PRESETS,
        default=None,
        dest="vlm_preset",
        help=(
            "Vision-Language Model preset for complex page analysis. "
            "If omitted, uses Standard Pipeline (no VLM). "
            "Options: %(choices)s"
        ),
    )


# ===========================================================================
# Command handlers
# ===========================================================================


def _handle_convert(args: argparse.Namespace) -> int:
    """
    Execute the ``convert`` subcommand.

    WHAT: validates that every input file exists, then calls the converter
    pipeline for each file. Collects results and reports failures.

    WHY validate existence upfront: argparse validates format choices
    but NOT path existence. Checking upfront gives a clear error message
    before any expensive imports or model loading.

    Args:
        args: Parsed argparse namespace with input, backend, ocr_engine, etc.

    Returns:
        Exit code: 0 if all files converted successfully, 1 if any failed.
    """
    # -- Validate file existence (before heavy imports) --
    # WHY: catching file-not-found early prevents the expensive docling
    # import from running just to report a typo'd path.
    missing: list[str] = []
    for path_str in args.input:
        if not Path(path_str).exists():
            missing.append(path_str)

    if missing:
        for m in missing:
            print(f"Error: file not found -- {m}", file=sys.stderr)
        return 1

    # -- Lazy import converter (heavy: docling, torch, transformers) --
    # WHY deferred: --help and file-existence checks stay sub-second.
    # The full import chain is only triggered when actual conversion work
    # is about to happen.
    from m1_parser.core.converter import (
        convert,
        convert_batch,
        ParseOptions,
    )

    # Build parse options from CLI flags
    options = ParseOptions(
        backend=args.backend,
        ocr_engine=args.ocr_engine,
        vlm_preset=args.vlm_preset,
        output_dir=args.output,
        output_formats=[args.output_format],
    )

    # -- Execute conversions --
    # WHY convert_batch: collects errors from individual files so one
    # corrupted file does not abort the entire batch run.
    results = convert_batch(args.input, options=options, raises_on_error=False)

    # -- Report results --
    failed_count = 0
    for result in results:
        if result.success:
            print(
                f"[OK] {result.source_path} -> {result.doc_id} "
                f"({result.page_count}p, {result.table_count}t, "
                f"{result.figure_count}f)"
            )
        else:
            failed_count += 1
            print(
                f"[FAIL] {result.source_path}: {result.error or 'unknown error'}",
                file=sys.stderr,
            )

    return 0 if failed_count == 0 else 1


# ===========================================================================
# Entry point
# ===========================================================================


def main(argv: list[str] | None = None) -> int:
    """
    Main entry point for the m1-parser CLI.

    WHAT: parses command-line arguments, dispatches to the appropriate
    subcommand handler, and returns an exit code.

    WHY argv parameter: allows programmatic invocation in tests
    (``main(["--help"])``) without forking a subprocess.

    Args:
        argv: Command-line argument list. If None, reads from sys.argv.

    Returns:
        Exit code suitable for sys.exit() (0 = success, 1 = error).
    """
    parser = build_parser()

    args = parser.parse_args(argv)

    if args.command is None:
        # No subcommand given -- print help and exit
        parser.print_help()
        return 0

    if args.command == "convert":
        return _handle_convert(args)

    # Unknown subcommand (should not happen with argparse)
    print(f"Error: unknown command '{args.command}'", file=sys.stderr)
    return 1


# ===========================================================================
# Script entry point (python -m m1_parser.standalone.cli)
# ===========================================================================

if __name__ == "__main__":
    sys.exit(main())
