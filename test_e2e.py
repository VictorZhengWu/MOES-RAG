#!/usr/bin/env python3
"""
End-to-end test script - Test complete chain M1→M2→M3→M4→M5→M8→M6
"""

import sys
import asyncio
import time

# Add paths
sys.path.insert(0, './contracts')
sys.path.insert(0, './m3-retrieval')
sys.path.insert(0, './m5-qa-engine')

from m5_qa import QAEngine
from m5_qa.core.config import QAConfig, LLMBackend
from contracts.qa_engine import ChatRequest, Message

async def test_deepseek_llm():
    """测试 DeepSeek API 集成"""
    print("=" * 60)
    print("测试 1: DeepSeek API 集成")
    print("=" * 60)

    # 配置 DeepSeek 后端
    llm_backend = LLMBackend(
        provider="deepseek",
        model="deepseek-chat",
        api_key="sk-fd22ed990ebf4c94b5ae11a108ac62ef",
        base_url="https://api.deepseek.com/v1"
    )
    config = QAConfig(
        llm=llm_backend,
        db_path="./data/m5_qa.db",
        system_prompt_id="system_en",
        web_search_engine="duckduckgo",
        retrieval_score_threshold=0.5
    )

    engine = QAEngine(config)

    # Test query
    query = "What is the welding procedure for EH36 steel in ship construction?"
    print(f"\nQuery: {query}")

    start_time = time.time()
    try:
        request = ChatRequest(
            model="deepseek-chat",
            messages=[Message(role="user", content=query)],
            temperature=0.7,
            max_tokens=1000
        )
        response = await engine.chat(request)
        elapsed = (time.time() - start_time) * 1000

        print(f"\nResponse time: {elapsed:.0f}ms")
        print(f"Answer: {response.choices[0].message.content}")
        print(f"\n[SUCCESS] DeepSeek API integration test passed")
        return True, elapsed

    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        print(f"\n[FAILED] Test failed: {e}")
        return False, elapsed

async def test_ollama_llm():
    """Test Ollama local LLM integration"""
    print("\n" + "=" * 60)
    print("Test 2: Ollama Local LLM Integration")
    print("=" * 60)

    # Configure Ollama backend
    llm_backend = LLMBackend(
        provider="ollama",
        model="qwen3.5:4b",
        base_url="http://localhost:11434/v1"
    )
    config = QAConfig(
        llm=llm_backend,
        db_path="./data/m5_qa.db",
        system_prompt_id="system_en",
        web_search_engine="duckduckgo",
        retrieval_score_threshold=0.5
    )

    engine = QAEngine(config)

    # Test query
    query = "What are the safety requirements for bilge pump systems?"
    print(f"\nQuery: {query}")

    start_time = time.time()
    try:
        request = ChatRequest(
            model="qwen3.5:4b",
            messages=[Message(role="user", content=query)],
            temperature=0.7,
            max_tokens=500
        )
        response = await engine.chat(request)
        elapsed = (time.time() - start_time) * 1000

        print(f"\nResponse time: {elapsed:.0f}ms ({elapsed/1000:.1f}s)")
        print(f"Answer: {response.choices[0].message.content}")
        print(f"\n[SUCCESS] Ollama local LLM integration test passed")
        return True, elapsed

    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        print(f"\n[FAILED] Test failed: {e}")
        return False, elapsed

async def test_llm_switching():
    """Test LLM hot switching"""
    print("\n" + "=" * 60)
    print("Test 3: LLM Hot Switching (DeepSeek → Ollama)")
    print("=" * 60)

    try:
        # First use DeepSeek
        llm_backend1 = LLMBackend(
            provider="deepseek",
            model="deepseek-chat",
            api_key="sk-fd22ed990ebf4c94b5ae11a108ac62ef",
            base_url="https://api.deepseek.com/v1"
        )
        config1 = QAConfig(
            llm=llm_backend1,
            db_path="./data/m5_qa.db"
        )

        engine1 = QAEngine(config1)
        request1 = ChatRequest(
            model="deepseek-chat",
            messages=[Message(role="user", content="Brief answer: What is EH36 steel?")],
            max_tokens=100
        )
        response1 = await engine1.chat(request1)
        print(f"\nDeepSeek answer: {response1.choices[0].message.content}")

        # Switch to Ollama
        llm_backend2 = LLMBackend(
            provider="ollama",
            model="qwen3.5:4b",
            base_url="http://localhost:11434/v1"
        )
        config2 = QAConfig(
            llm=llm_backend2,
            db_path="./data/m5_qa.db"
        )

        engine2 = QAEngine(config2)
        request2 = ChatRequest(
            model="qwen3.5:4b",
            messages=[Message(role="user", content="Brief answer: What is AH32 steel?")],
            max_tokens=100
        )
        response2 = await engine2.chat(request2)
        print(f"\nOllama answer: {response2.choices[0].message.content}")

        print(f"\n[SUCCESS] LLM hot switching test passed")
        return True

    except Exception as e:
        print(f"\n[FAILED] Test failed: {e}")
        return False

async def main():
    print("Marine & Offshore Expert System - End-to-End Test")
    print("=" * 60)

    # Test DeepSeek
    deepseek_success, deepseek_time = await test_deepseek_llm()

    # Test Ollama
    ollama_success, ollama_time = await test_ollama_llm()

    # Test hot switching
    switch_success = await test_llm_switching()

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    print(f"DeepSeek API: {'[PASS]' if deepseek_success else '[FAIL]'} ({deepseek_time:.0f}ms)")
    print(f"Ollama Local: {'[PASS]' if ollama_success else '[FAIL]'} ({ollama_time:.0f}ms)")
    print(f"LLM Hot Switch: {'[PASS]' if switch_success else '[FAIL]'}")

    if deepseek_success and ollama_success and switch_success:
        print(f"\n[SUCCESS] All tests passed! System is ready for release.")
    else:
        print(f"\n[WARNING] Some tests failed, need fixes.")

if __name__ == "__main__":
    asyncio.run(main())