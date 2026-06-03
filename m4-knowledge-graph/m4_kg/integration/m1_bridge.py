"""
M1 integration hook — bridges M4 knowledge graph extraction with M1 document parsing.

WHAT:
  This module provides the ``on_parse_complete()`` hook function that M1's
  converter.py calls after successfully parsing a document. It asynchronously
  triggers the M4 knowledge graph extraction pipeline without blocking M1's
  response to the user.

WHY:
  M4's entity/relation extraction can take seconds to minutes (depending on
  document size and LLM backend latency). M1 must return the parsed result
  to the user immediately — the JSON response includes a ``"kg_status":
  "building"`` field. M4 builds the graph in the background via
  asyncio.create_task(). When complete, it updates the status flag (future:
  writes to M2 RelationalDB ``m4_graphs`` table).

  This design follows M4-D08: "M1 parsing complete → async trigger M4 build,
  no blocking of user response."
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

# Logger for M1 bridge events — used by M1's own logging system to track
# KG extraction status. structured (key=value) format for machine parsing.
logger = logging.getLogger(__name__)


async def on_parse_complete(kiln_engine: Any, parsed_doc: Any) -> dict[str, str]:
    """
    M1 parse-complete hook — asynchronously triggers KG entity extraction.

    WHAT:
      Called by M1's ``converter.py`` after successful document parsing.
      Uses ``asyncio.create_task()`` to fire off the KG extraction pipeline
      in the background so M1 can return immediately with a
      ``"kg_status": "building"`` indicator in the JSON response.

    WHY:
      The extraction pipeline (rule extractor + optional LLM extraction +
      merger + Kuzu insert) can take multiple seconds. M1 must not block
      the HTTP response on this work. The background task runs independently;
      its completion status is published to M2 RelationalDB (future
      enhancement) or logged for monitoring.

    Args:
        kiln_engine: The KGEngine instance that performs entity/relation
                     extraction and graph insertion.
        parsed_doc: A ``ParsedDocument`` instance with ``.doc_id`` and
                    ``.chunks`` (list[Chunk]) from M1's parser output.

    Returns:
        A dict with keys ``kg_status`` (always "building") and ``doc_id``
        that M1 can inject into its JSON response to the user.

    Example:
        >>> from contracts.document import ParsedDocument
        >>> from m4_kg.core.engine import KGEngine
        >>> engine = KGEngine()
        >>> response = await on_parse_complete(engine, parsed_doc)
        >>> response
        {'kg_status': 'building', 'doc_id': 'abc123'}
    """
    doc_id: str = getattr(parsed_doc, "doc_id", "unknown")
    chunks: list = getattr(parsed_doc, "chunks", [])

    # Fire-and-forget: launch extraction as a background task.
    # WHY: asyncio.create_task() returns immediately — the coroutine
    # runs concurrently with M1's response handler. M1's HTTP response
    # is not blocked waiting for KG extraction to finish.
    # The returned Task object is intentionally not awaited here.
    asyncio.create_task(kiln_engine.extract_entities(doc_id, chunks))

    # Log the event so M1's monitoring system can track KG build status.
    logger.info(
        "kg_extraction_triggered doc_id=%s chunk_count=%d",
        doc_id,
        len(chunks),
    )

    # Return status immediately for M1 to inject into its API response.
    return {
        "kg_status": "building",
        "doc_id": doc_id,
    }
