# -*- coding: utf-8 -*-
"""
M2 Storage Abstraction Layer -- End-to-End Demo

Demonstrates all 4 backends working together:
  Vector Store  -> ChromaDB (insert + search with metadata filter)
  Document Index-> Meilisearch (index + full-text search)
  Relational DB -> SQLite (session + SELECT)
  File Store    -> LocalFS (put + get + list + metadata)

Run: python demo_m2.py
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path


def setup_demo_config(tmp_root: Path) -> Path:
    """Create a temporary deploy.yaml for the demo."""
    import yaml

    (tmp_root / "data" / "chromadb").mkdir(parents=True, exist_ok=True)
    (tmp_root / "data" / "files").mkdir(parents=True, exist_ok=True)

    config = {
        "deployment_mode": "personal",
        "storage": {
            "vector_store": {
                "backend": "chromadb",
                "chromadb": {
                    "persist_dir": str(tmp_root / "data" / "chromadb"),
                    "collection_name": "demo_collection",
                },
            },
            "document_index": {
                "backend": "meilisearch",
                "meilisearch": {
                    "host": os.environ.get("MEILISEARCH_URL", "http://127.0.0.1:7700"),
                    "api_key": "",
                    "index_name": "demo_index",
                },
            },
            "relational_db": {
                "backend": "sqlite",
                "sqlite": {"path": str(tmp_root / "data" / "demo.db")},
            },
            "file_store": {
                "backend": "local_fs",
                "local_fs": {"root_dir": str(tmp_root / "data" / "files")},
            },
        },
    }
    config_path = tmp_root / "deploy_demo.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path


async def main():
    tmp_root = Path(tempfile.mkdtemp(prefix="m2_demo_"))
    config_path = setup_demo_config(tmp_root)

    # Import from the copied m2_storage package
    from m2_storage.config import load_config
    from m2_storage.factory import create_storage_manager

    print("=" * 60)
    print("  M2 Storage Abstraction Layer -- Live Demo")
    print("=" * 60)

    # ---- 1. Load config ----
    print("\n[1/7] Loading deploy config...")
    cfg = load_config(str(config_path))
    print(f"   deployment_mode = {cfg.deployment_mode}")
    print(f"   vector_store    = {cfg.vector_store.backend}")
    print(f"   document_index  = {cfg.document_index.backend}")
    print(f"   relational_db   = {cfg.relational_db.backend}")
    print(f"   file_store      = {cfg.file_store.backend}")

    # ---- 2. Create StorageManager ----
    print("\n[2/7] Creating StorageManager...")
    manager = create_storage_manager(str(config_path))
    print(f"   vector_store  = {type(manager.vector_store).__name__}")
    print(f"   doc_index     = {type(manager.doc_index).__name__}")
    print(f"   relational_db = {type(manager.relational_db).__name__}")
    print(f"   file_store    = {type(manager.file_store).__name__}")

    # ---- 3. Initialize ----
    print("\n[3/7] Initializing all 4 backends...")
    await manager.initialize()
    print("   All backends initialized.")

    # ---- 4. Health Check ----
    print("\n[4/7] Health check:")
    health = await manager.health_check()
    for name, status in health.items():
        flag = "OK" if status else "!!"
        print(f"   [{flag}] {name}: {'healthy' if status else 'unhealthy'}")

    # ---- 5. Vector Store (ChromaDB) ----
    print("\n[5/7] Vector Store demo -- insert & search...")
    from contracts.document import Chunk, DocumentMetadata, Domain

    chunks = [
        Chunk(
            chunk_id="demo-chunk-1",
            text="DNV Pt.4 Ch.3 -- Welding procedure qualification for "
                 "bulkheads requires preheating to 150C for steel grades "
                 "EH36 and above.",
            metadata=DocumentMetadata(
                source_filename="dnv_pt4_ch3.pdf",
                domain=Domain.STRUCTURE,
            ),
            chunk_type="clause",
            position_in_document=0,
        ),
        Chunk(
            chunk_id="demo-chunk-2",
            text="ABS Pt.5B 3-2 -- Hull structural fire protection: A-60 "
                 "class division required between machinery spaces and "
                 "accommodation areas.",
            metadata=DocumentMetadata(
                source_filename="abs_pt5b.pdf",
                domain=Domain.STRUCTURE,
            ),
            chunk_type="clause",
            position_in_document=1,
        ),
        Chunk(
            chunk_id="demo-chunk-3",
            text="CCS Rules Ch.7 -- Pump capacity for bilge systems shall "
                 "be not less than 2.0 m3/h per 100 mm of main bilge pipe "
                 "diameter.",
            metadata=DocumentMetadata(
                source_filename="ccs_ch7.pdf",
                domain=Domain.MACHINERY,
            ),
            chunk_type="clause",
            position_in_document=0,
        ),
    ]

    def demo_embed(text: str, dim: int = 8) -> list[float]:
        """Simple hash-based embedding for demo purposes."""
        h = hash(text)
        return [((h >> i) & 0xFF) / 255.0 for i in range(0, dim * 8, 8)]

    embeddings = [demo_embed(c.text) for c in chunks]

    ids = await manager.vector_store.insert(chunks, embeddings)
    print(f"   Inserted {len(ids)} chunks: {ids}")
    print(f"   Total in collection: {await manager.vector_store.count()}")

    # Search
    query_text = "welding procedure preheating steel bulkheads"
    query_embedding = demo_embed(query_text)
    results = await manager.vector_store.search(query_embedding, top_k=3)

    print(f'\n   Query: "{query_text}"')
    print(f"   Results ({len(results)}):")
    for i, (chunk, score) in enumerate(results):
        print(f"     #{i+1} [score={score:.3f}] {chunk.text[:80]}...")

    # Search with domain filter
    results_filtered = await manager.vector_store.search(
        query_embedding, top_k=3, filters={"domain": "machinery"}
    )
    print(f"\n   Query + filter domain=machinery "
          f"({len(results_filtered)} results):")
    for i, (chunk, score) in enumerate(results_filtered):
        print(f"     #{i+1} [score={score:.3f}] "
              f"domain={chunk.metadata.domain.value} | {chunk.text[:60]}...")

    # ---- 6. File Store (LocalFS) ----
    print("\n[6/7] File Store demo -- put, get, list...")
    key = "regulations/dnv_rules_2024.pdf"
    content = b"%PDF-1.4\n% DNV Rules for Classification of Ships"
    stored = await manager.file_store.put(
        key, content,
        metadata={"author": "DNV", "edition": "2024", "pages": "450"}
    )
    print(f"   put('{key}', {len(content)} bytes) -> stored as '{stored}'")

    data = await manager.file_store.get(key)
    print(f"   get('{key}') -> {len(data)} bytes")
    print(f"   Preview: {data[:50].decode('utf-8', errors='replace')}")

    all_keys = await manager.file_store.list("regulations/")
    print(f"   list('regulations/') -> {all_keys}")

    # ---- 7. Relational DB (SQLite) ----
    print("\n[7/7] Relational DB demo -- session & query...")
    from sqlalchemy import text

    async with await manager.relational_db.get_session() as session:
        await session.execute(text(
            "CREATE TABLE IF NOT EXISTS demo_regulations ("
            "  id INTEGER PRIMARY KEY, "
            "  society TEXT, "
            "  part TEXT, "
            "  title TEXT"
            ")"
        ))
        await session.execute(text(
            "INSERT INTO demo_regulations (society, part, title) VALUES "
            "('DNV', 'Pt.4 Ch.3', 'Welding Procedures'),"
            "('ABS', 'Pt.5B', 'Fire Protection'),"
            "('CCS', 'Ch.7', 'Bilge Systems')"
        ))
        await session.commit()

        result = await session.execute(text(
            "SELECT society, part, title FROM demo_regulations ORDER BY society"
        ))
        rows = result.fetchall()
        print(f"   Created table, inserted 3 rows")
        print(f"   SELECT * FROM demo_regulations:")
        for row in rows:
            print(f"     {row[0]:6s} | {row[1]:12s} | {row[2]}")

    # ---- Summary ----
    print()
    print("=" * 60)
    print("  All 4 backends operational!")
    print(f"  Temp data: {tmp_root}")
    print("=" * 60)

    await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
