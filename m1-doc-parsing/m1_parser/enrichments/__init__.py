# -*- coding: utf-8 -*-
"""
M1 enrichers -- post-parsing metadata extraction and document enrichment.

WHY: Raw parsed markdown lacks domain-specific metadata (classification
society, regulation version, structural references, language). These
enrichment modules extract structured metadata from unstructured text
and annotate parsed documents for downstream M3 retrieval and M5 QA.

Sub-modules:
  - marine_metadata: Classification society, regulation name, version year,
    chapter/section, and language extraction for offshore documents.
"""
