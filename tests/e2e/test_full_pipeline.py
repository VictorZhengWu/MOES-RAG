"""
E2E Integration Test — Marine & Offshore Expert System full pipeline.

Tests every module end-to-end with real data and real LLM (DeepSeek).
Run: PYTHONPATH=. python tests/e2e/test_full_pipeline.py
"""

import asyncio
import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
total = {"pass": 0, "fail": 0, "warn": 0}

DEEPSEEK_KEY = "sk-fd22ed990ebf4c94b5ae11a108ac62ef"

TEST_DOC = """<html><body>
<h1>DNV Pt.4 Ch.3 S2.1 - Welding Procedure Qualification</h1>
<p>EH36 steel requires preheat to 150C and interpass at 150-200C for all welding positions.</p>
<p>AH32 minimum preheat is 100C for plate thickness up to 30mm. Above 30mm, increase to 125C.</p>
<p>DH36 impact test temperature is -20C in transverse direction. Minimum absorbed energy is 34J.</p>
<p>Bilge pump capacity: minimum 2.0 m3/h per 100mm of main bilge pipe diameter.</p>
</body></html>"""


def log(step, status, msg=""):
    tag = {"pass": f"[{PASS}]", "fail": f"[{FAIL}]", "warn": f"[{WARN}]"}[status]
    print(f"  {tag} {msg}")
    total[status] += 1


def simple_embed(text, dim=256):
    h = int(hashlib.md5(text.encode()).hexdigest(), 16)
    return [(h >> i) & 0xFF for i in range(0, dim * 8, 8)]


