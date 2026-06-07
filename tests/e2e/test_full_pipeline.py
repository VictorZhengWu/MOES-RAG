"""
E2E Integration Test — Marine & Offshore Expert System full pipeline.
Run: DEEPSEEK_API_KEY=sk-... PYTHONPATH=. python tests/e2e/test_full_pipeline.py
"""

import asyncio, hashlib, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
total = {"pass": 0, "fail": 0, "warn": 0}
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

def log(step, status, msg=""):
    tag = {"pass": f"[{PASS}]", "fail": f"[{FAIL}]", "warn": f"[{WARN}]"}[status]
    print(f"  {tag} {msg}")
    total[status] += 1

def simple_embed(text, dim=256):
    h = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [(h >> i) & 0xFF for i in range(0, dim * 8, 8)]

TEST_DOC = """<html><body>
<h1>DNV Pt.4 Ch.3 S2.1 - Welding Procedure Qualification</h1>
<p>EH36 steel requires preheat to 150C and interpass at 150-200C for all positions.</p>
<p>AH32 minimum preheat is 100C for plate up to 30mm. Above 30mm, increase to 125C.</p>
<p>Bilge pump capacity: minimum 2.0 m3/h per 100mm of main bilge pipe diameter.</p>
</body></html>"""


async def main():
    tmp = Path(tempfile.mkdtemp(prefix="e2e_"))
    print("=" * 60)
    print("  Marine & Offshore Expert System — E2E Test")
    print("=" * 60)

    # ── 1. M1 ──
    print("\n[1] M1 Document Parsing")
    try:
        from m1_parser.core.converter import convert, ParseOptions
        (tmp / "test.html").write_text(TEST_DOC, encoding="utf-8")
        opts = ParseOptions(backend="docling", output_dir=str(tmp/"out"), output_formats=["md"], doc_name="test_dnv")
        r = convert(str(tmp/"test.html"), opts)
        if r.success:
            log("1","pass",f"society={r.metadata.get('classification_society')}, chapter={r.metadata.get('chapter_section')}")
            ct = [l.strip() for l in r.markdown.split("\n") if l.strip() and not l.strip().startswith("# ")]
        else:
            log("1","fail",r.error); ct=[]
    except Exception as e:
        log("1","fail",str(e)); ct=[]

    # ── 2. M2 ──
    print("\n[2] M2 ChromaDB Storage")
    try:
        import yaml
        from contracts.document import Chunk, DocumentMetadata, Domain, ClassificationSociety
        from m2_storage.factory import create_storage_manager
        cd = str(tmp/"chromadb")
        with open(tmp/"deploy.yaml","w") as f:
            yaml.dump({"deployment_mode":"personal","storage":{
                "vector_store":{"backend":"chromadb","chromadb":{"persist_dir":cd,"collection_name":"e2e_test"}},
                "document_index":{"backend":"meilisearch","meilisearch":{"host":"http://127.0.0.1:7700","api_key":"","index_name":"e2e_test"}},
                "relational_db":{"backend":"sqlite","sqlite":{"path":str(tmp/"test.db")}},
                "file_store":{"backend":"local_fs","local_fs":{"root_dir":str(tmp/"files")}},
            }},f)
        mgr = create_storage_manager(str(tmp/"deploy.yaml"))
        await mgr.initialize()
        chunks = [Chunk(chunk_id=hashlib.md5(line.encode()).hexdigest()[:12], text=line, metadata=DocumentMetadata(
            source_filename="test_dnv.html", domain=Domain.STRUCTURE,
            classification_society=ClassificationSociety.DNV, regulation_name="Pt.4 Ch.3",
            version_year=2024, language="en"), chunk_type="clause", position_in_document=i)
            for i, line in enumerate(ct[:20])]
        ids = await mgr.vector_store.insert(chunks, [simple_embed(c.text) for c in chunks])
        count = await mgr.vector_store.count()
        log("2","pass",f"Inserted {len(ids)}, count={count}")
        await mgr.close()
    except Exception as e:
        log("2","fail",str(e))

    # ── 3. M3 Query Analysis ──
    print("\n[3] M3 Query Analysis + Hierarchical Fallback")
    try:
        from m3_retrieval.stages.query_analyzer import analyze_query, strip_section, build_fallback_chain
        qa = analyze_query("DNV Pt.4 Ch.3 S2.1 EH36 preheat temperature")
        assert qa.classification_society == "DNV"
        log("3a","pass",f"Society={qa.classification_society}, Chapter={qa.chapter_section}")
        r = strip_section("Pt.4 Ch.3 S2.1")
        assert r == "Pt.4 Ch.3"
        log("3b","pass",f"strip: 'Pt.4 Ch.3 S2.1' -> '{r}'")
        chain = build_fallback_chain("Pt.4 Ch.3 S2.1")
        assert chain == ["Pt.4 Ch.3 S2.1","Pt.4 Ch.3","Pt.4",None]
        log("3c","pass",f"Fallback: {chain}")
    except Exception as e:
        log("3","fail",str(e))

    # ── 3b. Proposition Extraction ──
    print("\n[3b] M3 Proposition Extraction")
    if not DEEPSEEK_KEY:
        log("3d","warn","Skipped — DEEPSEEK_API_KEY not set")
    else:
        try:
            from m3_retrieval.embeddings.proposition_extractor import PropositionExtractor
            ext = PropositionExtractor(base_url="https://api.deepseek.com/v1",model="deepseek-chat",api_key=DEEPSEEK_KEY,batch_size=5,max_concurrent=1)
            props = await ext.extract(["EH36 requires preheat to 150C.","AH32 minimum preheat is 100C."])
            assert len(props) >= 2
            log("3d","pass",f"Extracted {len(props)} propositions: {props}")
        except Exception as e:
            log("3d","warn",str(e))

    # ── 4. M4 Kuzu ──
    print("\n[4] M4 Knowledge Graph")
    try:
        from m4_kg.graph.kuzu_store import KuzuStore
        from m4_kg.graph.traversal import bfs_traverse
        from contracts.knowledge_graph import Entity, Relation
        store = KuzuStore(str(tmp/"test_m4.db"))
        await store.insert_entities([
            Entity(entity_id="e1",name="EH36",entity_type="steel_grade",source_doc_id="test"),
            Entity(entity_id="e2",name="AH32",entity_type="steel_grade",source_doc_id="test"),
            Entity(entity_id="e3",name="preheat_150C",entity_type="parameter",source_doc_id="test"),
        ])
        await store.insert_relations([Relation(relation_id="r1",source_entity_id="e1",target_entity_id="e3",relation_type="constrains",confidence=1.0)])
        ents = await store.query_entities_by_name("EH36")
        assert len(ents) >= 1
        log("4a","pass",f"Entity: {ents[0].name} ({ents[0].entity_type})")
        sub = await bfs_traverse(store,["e1"],depth=1)
        assert len(sub.entities) >= 2
        log("4b","pass",f"BFS: {len(sub.entities)} entities, {len(sub.relations)} relations")
        await store.close()
    except Exception as e:
        log("4","fail",str(e))

    # ── 5a. M5 DeepSeek ──
    print("\n[5a] M5 QA — DeepSeek API")
    if not DEEPSEEK_KEY:
        log("5a","warn","Skipped — DEEPSEEK_API_KEY not set")
    else:
        try:
            from m5_qa.core.config import QAConfig, LLMBackend
            from m5_qa.core.engine import QAEngine
            from contracts.qa_engine import ChatRequest, Message
            be = LLMBackend(provider="deepseek",model="deepseek-chat",api_key=DEEPSEEK_KEY,base_url="https://api.deepseek.com/v1")
            cfg = QAConfig(llm=be,db_path=str(tmp/"m5_ds.db"),default_tier="pro")
            engine = QAEngine(cfg)
            req = ChatRequest(model="deepseek-chat",messages=[Message(role="user",content="What is EH36 preheat temperature?")],stream=False)
            t0=time.perf_counter(); resp=await engine.chat(req); lat=(time.perf_counter()-t0)*1000
            ans=resp.choices[0].message.content
            assert len(ans)>10
            log("5a","pass",f"DeepSeek ({lat:.0f}ms): {ans[:150]}...")
        except Exception as e:
            log("5a","fail",str(e))

    # ── 6. M8 Keys ──
    print("\n[6] M8 API Key Lifecycle")
    try:
        from m8_gateway.auth.key_manager import KeyManager
        km = KeyManager(str(tmp/"m8_test.db"))
        raw = await km.generate_key("test-user","pro")
        assert raw.startswith("sk-m8-") and len(raw)==22
        log("6a","pass",f"Generated: {raw[:10]}...")
        v = await km.validate_key(raw)
        assert v and v.tier=="pro"
        log("6b","pass",f"Validated: tier={v.tier}")
        assert await km.validate_key("sk-m8-deadbeef00000000") is None
        log("6c","pass","Invalid key rejected")
        await km.revoke_key(raw[:10])
        assert await km.validate_key(raw) is None
        log("6d","pass","Revoked key rejected")
    except Exception as e:
        log("6","fail",str(e))

    # ── 7. Config ──
    print("\n[7] M8 Config Hot-Reload")
    try:
        from m8_gateway.routes.admin import _set_section, _get_section
        await _set_section("llm",{"provider":"deepseek","model":"deepseek-chat","base_url":"https://api.deepseek.com/v1"})
        d = await _get_section("llm")
        assert d.get("provider")=="deepseek"
        log("7","pass",f"LLM config: provider={d.get('provider')}, model={d.get('model')}")
    except Exception as e:
        log("7","fail",str(e))

    # ── 8. Error Handling ──
    print("\n[8] Error Handling — LLM Failure")
    try:
        from m5_qa.core.engine import QAEngine
        from m5_qa.core.config import QAConfig
        from contracts.qa_engine import ChatRequest, Message
        cfg = QAConfig(llm=None,db_path=str(tmp/"m5_nollm.db"),default_tier="basic")
        engine = QAEngine(cfg)
        resp = await engine.chat(ChatRequest(model="none",messages=[Message(role="user",content="Test")],stream=False))
        ans = resp.choices[0].message.content
        assert "sorry" in ans.lower() or "error" in ans.lower() or "unavailable" in ans.lower()
        log("8","pass",f"Friendly error: {ans[:100]}...")
    except Exception as e:
        log("8","fail",str(e))

    # ── 9. Factory ──
    print("\n[9] M2 VectorStore Factory")
    try:
        from m2_storage.config import VectorStoreConfig
        from m2_storage.factory import _create_vector_store
        for be in ["chromadb","faiss"]:
            store = _create_vector_store(VectorStoreConfig(backend=be))
            log("9","pass",f"_create_vector_store('{be}') -> {type(store).__name__}")
    except Exception as e:
        log("9","fail",str(e))

    # ── Summary ──
    import shutil; shutil.rmtree(tmp,ignore_errors=True)
    print("\n"+"="*60)
    print(f"  E2E Results: {total['pass']} passed, {total['fail']} failed, {total['warn']} warnings")
    print("="*60)
    if total["fail"]>0:
        print("  STATUS: FAILED"); sys.exit(1)
    else:
        print("  STATUS: PASSED")

if __name__=="__main__":
    asyncio.run(main())
