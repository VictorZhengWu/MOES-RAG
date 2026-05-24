# M3 检索引擎 — 详细设计规范

> **日期**：2026-05-24 | **状态**：待审批
> **依赖**：contracts/ (00010), M2 (00050), M1 (00060)
> **定位**：Layer 2 (Processing)，系统的核心检索中枢

---

## 1. 模块定位

M3 是系统的检索中枢。它接收来自 M5（问答引擎）的查询请求，通过混合检索管线从 M2 存储中找出最相关的文档块，返回给 M5 用于生成答案。

**核心原则**：

- **精准优先** — 元数据过滤优先于语义检索，关键词精确匹配优先于向量模糊匹配
- **管道化设计** — 6 阶段管线：查询分析 → 双路检索 → 融合 → 重排序 → 上下文扩展 → 输出
- **单职责** — 只做检索，不做查询分解（M5 负责），不做答案生成（M5 负责）
- **与 LLM 解耦** — M3 不依赖 LLM，HyDE 通过外部调用微调嵌入模型实现

---

## 2. 模块目录结构

```
m3-retrieval/
├── m3_retrieval/
│   ├── __init__.py              # 公开 API 导出
│   ├── core/
│   │   ├── __init__.py
│   │   ├── engine.py            # 检索引擎主入口（RemovalEngine）
│   │   ├── pipeline.py          # 6 阶段管线编排
│   │   ├── config.py            # 配置管理：模型选择、融合参数
│   │   └── metrics.py           # 检索质量度量（MRR, NDCG, Recall@k）
│   │
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── query_analyzer.py    # 阶段 1：查询解析 + 元数据提取 + 关键词分离
│   │   ├── dense_retriever.py   # 阶段 2a：向量检索（ChromaDB）
│   │   ├── sparse_retriever.py  # 阶段 2b：全文检索（Meilisearch BM25）
│   │   ├── fusion.py            # 阶段 3：RRF/加权/混合融合
│   │   ├── reranker.py          # 阶段 4：Cross-Encoder 重排序
│   │   └── context_expander.py  # 阶段 5：父文档上下文扩展
│   │
│   ├── embeddings/
│   │   ├── __init__.py
│   │   ├── embedder.py          # 嵌入模型封装（BGE-M3/GTE-Qwen2）
│   │   └── hyde.py              # HyDE 文档生成（可选）
│   │
│   └── integration/
│       ├── __init__.py
│       ├── m2_client.py          # M2 存储客户端（VectorStore + DocumentIndex）
│       └── m5_protocol.py        # M5 调用接口（RetrievalEngineProtocol）
│
├── tests/
│   ├── conftest.py
│   ├── test_query_analyzer.py
│   ├── test_dense_retriever.py
│   ├── test_sparse_retriever.py
│   ├── test_fusion.py
│   ├── test_reranker.py
│   ├── test_context_expander.py
│   ├── test_pipeline.py
│   ├── test_engine.py
│   └── test_metrics.py
│
├── requirements.txt
└── pyproject.toml
```

---

## 3. 检索管线（6 阶段）

```
M5 查询请求: "DNV Pt.4 Ch.3 EH36 预热温度要求"
    │
    ▼
阶段 1: 查询分析 (query_analyzer.py)
    │  提取: classification_society=DNV, chapter=Pt.4 Ch.3
    │  关键词: "EH36", "preheat", "temperature"
    │  语义查询: "preheat temperature requirements for steel grade"
    │
    ├──→ 阶段 2a: 向量检索 (dense_retriever.py)
    │       │  语义查询 → BGE-M3 嵌入 → ChromaDB ANN 搜索
    │       │  元数据过滤: where={"classification_society": "DNV"}
    │       │  返回: Top 50 ScoredChunk (source="dense")
    │
    └──→ 阶段 2b: 全文检索 (sparse_retriever.py)
            │  关键词查询: "EH36 preheat temperature"
            │  Meilisearch BM25 搜索
            │  返回: Top 20 ScoredChunk (source="bm25")
    │
    ▼
阶段 3: 融合 (fusion.py)
    │  策略: RRF (Reciprocal Rank Fusion)
    │  k=60, 合并去重
    │  返回: Top 50 ScoredChunk (source="fusion")
    │
    ▼
阶段 4: 重排序 (reranker.py)
    │  Cross-Encoder 模型: BGE-Reranker-v2-m3
    │  对 Top 50 逐一打分
    │  返回: Top 20 ScoredChunk (score=reranker_score)
    │
    ▼
阶段 5: 上下文扩展 (context_expander.py)
    │  每个 chunk 附加上下文: 前后段落 + 父章节标题
    │  表格 chunk: 附回表头行
    │
    ▼
阶段 6: 输出 (pipeline.py)
    │  RetrievedContext: chunks + total_found + latency + query_rewrites
    │  → 返回给 M5
```