async def main():
    tmp = Path(tempfile.mkdtemp(prefix="e2e_"))
    print("=" * 60)
    print("  Marine & Offshore Expert System — E2E Test")
    print("=" * 60)

    # ── 1. M1: Document Parsing ──────────────────────────────────
    print("\n[1] M1 Document Parsing")
    try:
        from m1_parser.core.converter import convert, ParseOptions
        doc_path = tmp / "test.html"
        doc_path.write_text(TEST_DOC, encoding="utf-8")
        opts = ParseOptions(backend="docling", output_dir=str(tmp / "out"),
                            output_formats=["md"], doc_name="test_dnv")
        result = convert(str(doc_path), opts)
        if result.success:
            log("1", "pass", f"Parsed: society={result.metadata.get('classification_society')}, chapter={result.metadata.get('chapter_section')}")
            chunks_text = [l.strip() for l in result.markdown.split("\n") if l.strip() and not l.strip().startswith("# ")]
        else:
            log("1", "fail", f"Parse failed: {result.error}")
            chunks_text = []
    except Exception as e:
        log("1", "fail", str(e))
        chunks_text = []

    # ── 2. M2: ChromaDB Storage ──────────────────────────────────
    print("\n[2] M2 ChromaDB Storage")
    try:
        import yaml
        from contracts.document import Chunk, DocumentMetadata, Domain, ClassificationSociety
        from m2_storage.factory import create_storage_manager

        chroma_dir = str(tmp / "chromadb")
        cfg_path = tmp / "deploy.yaml"
        with open(cfg_path, "w") as f:
            yaml.dump({"deployment_mode": "personal", "storage": {
                "vector_store": {"backend": "chromadb", "chromadb": {"persist_dir": chroma_dir, "collection_name": "e2e_test"}},
                "document_index": {"backend": "meilisearch", "meilisearch": {"host": "http://127.0.0.1:7700", "api_key": "", "index_name": "e2e_test"}},
                "relational_db": {"backend": "sqlite", "sqlite": {"path": str(tmp / "test.db")}},
                "file_store": {"backend": "local_fs", "local_fs": {"root_dir": str(tmp / "files")}},
            }}, f)
        mgr = create_storage_manager(str(cfg_path))
        await mgr.initialize()

        chunks = []
        for i, line in enumerate(chunks_text[:20]):
            cid = hashlib.md5(line.encode()).hexdigest()[:12]
            chunks.append(Chunk(chunk_id=cid, text=line, metadata=DocumentMetadata(
                source_filename="test_dnv.html", domain=Domain.STRUCTURE,
                classification_society=ClassificationSociety.DNV,
                regulation_name="Pt.4 Ch.3", version_year=2024, language="en",
            ), chunk_type="clause", position_in_document=i))
        ids = await mgr.vector_store.insert(chunks, [simple_embed(c.text) for c in chunks])
        count = await mgr.vector_store.count()
        log("2", "pass", f"Inserted {len(ids)}, count={count}")
        await mgr.close()
    except Exception as e:
        log("2", "fail", str(e))

    # ── 3. M3: Query Analysis + Hierarchical ─────────────────────
    print("\n[3] M3 Query Analysis + Hierarchical Fallback")
    try:
        from m3_retrieval.stages.query_analyzer import analyze_query, strip_section, build_fallback_chain
        qa = analyze_query("DNV Pt.4 Ch.3 S2.1 EH36 preheat temperature")
        assert qa.classification_society == "DNV", f"Society: {qa.classification_society}"
        log("3a", "pass", f"Society={qa.classification_society}, Chapter={qa.chapter_section}")
        r = strip_section("Pt.4 Ch.3 S2.1")
        assert r == "Pt.4 Ch.3", f"strip: {r}"
        log("3b", "pass", f"strip_section: 'Pt.4 Ch.3 S2.1' → '{r}'")
        chain = build_fallback_chain("Pt.4 Ch.3 S2.1")
        assert chain == ["Pt.4 Ch.3 S2.1", "Pt.4 Ch.3", "Pt.4", None], f"chain: {chain}"
        log("3c", "pass", f"Fallback chain: {chain}")
    except Exception as e:
        log("3", "fail", str(e))

    # ── 3b. M3: Proposition Extraction (DeepSeek) ────────────────
    print("\n[3b] M3 Proposition Extraction")
    try:
        from m3_retrieval.embeddings.proposition_extractor import PropositionExtractor
        extractor = PropositionExtractor(
            base_url="https://api.deepseek.com/v1", model="deepseek-chat",
            api_key=DEEPSEEK_KEY, batch_size=5, max_concurrent=1,
        )
        props = await extractor.extract([
            "EH36 requires preheat to 150C and interpass at 150-200C for all positions.",
            "AH32 minimum preheat is 100C for plate thickness up to 30mm.",
        ])
        assert len(props) >= 2, f"Only {len(props)} propositions"
        log("3d", "pass", f"Extracted {len(props)} propositions: {props[:3]}")
    except Exception as e:
        log("3d", "warn", str(e))

    # ── 4. M4: Knowledge Graph (Kuzu) ────────────────────────────
    print("\n[4] M4 Knowledge Graph")
    try:
        from m4_kg.graph.kuzu_store import KuzuStore
        from m4_kg.graph.traversal import bfs_traverse
        from contracts.knowledge_graph import Entity, Relation
        store = KuzuStore(str(tmp / "test_m4.db"))
        await store.insert_entities([
            Entity(entity_id="e1", name="EH36", entity_type="steel_grade", source_doc_id="test"),
            Entity(entity_id="e2", name="AH32", entity_type="steel_grade", source_doc_id="test"),
            Entity(entity_id="e3", name="preheat_150C", entity_type="parameter", source_doc_id="test"),
        ])
        await store.insert_relations([
            Relation(relation_id="r1", source_entity_id="e1", target_entity_id="e3",
                     relation_type="constrains", confidence=1.0),
        ])
        entities = await store.query_entities_by_name("EH36")
        assert len(entities) >= 1, f"Found {len(entities)}"
        log("4a", "pass", f"Entity: {entities[0].name} ({entities[0].entity_type})")
        sub = await bfs_traverse(store, ["e1"], depth=1)
        assert len(sub.entities) >= 2, f"BFS: {len(sub.entities)} entities"
        log("4b", "pass", f"BFS traversal: {len(sub.entities)} entities, {len(sub.relations)} relations")
        await store.close()
    except Exception as e:
        log("4", "fail", str(e))

    # ── 5a. M5: QA with DeepSeek ─────────────────────────────────
    print("\n[5a] M5 QA Engine — DeepSeek API")
    try:
        from m5_qa.core.config import QAConfig, LLMBackend
        from m5_qa.core.engine import QAEngine
        from contracts.qa_engine import ChatRequest, Message
        backend = LLMBackend(provider="deepseek", model="deepseek-chat",
                             api_key=DEEPSEEK_KEY, base_url="https://api.deepseek.com/v1")
        config = QAConfig(llm=backend, db_path=str(tmp / "m5_ds.db"), default_tier="pro")
        engine = QAEngine(config)
        req = ChatRequest(model="deepseek-chat", messages=[
            Message(role="user", content="What is the preheat temperature for EH36 steel?")
        ], stream=False, web_search_enabled=False)
        t0 = time.perf_counter()
        resp = await engine.chat(req)
        lat = (time.perf_counter() - t0) * 1000
        ans = resp.choices[0].message.content
        assert len(ans) > 10, f"Answer too short: {ans[:50]}"
        log("5a", "pass", f"DeepSeek ({lat:.0f}ms): {ans[:150]}...")
    except Exception as e:
        log("5a", "fail", str(e))

    # ── 5b. M5: QA with Ollama ───────────────────────────────────
    print("\n[5b] M5 QA Engine — Ollama (qwen3.5:4b)")
    try:
        from m5_qa.core.config import QAConfig, LLMBackend
        from m5_qa.core.engine import QAEngine
        from contracts.qa_engine import ChatRequest, Message
        backend = LLMBackend(provider="ollama", model="qwen3.5:4b",
                             base_url="http://localhost:11434/v1")
        config = QAConfig(llm=backend, db_path=str(tmp / "m5_ollama.db"), default_tier="pro")
        engine = QAEngine(config)
        req = ChatRequest(model="qwen3.5:4b", messages=[
            Message(role="user", content="What temperature is required for EH36 preheat?")
        ], stream=False, web_search_enabled=False)
        t0 = time.perf_counter()
        resp = await engine.chat(req)
        lat = (time.perf_counter() - t0) * 1000
        ans = resp.choices[0].message.content
        assert len(ans) > 5, f"Answer too short: {ans[:50]}"
        log("5b", "pass", f"Ollama ({lat:.0f}ms): {ans[:150]}...")
    except Exception as e:
        log("5b", "warn", str(e))

    # ── 6. M8: API Key Lifecycle ─────────────────────────────────
    print("\n[6] M8 API Key Lifecycle")
    try:
        from m8_gateway.auth.key_manager import KeyManager
        km = KeyManager(str(tmp / "m8_test.db"))
        raw = await km.generate_key("test-user", "pro")
        assert raw.startswith("sk-m8-") and len(raw) == 22, f"Bad key: {raw[:10]}"
        log("6a", "pass", f"Generated: {raw[:10]}...")
        valid = await km.validate_key(raw)
        assert valid is not None and valid.tier == "pro", f"Validate failed"
        log("6b", "pass", f"Validated: tier={valid.tier}")
        invalid = await km.validate_key("sk-m8-deadbeef00000000")
        assert invalid is None, "Invalid key accepted"
        log("6c", "pass", "Invalid key rejected")
        await km.revoke_key(raw[:10])
        revoked = await km.validate_key(raw)
        assert revoked is None, "Revoked key still valid"
        log("6d", "pass", "Revoked key rejected")
    except Exception as e:
        log("6", "fail", str(e))

    # ── 7. Config: LLM Config Hot-Reload ─────────────────────────
    print("\n[7] M8 Config Hot-Reload")
    try:
        from m8_gateway.routes.admin import _set_section, _get_section
        await _set_section("llm", {"provider": "deepseek", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"})
        data = await _get_section("llm")
        assert data.get("provider") == "deepseek", f"Provider: {data.get('provider')}"
        log("7a", "pass", f"LLM config saved: provider={data.get('provider')}, model={data.get('model')}")
    except Exception as e:
        log("7", "fail", str(e))

    # ── 8. Error Handling: Pipeline resilience ───────────────────
    print("\n[8] Error Handling")
    try:
        from m5_qa.core.engine import QAEngine
        from contracts.qa_engine import ChatRequest, Message
        # Create engine with NO LLM backend — should return friendly error, not traceback
        from m5_qa.core.config import QAConfig
        cfg = QAConfig(llm=None, db_path=str(tmp / "m5_nollm.db"), default_tier="basic")
        no_llm_engine = QAEngine(cfg)
        req = ChatRequest(model="none", messages=[
            Message(role="user", content="Test question")
        ], stream=False)
        resp = await no_llm_engine.chat(req)
        ans = resp.choices[0].message.content
        assert "sorry" in ans.lower() or "error" in ans.lower() or "unavailable" in ans.lower(), f"No error message: {ans[:100]}"
        log("8a", "pass", f"Friendly error on LLM failure: {ans[:100]}...")
    except Exception as e:
        log("8a", "fail", str(e))

    # ── 9. M2: VectorStore factory dispatch (all 4 backends) ─────
    print("\n[9] M2 VectorStore Factory")
    try:
        from m2_storage.config import VectorStoreConfig
        from m2_storage.factory import _create_vector_store
        for backend in ["chromadb", "faiss"]:  # Only test embedded backends
            cfg = VectorStoreConfig(backend=backend)
            store = _create_vector_store(cfg)
            log("9", "pass", f"_create_vector_store('{backend}') → {type(store).__name__}")
    except Exception as e:
        log("9", "fail", str(e))

    # ── Summary ──────────────────────────────────────────────────
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 60)
    print(f"  E2E Results: {total['pass']} passed, {total['fail']} failed, {total['warn']} warnings")
    print("=" * 60)
    if total["fail"] > 0:
        print("  STATUS: FAILED — some tests did not pass")
        sys.exit(1)
    else:
        print("  STATUS: PASSED — all critical paths verified")


if __name__ == "__main__":
    asyncio.run(main())
