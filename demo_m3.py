# -*- coding: utf-8 -*-
"""
M3 end-to-end demo: M1 parse -> M2 store -> M3 retrieve.

Step 1: Parse a PDF with M1
Step 2: Create chunks and write to M2 (ChromaDB + Meilisearch)
Step 3: Search with M3 query analyzer
"""

import asyncio
import tempfile
from pathlib import Path

async def main():
    tmp_root = Path(tempfile.mkdtemp(prefix="m3_demo_"))
    print("=" * 60)
    print("  M3 Retrieval Engine -- End-to-End Demo")
    print("=" * 60)

    # =========================================================================
    # Step 1: Parse with M1
    # =========================================================================
    print("\n[1/4] M1: Parsing document...")
    from m1_parser.core.converter import convert, ParseOptions

    # Create a test document with marine content
    test_file = tmp_root / "test_dnv.html"
    test_file.write_text("""<html><body>
<h1>DNV Pt.4 Ch.3 -- Welding Procedures</h1>
<p>Welding procedure qualification for bulkheads requires preheating
to 150 degrees Celsius for steel grades EH36 and above. The interpass
temperature shall be maintained between 150C and 200C for all welding
positions.</p>
<p>For steel grade AH32, the minimum preheat temperature is 100C
for plate thickness up to 30mm. Above 30mm, the preheat shall be
increased to 125C.</p>
<p>Bilge pump capacity requirements: minimum 2.0 m3/h per 100mm
of main bilge pipe diameter. Emergency bilge pumps shall have
independent power supply.</p>
</body></html>""")

    opts = ParseOptions(backend="docling", output_dir=str(tmp_root / "output"))
    result = convert(str(test_file), opts)
    print(f"   Parsed: {result.page_count} pages, {result.table_count} tables")
    print(f"   Metadata: {result.metadata}")

    # =========================================================================
    # Step 2: Store in M2
    # =========================================================================
    print("\n[2/4] M2: Storing chunks in ChromaDB + Meilisearch...")
    from m2_storage.config import StorageConfig
    from m2_storage.factory import create_storage_manager

    # Create M2 config pointing at temp dirs
    config = StorageConfig()
    config.vector_store.chromadb.persist_dir = str(tmp_root / "data" / "chromadb")
    config.vector_store.chromadb.collection_name = "m3_demo"
    config.document_index.meilisearch.index_name = "m3_demo"
    config.relational_db.sqlite.path = str(tmp_root / "data" / "demo.db")
    config.file_store.local_fs.root_dir = str(tmp_root / "data" / "files")

    # Write a temp deploy.yaml for M2 factory
    import yaml
    cfg_path = tmp_root / "deploy.yaml"
    with open(cfg_path, "w") as f:
        yaml.dump({
            "deployment_mode": "personal",
            "storage": {
                "vector_store": {
                    "backend": "chromadb",
                    "chromadb": {"persist_dir": config.vector_store.chromadb.persist_dir, "collection_name": "m3_demo"},
                },
                "document_index": {
                    "backend": "meilisearch",
                    "meilisearch": {"host": "http://127.0.0.1:7700", "api_key": "", "index_name": "m3_demo"},
                },
                "relational_db": {
                    "backend": "sqlite",
                    "sqlite": {"path": config.relational_db.sqlite.path},
                },
                "file_store": {
                    "backend": "local_fs",
                    "local_fs": {"root_dir": config.file_store.local_fs.root_dir},
                },
            },
        }, f)

    mgr = create_storage_manager(str(cfg_path))
    await mgr.initialize()
    health = await mgr.health_check()
    print(f"   ChromaDB: {'OK' if health.get('vector_store') else 'UNAVAILABLE'}")
    print(f"   Meilisearch: {'OK' if health.get('doc_index') else 'UNAVAILABLE'}")

    # Create chunks from parsed markdown and insert into ChromaDB + Meilisearch
    from contracts.document import Chunk, DocumentMetadata, Domain, ClassificationSociety
    import hashlib

    # Split markdown into chunks
    lines = result.markdown.split("\n")
    chunks = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith("# "):
            continue
        chunk_id = hashlib.md5(line.encode()).hexdigest()[:12]
        chunks.append(Chunk(
            chunk_id=chunk_id,
            text=line,
            metadata=DocumentMetadata(
                source_filename="test_dnv.html",
                domain=Domain.STRUCTURE,
                classification_society=ClassificationSociety.DNV,
                regulation_name="Pt.4 Ch.3",
                version_year=2024,
                language="en",
            ),
            chunk_type="clause",
            position_in_document=i,
        ))

    # Generate simple embeddings and insert into ChromaDB
    def simple_embed(text, dim=256):
        h = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [(h >> i) & 0xFF for i in range(0, dim * 8, 8)]

    embeddings = [simple_embed(c.text) for c in chunks]
    ids = await mgr.vector_store.insert(chunks, embeddings)
    print(f"   ChromaDB: inserted {len(ids)} chunks")

    # Insert into Meilisearch (may fail if not running)
    try:
        await mgr.doc_index.index(chunks)
        print(f"   Meilisearch: indexed {len(chunks)} chunks")
    except Exception as e:
        print(f"   Meilisearch: UNAVAILABLE ({e})")

    # =========================================================================
    # Step 3: Search with M3
    # =========================================================================
    print("\n[3/4] M3: Query analysis demo...")
    from m3_retrieval.stages.query_analyzer import (
        analyze_query, _is_exact_match, _is_keyword_query
    )

    queries = [
        "DNV Pt.4 Ch.3 EH36 预热温度",
        "bilge pump capacity",
        "AH32 preheat temperature",
    ]

    for q in queries:
        qa = analyze_query(q)
        path = "fast" if _is_exact_match(q) else ("medium" if _is_keyword_query(q) else "full")
        print(f"\n   Query: {q!r}")
        print(f"     Society: {qa.classification_society or 'not detected'}")
        print(f"     Chapter: {qa.chapter_section or 'not detected'}")
        print(f"     Keywords: {qa.keywords}")
        print(f"     Semantic: {qa.semantic_query!r}")
        print(f"     Path: {path}")

        # Try actual retrieval through ChromaDB
        query_vec = simple_embed(qa.semantic_query)
        results = await mgr.vector_store.search(query_vec, top_k=3)
        if results:
            print(f"     ChromaDB results ({len(results)}):")
            for i, (chunk, score) in enumerate(results):
                print(f"       #{i+1} [score={score:.3f}] {chunk.text[:80]}...")
        else:
            print(f"     No ChromaDB results")

    # =========================================================================
    # Step 4: Summary
    # =========================================================================
    print("\n[4/4] Demo complete!")
    print(f"   Temp data: {tmp_root}")
    await mgr.close()


if __name__ == "__main__":
    asyncio.run(main())
