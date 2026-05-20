# -*- coding: utf-8 -*-
"""
M2 — Storage Abstraction Layer.

Provides a unified storage interface with pluggable backends
selected at deploy time via deploy.yaml. Upper modules (M1/M3/M4/M5)
interact with storage exclusively through StorageManager and the
Protocols defined in contracts/storage.py.

Usage:
    from m2_storage import create_storage_manager

    manager = await create_storage_manager("deploy.yaml")
    await manager.initialize()

    # Use backends directly via Protocol interfaces
    results = await manager.vector_store.search(query_vec, top_k=10)
    chunks  = await manager.doc_index.search("keyword", top_k=5)
    async with manager.relational_db.get_session() as session:
        ...
    file_data = await manager.file_store.get("path/to/file.pdf")

    await manager.close()

Backend selection (Personal mode defaults):
    Vector Store   → ChromaDB (embedded, persistent)
    Document Index → Meilisearch (BM25 full-text)
    Relational DB  → SQLite (WAL mode, async)
    File Store     → Local filesystem
"""

__version__ = "0.1.0"

from .factory import create_storage_manager
from .manager import StorageManager

__all__ = [
    "StorageManager",
    "create_storage_manager",
    "__version__",
]