### 关于 HyDE（已在 contracts/ 定义但不默认启用）

HyDE 接收查询后生成一份假设文档，用该文档做向量检索而非直接用查询。在海洋工程场景中，HyDE 的价值有限——规范用语高度标准化，"EH36" 在文档中出现的上下文非常确定。只在 `RetrievalRequest.enable_hyde=True` 时才启用，且作为可选嵌入模型扩展，默认关闭。

---

## 4. 查询分析器设计

### 4.1 元数据提取（复用 M1 的正则规则）

```python
def analyze_query(query: str) -> QueryAnalysis:
    """
    从自然语言查询中提取结构化过滤条件。

    示例:
    "DNV Pt.4 Ch.3 EH36 预热温度"
    → classification_society="DNV", chapter_section="Pt.4 Ch.3",
      keywords=["EH36", "预热温度"], semantic_query="preheat temperature for steel"
    """
    meta = extract_marine_metadata(query)  # 复用 M1 的 marine_metadata.py
    return QueryAnalysis(
        classification_society=meta.classification_society,
        chapter_section=meta.chapter_section,
        version_year=meta.version_year,
        keywords=extract_keywords(query),
        semantic_query=build_semantic_query(query, meta),
    )
```

### 4.2 关键词分离

关键词（如 "EH36"、"150°C"）必须精确匹配，不能做语义模糊。分离规则：
- 钢级标识符：`[A-Z]{2,4}\d{2,3}` → "EH36", "AH32"
- 温度值：`\d{2,4}°C` → "150°C"
- 规范章节号：`Pt\.\d+|Ch\.\d+|§\d+` → 已在元数据提取中处理
- 船级社缩写：已在元数据提取中处理

---

## 5. 双路检索设计

### 5.1 向量检索（Dense）

| 项 | 值 |
|----|-----|
| 嵌入模型 | BGE-M3（多语言，支持中英） |
| 向量库 | ChromaDB（M2 VectorStore） |
| 检索方式 | ANN + metadata where 过滤 |
| 默认 Top K | 50 |
| 距离度量 | Cosine |

**为什么选 BGE-M3**：
- 支持多语言（中/英/韩/日/挪威），覆盖全部 5 种 i18n 语言
- 1024 维向量，比 BGE-Large 的 768 维更丰富
- 在通用基准和海事实体检索上表现均衡

### 5.2 全文检索（Sparse）

| 项 | 值 |
|----|-----|
| 引擎 | Meilisearch（M2 DocumentIndex） |
| 算法 | BM25 |
| 默认 Top K | 20 |
| 查询构建 | 关键词 AND 连接 |

**为什么 BM25 和向量检索互补**：
- 规范编号（"Pt.4 Ch.3"）在向量空间中无对应语义，但 BM25 能精确命中
- 专有名词（"EH36"、"AH32"）在嵌入模型中可能被平滑为"钢级"，BM25 保留原样
- 短查询（<5 词）向量检索效果不稳定，BM25 更可靠

---

## 6. 融合与重排序

### 6.1 RRF 融合

```
RRF_score(d) = Σ 1/(k + rank_i(d))
k = 60（标准值）
```

RRF 不依赖原始分数的量级——向量检索的 Cosine 分数和 BM25 分数不在同一尺度，直接加权平均不可靠。

### 6.2 Cross-Encoder 重排序

| 项 | 值 |
|----|-----|
| 模型 | BGE-Reranker-v2-m3 |
| 输入 | (query, chunk.text) 对 |
| 输入 Top K | 50 |
| 输出 Top K | 20 |
| 批处理 | 单次推理 50 对 |

重排序后每个 chunk 的 `score` 字段更新为 Cross-Encoder 的 relevance 分数（0-1），`source` 保留原检索来源。

---

## 7. 上下文扩展设计

