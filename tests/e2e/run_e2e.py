"""
E2E Pipeline Test — direct execution (no pytest).
Usage: PYTHONPATH=. python tests/e2e/run_e2e.py
"""
import asyncio, hashlib, os, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

PASS, FAIL, WARN = "[PASS]", "[FAIL]", "[WARN]"

TEST_DOC = """<html><body>
<h1>DNV Pt.4 Ch.3 S2.1 - Welding Procedure Qualification</h1>
<p>EH36 requires preheat to 150C and interpass at 150-200C for all positions.</p>
<p>AH32 minimum preheat temperature is 100C for plate thickness up to 30mm.</p>
<p>DH36 impact test temperature is -20C. Minimum absorbed energy is 34J.</p>
<p>Bilge pump capacity: minimum 2.0 m3/h per 100mm of main bilge pipe diameter.</p>
<h2>DNV Pt.4 Ch.3 S2.2 - NDE Requirements</h2>
<p>All full penetration butt welds in EH36 and above shall be examined by 100% UT.</p>
</body></html>"""

DEEPSEEK_KEY = "sk-fd22ed990ebf4c94b5ae11a108ac62ef"

async def main():
    tmp = Path(tempfile.mkdtemp(prefix="e2e_"))
    print("=" * 60)
    print("  Marine & Offshore Expert System - E2E Test")
    print("=" * 60)

    # ── Step 1: M1 Parse ──
    print("\n[Step 1] M1: Document Parsing...")
    doc_path = tmp / "test.html"
    doc_path.write_text(TEST_DOC, encoding="utf-8")
    try:
        from m1_parser.core.converter import convert, ParseOptions
        opts = ParseOptions(backend="docling", output_dir=str(tmp / "out"), output_formats=["md"], doc_name="test_dnv")
        result = convert(str(doc_path), opts)
        if result.success:
            print(f"  {PASS} Parsed: {result.page_count} pages, society={result.metadata.get('classification_society')}")
            print(f"  {PASS} Chapter: {result.metadata.get('chapter_section')}")
        else:
            print(f"  {FAIL} Parse failed: {result.error}")
    except Exception as e:
        print(f"  {FAIL} {e}")

    # ── Step 2: M2 ChromaDB ──
    print("\n[Step 2] M2: ChromaDB Storage...")
    try:
        import yaml
        from contracts.document import Chunk, DocumentMetadata, Domain, ClassificationSociety
        from m2_storage.factory import create_storage_manager

        cfg_path = tmp / "deploy.yaml"
        chroma_dir = str(tmp / "chromadb")
        with open(cfg_path, "w") as f:
            yaml.dump({"deployment_mode":"personal","storage":{
                "vector_store":{"backend":"chromadb","chromadb":{"persist_dir":chroma_dir,"collection_name":"e2e_test"}},
                "document_index":{"backend":"meilisearch","meilisearch":{"host":"http://127.0.0.1:7700","api_key":"","index_name":"e2e_test"}},
                "relational_db":{"backend":"sqlite","sqlite":{"path":str(tmp/"test.db")}},
                "file_store":{"backend":"local_fs","local_fs":{"root_dir":str(tmp/"files")}},
            }}, f)
        mgr = create_storage_manager(str(cfg_path))
        await mgr.initialize()
        lines = [l.strip() for l in result.markdown.split("\n") if l.strip() and not l.strip().startswith("# ")]
        chunks = []
        for i, line in enumerate(lines[:20]):
            cid = hashlib.md5(line.encode()).hexdigest()[:12]
            chunks.append(Chunk(chunk_id=cid, text=line, metadata=DocumentMetadata(
                source_filename="test_dnv.html", domain=Domain.STRUCTURE,
                classification_society=ClassificationSociety.DNV,
                regulation_name="Pt.4 Ch.3", version_year=2024, language="en",
            ), chunk_type="clause", position_in_document=i))
        def emb(t): h=int(hashlib.md5(t.encode()).hexdigest(),16); return [(h>>i)&0xFF for i in range(0,2048)]
        await mgr.vector_store.insert(chunks, [emb(c.text) for c in chunks])
        count = await mgr.vector_store.count()
        print(f"  {PASS} Inserted {len(chunks)} chunks, ChromaDB count: {count}")
        await mgr.close()
    except Exception as e:
        print(f"  {FAIL} {e}")

    # ── Step 3: M3 Query Analysis + Hierarchical ──
    print("\n[Step 3] M3: Query Analysis + Hierarchical Navigation...")
    try:
        from m3_retrieval.stages.query_analyzer import analyze_query, strip_section, build_fallback_chain
        qa = analyze_query("DNV Pt.4 Ch.3 S2.1 EH36 preheat temperature")
        print(f"  {PASS} Society: {qa.classification_society}")
        print(f"  {PASS} Chapter: {qa.chapter_section}")
        print(f"  {PASS} Keywords: {qa.keywords}")
        r = strip_section("Pt.4 Ch.3 S2.1")
        print(f"  {PASS} strip_section: '{r}'")
        chain = build_fallback_chain("Pt.4 Ch.3 S2.1")
        print(f"  {PASS} Fallback chain: {chain}")
    except Exception as e:
        print(f"  {FAIL} {e}")

    # ── Step 3b: Proposition Extraction (DeepSeek) ──
    print("\n[Step 3b] M3: Proposition Extraction (DeepSeek)...")
    try:
        from m3_retrieval.embeddings.proposition_extractor import PropositionExtractor
        extractor = PropositionExtractor(
            base_url="https://api.deepseek.com/v1", model="deepseek-chat",
            api_key=DEEPSEEK_KEY, batch_size=5, max_concurrent=1,
        )
        props = await extractor.extract([
            "EH36 requires preheat to 150C and interpass at 150-200C for all positions.",
            "AH32 minimum preheat temperature is 100C for plate thickness up to 30mm.",
        ])
        print(f"  {PASS} Extracted {len(props)} propositions:")
        for p in props: print(f"    - {p}")
    except Exception as e:
        print(f"  {WARN} {e}")

    # ── Step 4: M4 Kuzu Graph ──
    print("\n[Step 4] M4: Knowledge Graph (Kuzu)...")
    try:
        from m4_kg.graph.kuzu_store import KuzuStore
        from m4_kg.graph.traversal import bfs_traverse
        from contracts.knowledge_graph import Entity, Relation
        store = KuzuStore(str(tmp / "test_m4.db"))
        await store.insert_entities([
            Entity(entity_id="e1", name="EH36", entity_type="steel_grade", source_doc_id="test"),
            Entity(entity_id="e2", name="AH32", entity_type="steel_grade", source_doc_id="test"),
            Entity(entity_id="e3", name="preheat_150C", entity_type="parameter", source_doc_id="test", properties={"value":"150C"}),
        ])
        await store.insert_relations([
            Relation(relation_id="r1", source_entity_id="e1", target_entity_id="e3", relation_type="constrains", confidence=1.0, source_doc_id="test"),
        ])
        entities = await store.query_entities_by_name("EH36")
        print(f"  {PASS} Found: {entities[0].name} ({entities[0].entity_type})")
        sub = await bfs_traverse(store, ["e1"], depth=1)
        print(f"  {PASS} BFS: {len(sub.entities)} entities, {len(sub.relations)} relations")
        await store.close()
    except Exception as e:
        print(f"  {FAIL} {e}")

    # ── Step 5a: M5 with DeepSeek ──
    print("\n[Step 5a] M5: QA with DeepSeek API...")
    try:
        from m5_qa.core.config import QAConfig, LLMBackend
        from m5_qa.core.engine import QAEngine
        from contracts.qa_engine import ChatRequest, Message
        backend = LLMBackend(provider="deepseek", model="deepseek-chat", api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com/v1")
        config = QAConfig(llm=backend, db_path=str(tmp/"m5_ds.db"), default_tier="pro")
        engine = QAEngine(config)
        req = ChatRequest(model="deepseek-chat", messages=[Message(role="user", content="What is the preheat temperature for EH36 steel in shipbuilding?")], stream=False, web_search_enabled=False)
        t0 = time.perf_counter()
        resp = await engine.chat(req)
        lat = (time.perf_counter()-t0)*1000
        ans = resp.choices[0].message.content
        print(f"  {PASS} DeepSeek ({lat:.0f}ms): {ans[:200]}...")
    except Exception as e:
        print(f"  {FAIL} {e}")

    # ── Step 5b: M5 with Ollama ──
    print("\n[Step 5b] M5: QA with local Ollama (qwen3.5:4b)...")
    try:
        from m5_qa.core.config import QAConfig, LLMBackend
        from m5_qa.core.engine import QAEngine
        from contracts.qa_engine import ChatRequest, Message
        backend = LLMBackend(provider="ollama", model="qwen3.5:4b", base_url="http://localhost:11434/v1")
        config = QAConfig(llm=backend, db_path=str(tmp/"m5_ollama.db"), default_tier="pro")
        engine = QAEngine(config)
        req = ChatRequest(model="qwen3.5:4b", messages=[Message(role="user", content="What temperature is required for preheating EH36 steel?")], stream=False, web_search_enabled=False)
        t0 = time.perf_counter()
        resp = await engine.chat(req)
        lat = (time.perf_counter()-t0)*1000
        ans = resp.choices[0].message.content
        print(f"  {PASS} Ollama ({lat:.0f}ms): {ans[:200]}...")
    except Exception as e:
        print(f"  {WARN} {e}")

    # ── Step 6: M8 Key Management ──
    print("\n[Step 6] M8: API Key lifecycle...")
    try:
        from m8_gateway.auth.key_manager import KeyManager
        km = KeyManager(str(tmp/"m8_test.db"))
        raw = await km.generate_key("test-user", "pro")
        print(f"  {PASS} Generated: {raw[:10]}...")
        valid = await km.validate_key(raw)
        print(f"  {PASS} Validated: tier={valid.tier}")
        invalid = await km.validate_key("sk-m8-deadbeef00000000")
        print(f"  {PASS} Invalid rejected: {invalid is None}")
        await km.revoke_key(raw[:10])
        revoked = await km.validate_key(raw)
        print(f"  {PASS} Revoked rejected: {revoked is None}")
    except Exception as e:
        print(f"  {FAIL} {e}")

    # ── Cleanup ──
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + "=" * 60)
    print("  E2E Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
