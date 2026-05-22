# -*- coding: utf-8 -*-
"""
M1 integration package.

WHAT: bridges between the M1 Document Parsing Engine and external modules
(M2 Storage, M6/M7 portals). Each bridge module encapsulates the translation
logic from M1 domain objects to the target module's expected format.

WHY: keeps M1 independent of other modules' implementation details. When a
downstream module changes its interface, only the relevant bridge module
needs updating -- the core M1 pipeline remains untouched.

Exports:
    create_document_record  -- build an m1_documents table row dict
    should_store_in_vector_store  -- quality gate for vector DB admission
"""

from .m2_bridge import create_document_record, should_store_in_vector_store

__all__ = [
    "create_document_record",
    "should_store_in_vector_store",
]
