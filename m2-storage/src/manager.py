"""
StorageManager -- unified lifecycle management for M2 backends.

WHY: Upper modules (M1, M3, M4, M5) need a single object to initialize,
health-check, and shut down all four storage backends. The Manager owns
the lifecycle but does NOT proxy method calls -- consumers call
manager.vector_store.search() directly. This keeps the Manager thin
and avoids duplicating every Protocol method as a pass-through.

Each backend is accessed as an attribute on the manager:
  - manager.vector_store  -> VectorStore
  - manager.doc_index     -> DocumentIndex
  - manager.relational_db -> RelationalDB
  - manager.file_store    -> FileStore

Lifecycle operations (initialize, health_check, close) run all four
backends concurrently via asyncio.gather to minimize startup/shutdown
latency. Individual backend failures are logged but do not prevent
other backends from completing their lifecycle transitions.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Holds references to all 4 storage backends and manages their lifecycle.

    Upper modules access backends directly as attributes:
        manager.vector_store.search(...)
        manager.doc_index.search(...)
        manager.relational_db.get_session()
        manager.file_store.get(...)

    The Manager is responsible for:
    - initialize(): start all backends concurrently
    - health_check(): verify all backends are healthy
    - close(): gracefully shut down all backends
    """

    def __init__(self, *, vector_store, doc_index, relational_db, file_store):
        """
        Inject 4 backend instances.

        WHY keyword-only arguments: callers must be explicit about which
        backend goes where. Positional args would invite ordering bugs
        where vector_store and doc_index parameters were swapped.
        """
        self.vector_store = vector_store
        self.doc_index = doc_index
        self.relational_db = relational_db
        self.file_store = file_store

    async def initialize(self) -> None:
        """
        Initialize all 4 backends concurrently.

        WHY asyncio.gather with return_exceptions=True: sequential init
        of 4 backends could take several seconds. Concurrent init cuts
        startup time to roughly the slowest single backend. Individual
        failures are logged but do not prevent other backends from
        initializing -- a user might tolerate a broken file store but
        still need vector search to work.
        """
        results = await asyncio.gather(
            self.vector_store.initialize(),
            self.doc_index.initialize(),
            self.relational_db.initialize(),
            self.file_store.initialize(),
            return_exceptions=True,
        )
        names = ["vector_store", "doc_index", "relational_db", "file_store"]
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                logger.error(
                    "Failed to initialize %s: %s", name, result
                )
            else:
                logger.info("Initialized %s successfully", name)

    async def health_check(self) -> dict[str, bool]:
        """
        Check the health of all 4 backends concurrently.

        Returns a dict mapping backend name to healthy/unhealthy status.
        A failed health check does not raise -- it returns False for
        that backend so monitoring systems can surface which specific
        component is degraded.

        Returns:
            dict with keys: "vector_store", "doc_index", "relational_db",
            "file_store", each mapped to a boolean health status.
        """
        results = await asyncio.gather(
            self.vector_store.health_check(),
            self.doc_index.health_check(),
            self.relational_db.health_check(),
            self.file_store.health_check(),
            return_exceptions=True,
        )
        names = ["vector_store", "doc_index", "relational_db", "file_store"]
        return {
            name: (result if isinstance(result, bool) else False)
            for name, result in zip(names, results)
        }

    async def close(self) -> None:
        """
        Gracefully close all 4 backend connections concurrently.

        Each backend's close() is called even if others raise, ensuring
        we never leak connections. Exceptions are returned rather than
        raised so that all backends get a chance to close.

        WHY logging individual failures: if a backend fails to close
        cleanly, the operator needs to know which specific backend
        leaked resources. Silent failures during shutdown are
        indistinguishable from successful shutdowns and lead to
        resource exhaustion over repeated deploy cycles.
        """
        results = await asyncio.gather(
            self.vector_store.close(),
            self.doc_index.close(),
            self.relational_db.close(),
            self.file_store.close(),
            return_exceptions=True,
        )
        names = ["vector_store", "doc_index", "relational_db", "file_store"]
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                logger.error(
                    "Failed to close %s: %s", name, result
                )