每个检索出的 chunk 在返回给 M5 之前，附加上下文窗口：

```
返回给 M5 的不是:
  "150°C"   ← 孤立的表格单元格

而是:
  "Table 3-1 预热温度要求 | Steel Grade: EH36 (t≤50mm) |
   Minimum Preheat Temp: 150°C | Interpass Temp: 200°C"
  ↑ chunk 本身（已由 M1 table_annotator 注解）+ 表标题（context_expander 附加）
```

扩展逻辑：
1. 从 M2 FileStore 读取 chunk 所属的 `full.md`
2. 找到 chunk 在文档中的位置
3. 向前取 `context_before` 段、向后取 `context_after` 段
4. 如果是表格 chunk，附加表标题行

配置参数：`context_window=3`（前后各 3 个段落）

---

## 8. M2 集成

M3 通过 M2 的 StorageManager 访问两个后端：

| M2 后端 | M3 用途 | 方式 |
|---------|--------|------|
| VectorStore (ChromaDB) | 向量检索 | `manager.vector_store.search(query_vector, top_k, filters)` |
| DocumentIndex (Meilisearch) | 全文检索 | `manager.doc_index.search(keywords, top_k, filters)` |
| FileStore (LocalFS) | 上下文扩展 | `manager.file_store.get(f"{doc_id}/full.md")` |
| RelationalDB (SQLite) | 可选：统计查询 | — |

---

## 9. M5 集成接口

M3 实现 `contracts/retrieval.py` 中的 `RetrievalEngineProtocol`：

```python
class RetrievalEngine:
    async def retrieve(self, request: RetrievalRequest) -> RetrievedContext:
        """执行完整 6 阶段检索管线"""
        ...

    async def health_check(self) -> dict[str, Any]:
        """验证所有后端连通性"""
        ...
```

M5 调用方式：
```python
from m3_retrieval import create_retrieval_engine

engine = await create_retrieval_engine(storage_manager)
result = await engine.retrieve(RetrievalRequest(
    query="DNV Pt.4 Ch.3 EH36 预热温度",
    top_k=20,
    fusion_strategy="rrf",
))
```

---

## 10. 质量度量

| 指标 | 说明 | 目标 |
|------|------|:--:|
| Recall@20 | 前 20 结果中包含正确答案的比例 | ≥90% |
| MRR | 正确结果的平均倒数排名 | ≥0.7 |
| NDCG@20 | 归一化折损累计增益 | ≥0.8 |
| P@5 | 前 5 结果的精确率 | ≥0.8 |

度量模块支持两种模式：
1. **离线评估** — 使用标注好的查询-文档对计算指标
2. **在线记录** — 每次检索记录查询和返回结果，供后续分析

---

## 11. 技术选型汇总

| 组件 | 选型 | 原因 |
|------|------|------|
| 嵌入模型 | BGE-M3 | 多语言, 1024维, 海洋领域适配 |
| 向量库 | ChromaDB (M2) | 已部署，嵌入运行 |
| 全文引擎 | Meilisearch (M2) | 已部署，BM25 |
| 融合算法 | RRF (k=60) | 分数无关，稳定可靠 |
| 重排序 | BGE-Reranker-v2-m3 | Cross-Encoder 精度高 |
| 元数据提取 | 复用 M1 marine_metadata | 规则一致，零重复 |
| 框架 | 纯 Python, 无额外服务 | Personal 模式零外部依赖 |

---

## 12. 开发决策记录

| ID | 日期 | 决策 |
|----|------|------|
| M3-D01 | 2026-05-24 | 双路检索（向量 + BM25），RRF 融合 |
| M3-D02 | 2026-05-24 | Cross-Encoder 重排序（BGE-Reranker-v2-m3） |
| M3-D03 | 2026-05-24 | 元数据过滤优先：classification_society + chapter_section |
| M3-D04 | 2026-05-24 | 不实现查询分解（M5 负责），不内置 LLM 依赖 |
| M3-D05 | 2026-05-24 | HyDE 默认关闭，作为可选扩展 |
| M3-D06 | 2026-05-24 | 上下文扩展：前后 3 段落 + 表格表头 |
| M3-D07 | 2026-05-24 | 嵌入模型 BGE-M3，重排序 BGE-Reranker-v2-m3 |

---

*设计规范结束。待审批后生成实现计划和任务分解。*
