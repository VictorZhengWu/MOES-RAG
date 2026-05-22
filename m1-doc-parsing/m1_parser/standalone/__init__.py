# -*- coding: utf-8 -*-
"""
Standalone entry points for the M1 document parsing engine.

Provides two self-contained ways to use M1 without M6/M7:
  - CLI (cli.py): ``m1-parser convert input.pdf --backend docling``
  - Web server (web_server.py): ``python -m m1_parser.standalone.web_server``

WHY separate standalone package: these are thin wrappers that depend on
the core pipeline. Keeping them in their own sub-package makes the
boundary clear -- standalone/ never contains business logic.
"""
