# Phase 3 — 命题式索引（Propositional Indexing）

> **RAG 技术**：命题式索引 (#12) | **改动范围**：M3 + M2 | **改动量**：中
> 每条事实单独索引——"EH36 预热 150°C when t≤50mm"，不是 200 字的段落

---

## 1. 核心思路

当前检索 → 返回 200 字 chunk → LLM 自己找答案。

```
用户: "EH36 预热温度是多少？"
  → M3 返回: "Welding procedure qualification for bulkheads requires
    preheating to 150 degrees Celsius for steel grades EH36 and above.
    The interpass temperature shall be maintained between 150C and
    200C for all welding positions."
  → LLM 必须读 200 字，找 "150" 和 "EH36"

改为命题式索引后：

用户: "EH36 预热温度是多少？"
  → M3 返回: "EH36 requires preheat to 150°C when t≤50mm"
  → LLM 直接看到答案
```

## 2. 存储策略

新 ChromaDB collection `marine_rag_propositions`，与 `marine_rag_chunks` 并行：

```
ChromaDB
  ├── marine_rag_chunks (现有，不改)
  └── marine_rag_propositions (新增)
        ├── prop_001: "EH36 requires preheat to 150°C when t≤50mm"
        ├── prop_002: "AH32 requires preheat to 100°C when t≤30mm"
        └── ...
```

每个 proposition 嵌入为 1024 维向量。元数据保留 source_doc_id, classification_society, chapter_section。

## 3. 建索引管线

在 M1 解析完成后异步触发（复用 M4 的 `on_parse_complete` 模式）：

```
M1 parse 完成
  → on_parse_complete() hook
    → M4: entity/relation extraction (已有)
    → NEW: PropositionExtractor.extract(chunks) → propositions → ChromaDB
```

## 4. LLM 提取

每批 10 个 chunks 送入 LLM，Prompt 要求输出原子事实：

```
For each sentence in the text below, extract self-contained atomic facts
that could answer a specific question. Each fact must be understandable
without additional context — include the subject, the requirement, and
any numeric values.

Rules:
- One fact per line
- Include the technical subject (e.g. "EH36 steel" not "it")
- Include numeric values with units (e.g. "150°C" not "high temperature")
- Skip headings, introductions, and table of contents
- If a sentence contains multiple facts, split them
- Output ONLY the facts, one per line, no markdown, no numbering

Example:
Input: "EH36 requires preheat to 150°C and interpass at 150-200°C for all positions."
Output:
EH36 steel requires preheat to 150°C
EH36 steel requires interpass temperature between 150°C and 200°C for all welding positions

Text:
{chunk_text}
```

## 5. 检索融合

M3 的 `parallel_retrieve` 搜三个 source：

```python
# M5 retriever.py
async def parallel_retrieve(query, ...):
    m3_chunks = await m3.retrieve(query)       # chunks (现有)
    m4_graph = await m4.graph_search(query)     # graph (现有)
    m3_props = await m3.retrieve_propositions(query)  # NEW: propositions
    return RetrievalContext(
        chunks=m3_chunks, graph=m4_graph,
        propositions=m3_props,  # NEW
    )
```

fusion.py 将 propositions 作为独立的上下文字段：

```
## Document Facts (propositions)
- EH36 steel requires preheat to 150°C
- EH36 steel requires interpass temperature between 150°C and 200°C
...
```

## 6. 改动清单

| 文件 | 改动 |
|------|------|
| `m3_retrieval/m3_retrieval/embeddings/proposition_extractor.py` | **新建** — LLM 命题提取 |
| `m3_retrieval/m3_retrieval/core/pipeline.py` | `retrieve_propositions()` 方法 |
| `m3_retrieval/m3_retrieval/core/config.py` | `propositions_collection` 配置 |
| `m5_qa/m5_qa/context/retriever.py` | 并行搜 propositions |
| `m5_qa/m5_qa/context/fusion.py` | propositions 格式化 |
| `m5_qa/m5_qa/context/retriever.py` | `RetrievalContext.propositions` 字段 |
| `m3_retrieval/tests/test_proposition_extractor.py` | **新建** — 3 个测试 |
| `m5_qa/tests/test_retriever.py` | +1 测试 |

## 7. 测试

1. `test_extract_propositions` — mock LLM 返回事实列表 → 正确解析
2. `test_empty_chunks` — 空 chunks → 返回空列表
3. `test_propositions_in_context` — propositions 出现在 fusion 格式化输出中

---

*设计结束。开始实现。*
