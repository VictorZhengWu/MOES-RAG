# -*- coding: utf-8 -*-
"""
CLI integration tests for m1-parser standalone tool.

WHY: The CLI is the primary interface for power users and automated
pipelines. It must handle --help correctly (first thing any user types),
fail gracefully on nonexistent files, and accept all documented flags.

Tests use subprocess for exit code / stderr validation, and in-process
argparse for flag acceptance. Full conversion is tested in test_converter.py.
"""

from __future__ import annotations

import sys
import subprocess
import tempfile
from pathlib import Path

import pytest
from m1_parser.standalone.cli import build_parser


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The installed entry point (pyproject.toml: m1-parser = m1_parser.standalone.cli:main)
# may not be available during testing, so invoke via module path.
CLI_MODULE = "m1_parser.standalone.cli"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """
    Invoke the CLI module with the given arguments.

    WHAT: runs ``python -m m1_parser.standalone.cli <args>`` in a subprocess,
    capturing stdout and stderr as text.

    WHY subprocess: real integration test -- verifies the exact exit codes,
    stderr messages, and stdout output that an end user would see.
    """
    return subprocess.run(
        [sys.executable, "-m", CLI_MODULE, *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


# ===========================================================================
# In-process argparse tests (fast, no subprocess)
# ===========================================================================


def test_parser_accepts_all_flags():
    """
    The argparse parser MUST accept --backend, --ocr, --output, --format,
    and --vlm with all documented choices.

    WHY: argparse validates choices when parsing, not when the handler runs.
    If a choice is rejected, argparse exits with a help message before any
    heavy imports happen -- keeping the error fast and actionable.
    """
    parser = build_parser()

    # Single file with all flags
    args = parser.parse_args([
        "convert", "doc.pdf",
        "--backend", "docling",
        "--ocr", "easyocr",
        "--output", "./out/",
        "--format", "json",
        "--vlm", "granite_docling",
    ])
    assert args.command == "convert"
    assert args.input == ["doc.pdf"]
    assert args.backend == "docling"
    assert args.ocr_engine == "easyocr"
    assert args.output == "./out/"
    assert args.output_format == "json"
    assert args.vlm_preset == "granite_docling"


def test_parser_accepts_multiple_inputs():
    """
    The ``convert`` subcommand MUST accept multiple positional input files.

    WHY: batch conversion is a core use case. The user runs
    ``m1-parser convert *.pdf`` and the shell expands to multiple paths.
    argparse must handle nargs="+" correctly to accept the expanded list.
    """
    parser = build_parser()
    args = parser.parse_args(["convert", "a.pdf", "b.docx", "c.png"])
    assert args.input == ["a.pdf", "b.docx", "c.png"]


def test_parser_defaults():
    """
    When optional flags are omitted, the parser MUST use documented defaults.

    WHY: defaults enable the simplest usage: ``m1-parser convert doc.pdf``
    should work without any extra flags. If defaults are wrong, the user
    gets unexpected behavior.
    """
    parser = build_parser()
    args = parser.parse_args(["convert", "doc.pdf"])
    assert args.backend == "docling"
    assert args.ocr_engine == "easyocr"
    assert args.output == "./output"
    assert args.output_format == "md"
    assert args.vlm_preset is None


def test_parser_rejects_invalid_backend():
    """
    argparse MUST reject an invalid --backend value with a nonzero exit
    code and an informative error message.

    WHY: catching invalid choices at parse time prevents the error from
    surfacing later during conversion (e.g., after models are loaded).
    """
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["convert", "doc.pdf", "--backend", "invalid_backend"])
    assert exc_info.value.code != 0


def test_parser_validates_format_choices():
    """
    argparse MUST reject an invalid --format value.
    """
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["convert", "doc.pdf", "--format", "xml"])


# ===========================================================================
# Subprocess integration tests (real exit codes and output)
# ===========================================================================


def test_cli_help():
    """
    ``m1-parser --help`` MUST return exit code 0 and show usage text.

    WHY: --help is the first command any user runs. If it fails or prints
    nothing useful, the tool is effectively undiscoverable.
    """
    result = _run("--help")
    assert result.returncode == 0, (
        f"Expected exit code 0, got {result.returncode}\n"
        f"stderr:\n{result.stderr}"
    )
    stdout = result.stdout + result.stderr  # argparse writes help to stdout
    assert "usage:" in stdout.lower(), (
        f"Expected 'usage:' in help output, got:\n{stdout}"
    )


def test_cli_convert_help():
    """
    ``m1-parser convert --help`` MUST return exit code 0 and show
    subcommand usage.

    WHY: each subcommand should have its own help. A user who knows they
    want to convert a file needs to see the convert-specific flags.
    """
    result = _run("convert", "--help")
    assert result.returncode == 0, (
        f"Expected exit code 0, got {result.returncode}\n"
        f"stderr:\n{result.stderr}"
    )
    stdout = result.stdout + result.stderr
    assert "usage:" in stdout.lower(), (
        f"Expected 'usage:' in convert --help output, got:\n{stdout}"
    )
    # Verify that required flags are mentioned in help text
    for flag in ("--backend", "--ocr", "--output", "--format", "--vlm"):
        assert flag in stdout, (
            f"Flag {flag} MUST appear in convert --help output.\nGot:\n{stdout}"
        )


def test_nonexistent_file():
    """
    Converting a file path that does not exist MUST return a nonzero
    exit code with an error message.

    WHY: silent failures on bad input confuse users and automation scripts.
    The CLI must loudly report "this file doesn't exist" and exit nonzero
    so that shell pipelines and CI jobs fail correctly.
    """
    result = _run("convert", "nonexistent_file_12345.pdf")
    assert result.returncode != 0, (
        f"Expected nonzero exit code for nonexistent file, "
        f"got {result.returncode}"
    )
    combined = (result.stdout + result.stderr).lower()
    # At least one of these error indicators must be present
    assert (
        "not exist" in combined
        or "not found" in combined
        or "no such file" in combined
        or "error" in combined
    ), (
        f"Expected error message for nonexistent file.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_cli_format_choices():
    """
    The ``--format`` flag MUST accept only valid output format values
    (md, json, html).

    WHY: a typo like ``--format markdowwn`` should be caught early by
    argparse, not halfway through a 10-minute document conversion.
    """
    result = _run("convert", "--format", "invalid_format", "dummy.pdf")
    assert result.returncode != 0, (
        f"Expected nonzero exit code for invalid --format value, "
        f"got {result.returncode}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert "invalid" in combined or "error" in combined or "argument" in combined or "choice" in combined, (
        f"Expected error message for invalid --format.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
