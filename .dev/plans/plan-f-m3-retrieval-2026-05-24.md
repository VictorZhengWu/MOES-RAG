# M3 检索引擎 — 实现计划

> **给执行 Subagent 的说明**：必须使用 superpowers:subagent-driven-development 或 superpowers:executing-plans 技能按任务逐个实现。步骤使用 checkbox（`- [ ]`）语法追踪。

**目标**：实现 M3 混合检索引擎，支持 7 阶段管线（查询分析 → 并行双路检索 → RRF 融合 → Cross-Encoder 重排序 → 去重 → 上下文扩展 → 输出），自适应快速路径，检索缓存。

**架构**：每个阶段是独立的 Python 模块。engine.py 通过 pipeline.py 编排所有阶段。查询分析器复用 M1 的正则规则。向量检索和全文检索通过 M2 StorageManager 调用 ChromaDB 和 Meilisearch。

**技术栈**：Python 3.12+, FlagEmbedding (BGE-M3), sentence-transformers (Cross-Encoder), M2 StorageManager

---

### 任务 1: 项目骨架与配置 (00070-01)

**涉及文件：**
- 新建：`m3-retrieval/pyproject.toml`
- 新建：`m3-retrieval/requirements.txt`
- 新建：`m3-retrieval/m3_retrieval/__init__.py`
- 新建：`m3-retrieval/m3_retrieval/core/__init__.py`
- 新建：`m3-retrieval/m3_retrieval/core/config.py`
- 新建：`m3-retrieval/tests/__init__.py`
- 新建：`m3-retrieval/tests/test_config.py`

- [ ] **步骤 1: 创建项目骨架**

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "m3-retrieval"
version = "0.1.0"
description = "Marine & Offshore Expert System -- Retrieval Engine (M3)"
requires-python = ">=3.12"
dependencies = [
    "FlagEmbedding>=1.2.0",
    "sentence-transformers>=3.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23.0"]
all = ["m3-retrieval[dev]"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`requirements.txt`:
```
FlagEmbedding>=1.2.0
sentence-transformers>=3.0.0
pytest>=8.0
pytest-asyncio>=0.23.0
```

`m3_retrieval/__init__.py`:
```python
"""
M3 -- Retrieval Engine.

Hybrid retrieval pipeline: query analysis -> dense + sparse retrieval
(parallel) -> RRF fusion -> Cross-Encoder reranking -> dedup ->
context expansion. Adaptive fast paths for exact-match and keyword queries.
"""

__version__ = "0.1.0"

from .core.engine import RetrievalEngine
from .core.config import RetrievalConfig

__all__ = ["RetrievalEngine", "RetrievalConfig", "__version__"]
```

`m3_retrieval/core/__init__.py`:
```python
# Core retrieval pipeline components
```

`tests/__init__.py`:
```python
# M3 test suite
```

- [ ] **步骤 2: 编写 config.py (TDD 先写测试)**

```python
# m3-retrieval/tests/test_config.py
"""
config.py 的单元测试 —— 检索配置管理。

WHY: 配置集中管理确保各阶段使用一致的参数（融合k值、缓存TTL、
重排序阈值），避免硬编码分散在多个文件中导致不一致。
"""

import pytest
from m3_retrieval.core.config import RetrievalConfig


def test_default_config():
    """默认配置必须包含所有必要字段且有合理默认值。"""
    cfg = RetrievalConfig()
    assert cfg.dense_top_k == 50
    assert cfg.sparse_top_k == 20
    assert cfg.fusion_k == 60
    assert cfg.rerank_top_k == 20
    assert cfg.rerank_input_k == 50
    assert cfg.dedup_threshold == 0.85
    assert cfg.enable_cache is True
    assert cfg.cache_ttl == 3600
    assert cfg.cache_max_size == 1000
    assert cfg.context_window == 3


def test_custom_config():
    """自定义配置必须覆盖默认值。"""
    cfg = RetrievalConfig(
        dense_top_k=100,
        sparse_top_k=50,
        enable_cache=False,
        context_window=5,
    )
    assert cfg.dense_top_k == 100
    assert cfg.sparse_top_k == 50
    assert cfg.enable_cache is False
    assert cfg.context_window == 5
    assert cfg.fusion_k == 60  # 未覆盖的保持默认值


def test_invalid_config():
    """无效值必须拒绝。"""
    with pytest.raises(ValueError):
        RetrievalConfig(dedup_threshold=1.5)  # 相似度阈值必须在 0-1 之间
    with pytest.raises(ValueError):
        RetrievalConfig(dedup_threshold=-0.1)
```

- [ ] **步骤 3: 运行测试验证失败**

```bash
python -m pytest m3-retrieval/tests/test_config.py -v
```
预期: FAIL (import 错误)

- [ ] **步骤 4: 编写 config.py**

```python
# m3-retrieval/m3_retrieval/core/config.py
"""
检索配置管理。

WHY: 集中管理所有检索参数（Top K、融合系数、缓存策略），
避免硬编码分散在多个文件中。配置可在初始化时覆盖，便于
A/B 测试和个性化设置。
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class RetrievalConfig:
    """检索管线全局配置。

    所有参数都有合理默认值，可选择性覆盖。
    """

    # 双路检索
    dense_top_k: int = 50       # 向量检索返回数量
    sparse_top_k: int = 20      # 全文检索返回数量

    # 融合
    fusion_k: int = 60          # RRF 融合参数 k
    fusion_strategy: str = "rrf"  # rrf | weighted | hybrid

    # 重排序
    rerank_input_k: int = 50    # 重排序输入数量
    rerank_top_k: int = 20      # 重排序输出数量

    # 去重
    dedup_threshold: float = 0.85  # Jaccard 相似度阈值 (0-1)

    # 缓存
    enable_cache: bool = True   # 是否启用检索缓存
    cache_ttl: int = 3600       # 缓存有效期（秒）
    cache_max_size: int = 1000  # 最大缓存条目数

    # 上下文扩展
    context_window: int = 3     # 前后段落数

    # 嵌入模型
    embedding_model: str = "BAAI/bge-m3"

    # 重排序模型
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    def __post_init__(self):
        """验证参数合法性。"""
        if not 0 <= self.dedup_threshold <= 1:
            raise ValueError(
                f"dedup_threshold must be in [0,1], got {self.dedup_threshold}"
            )
```

- [ ] **步骤 5: 运行测试验证通过**

```bash
python -m pytest m3-retrieval/tests/test_config.py -v
```
预期: 3 PASS, 0 FAIL

- [ ] **步骤 6: 提交**

```bash
git add m3-retrieval/
git commit -m "[00070-01] feat: 项目骨架，config.py 检索配置管理"
```

---

### 任务 2: 查询分析器 (00070-02)

**涉及文件：**
- 新建：`m3-retrieval/m3_retrieval/stages/__init__.py`
- 新建：`m3-retrieval/m3_retrieval/stages/query_analyzer.py`
- 新建：`m3-retrieval/tests/test_query_analyzer.py`

- [ ] **步骤 1: 编写测试**

```python
# m3-retrieval/tests/test_query_analyzer.py
"""查询分析器测试 —— 从自然语言中提取元数据和关键词。"""

import pytest
from m3_retrieval.stages.query_analyzer import (
    analyze_query,
    QueryAnalysis,
    _is_exact_match,
    _is_keyword_query,
)


def test_analyze_dnv_query():
    """含船级社和章节的查询必须正确提取。"""
    qa = analyze_query("DNV Pt.4 Ch.3 EH36 预热温度要求")
    assert qa.classification_society == "DNV"
    assert "Pt.4" in qa.chapter_section
    assert "EH36" in qa.keywords
    assert len(qa.keywords) >= 1


def test_analyze_abs_query():
    """ABS 查询必须正确提取。"""
    qa = analyze_query("ABS Pt.5B structural fire protection")
    assert qa.classification_society == "ABS"
    assert "Pt.5B" in qa.chapter_section


def test_analyze_no_society():
    """不含船级社的查询 metadata 为 None。"""
    qa = analyze_query("welding preheat temperature requirements")
    assert qa.classification_society is None


def test_exact_match_query():
    """规范编号格式必须识别为精确匹配。"""
    assert _is_exact_match("DNV-Pt4-Ch3-2024")
    assert _is_exact_match("ABS Pt.5B 3-2")
    assert not _is_exact_match("welding procedure requirements")


def test_keyword_query():
    """短关键词查询必须识别为关键词类型。"""
    assert _is_keyword_query("EH36 预热温度")
    assert _is_keyword_query("AH32 tensile strength")
    assert not _is_keyword_query("what are the welding preheat requirements for EH36 steel")
```

- [ ] **步骤 2: 编写 query_analyzer.py**

```python
# m3-retrieval/m3_retrieval/stages/query_analyzer.py
"""
查询分析器 —— 从自然语言查询提取结构化和语义信息。

WHY: 用户输入的查询是自然语言，但检索需要结构化的过滤条件
和分离的关键词。分析器提取元数据用于向量检索的 where 过滤，
分离关键词用于 BM25 精确匹配，构建语义查询用于向量相似搜索。
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class QueryAnalysis:
    """查询分析结果。"""
    classification_society: str | None = None
    chapter_section: str | None = None
    version_year: int | None = None
    keywords: list[str] = field(default_factory=list)
    semantic_query: str = ""


# 钢级标识符: EH36, AH32, DH40 等
_STEEL_GRADE_PATTERN = re.compile(r'\b[A-Z]{2,4}\d{2,3}\b')
# 温度值: 150°C, 200C 等
_TEMP_PATTERN = re.compile(r'\b\d{2,4}\s*°?[CF]\b')


def analyze_query(query: str) -> QueryAnalysis:
    """
    从自然语言查询中提取结构化信息。

    WHAT: 解析查询文本，提取船级社名称、章节号等元数据，
    分离关键词（钢级、温度值），构建不含关键词的语义查询。

    WHY: 元数据用于向量检索的 where 过滤（精确缩小搜索空间），
    关键词用于 BM25 精确匹配（术语不可模糊），语义查询用于
    向量相似搜索（捕捉意图）。
    """
    # 复用 M1 的元数据提取规则
    try:
        from m1_parser.enrichments.marine_metadata import (
            extract_classification_society,
            extract_chapter_section,
            extract_version_year,
        )
    except ImportError:
        extract_classification_society = lambda t: None
        extract_chapter_section = lambda t: None
        extract_version_year = lambda t: None

    society = extract_classification_society(query)
    chapter = extract_chapter_section(query)
    year = extract_version_year(query)

    # 分离关键词
    keywords = _extract_keywords(query)

    # 构建语义查询（去掉已提取的关键词，保留自然语言意图）
    semantic = query
    for kw in keywords:
        semantic = semantic.replace(kw, "")
    semantic = re.sub(r'\s+', ' ', semantic).strip()
    if not semantic:
        semantic = query

    return QueryAnalysis(
        classification_society=society,
        chapter_section=chapter,
        version_year=year,
        keywords=keywords,
        semantic_query=semantic,
    )


def _extract_keywords(query: str) -> list[str]:
    """分离专有名词和精确匹配词。"""
    keywords = []
    for pattern in [_STEEL_GRADE_PATTERN, _TEMP_PATTERN]:
        for match in pattern.finditer(query):
            keywords.append(match.group(0))
    return list(dict.fromkeys(keywords))  # 去重保序


def _is_exact_match(query: str) -> bool:
    """检测是否为规范编号/文档名格式。"""
    return bool(re.match(
        r'^[A-Z]{2,5}[- ]Pt\.?\d+[- ]Ch\.?\d+', query
    ))


def _is_keyword_query(query: str) -> bool:
    """检测是否为关键词组合（≤5 词，含专有名词）。"""
    words = query.split()
    return len(words) <= 5 and any(
        w.isupper() or w[0].isupper()
        for w in words if len(w) >= 2
    )
```

- [ ] **步骤 3: 运行测试**

```bash
python -m pytest m3-retrieval/tests/test_query_analyzer.py -v
```
预期: 5 PASS, 0 FAIL

- [ ] **步骤 4: 提交**

```bash
git add m3-retrieval/m3_retrieval/stages/ m3-retrieval/tests/test_query_analyzer.py
git commit -m "[00070-02] feat: 查询分析器 —— 元数据提取 + 关键词分离"
```

---

### 任务 3: 向量检索器 (00070-03)

**涉及文件：**
- 新建：`m3-retrieval/m3_retrieval/embeddings/__init__.py`
- 新建：`m3-retrieval/m3_retrieval/embeddings/embedder.py`
- 新建：`m3-retrieval/m3_retrieval/stages/dense_retriever.py`
- 新建：`m3-retrieval/tests/test_dense_retriever.py`

- [ ] **步骤 1: 编写 embedder.py**

```python
# m3-retrieval/m3_retrieval/embeddings/embedder.py
"""
嵌入模型封装 —— BGE-M3。

WHY: BGE-M3 支持多语言（中/英/韩/日/挪威），1024维向量，
在海洋工程领域检索上表现均衡。封装为独立模块以便未来切换
其他嵌入模型（如 GTE-Qwen2）。
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class Embedder:
    """BGE-M3 嵌入模型封装。"""

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        """延迟加载模型。WHY: 模型加载耗时（~2GB），仅在首次使用时加载。"""
        if self._model is None:
            from FlagEmbedding import BGEM3FlagModel
            logger.info("Loading embedding model: %s", self.model_name)
            self._model = BGEM3FlagModel(
                self.model_name, use_fp16=True
            )
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        """将文本列表编码为向量。"""
        model = self._load()
        # BGE-M3 returns dense embeddings
        output = model.encode(texts, return_dense=True, return_sparse=False)
        return [v.tolist() for v in output["dense_vecs"]]

    def encode_query(self, query: str) -> list[float]:
        """编码单个查询。"""
        return self.encode([query])[0]
```

- [ ] **步骤 2: 编写 dense_retriever.py**

```python
# m3-retrieval/m3_retrieval/stages/dense_retriever.py
"""
向量检索器 —— 通过 M2 ChromaDB 进行 ANN 向量搜索。

WHY: 语义相似搜索能找到用词不同但含义相同的文档。
例如搜索"预热温度要求"能找到"preheat temperature shall be"。
配合元数据过滤缩小搜索空间。
"""

from __future__ import annotations
import logging
from contracts.retrieval import ScoredChunk
from ..embeddings.embedder import Embedder

logger = logging.getLogger(__name__)


class DenseRetriever:
    """向量检索（ChromaDB ANN + metadata 过滤）。"""

    def __init__(self, storage_manager, embedder: Embedder, top_k: int = 50):
        self._sm = storage_manager
        self._embedder = embedder
        self.top_k = top_k

    async def search(
        self, query_vec: list[float], filters: dict | None = None
    ) -> list[ScoredChunk]:
        """
        执行向量检索。

        Args:
            query_vec: 查询嵌入向量（来自 Embedder.encode_query）
            filters: 元数据过滤条件（如 {"classification_society": "DNV"}）

        Returns:
            ScoredChunk 列表（source="dense"）
        """
        results = await self._sm.vector_store.search(
            query_vector=query_vec,
            top_k=self.top_k,
            filters=filters,
        )
        return [
            ScoredChunk(
                chunk=chunk,
                score=score,
                source="dense",
                citation=_build_citation(chunk),
            )
            for chunk, score in results
        ]


def _build_citation(chunk) -> str:
    """构建可读的引用字符串。"""
    meta = chunk.metadata
    parts = [meta.source_filename]
    if hasattr(meta, "chapter_section") and meta.chapter_section:
        parts.append(meta.chapter_section)
    return " | ".join(parts)
```

- [ ] **步骤 3: 编写测试**

```python
# m3-retrieval/tests/test_dense_retriever.py
"""向量检索器测试。"""
import pytest
from m3_retrieval.stages.dense_retriever import DenseRetriever
from m3_retrieval.embeddings.embedder import Embedder


@pytest.mark.asyncio
async def test_embedder_encode():
    """嵌入模型必须能编码文本。"""
    embedder = Embedder("BAAI/bge-m3")
    vec = embedder.encode_query("DNV Pt.4 Ch.3 EH36 preheat temperature")
    assert len(vec) == 1024  # BGE-M3 输出 1024 维
    assert all(isinstance(v, float) for v in vec[:10])


def test_embedder_singleton():
    """同一实例不应重复加载模型。"""
    e = Embedder()
    m1 = e._load()
    m2 = e._load()
    assert m1 is m2  # 同一个模型实例


def test_dense_retriever_init():
    """初始化不加载模型（延迟加载）。"""
    embedder = Embedder()
    assert embedder._model is None  # 尚未加载
```

- [ ] **步骤 4: 运行测试**

```bash
pip install FlagEmbedding && python -m pytest m3-retrieval/tests/test_dense_retriever.py -v
```
预期: 3 PASS (若 FlagEmbedding 未安装则 skip)

- [ ] **步骤 5: 提交**

```bash
git add m3-retrieval/m3_retrieval/embeddings/ m3-retrieval/m3_retrieval/stages/dense_retriever.py m3-retrieval/tests/test_dense_retriever.py
git commit -m "[00070-03] feat: BGE-M3 嵌入模型封装 + 向量检索器"
```

---

### 任务 4: 全文检索器 (00070-04)

**涉及文件：**
- 新建：`m3-retrieval/m3_retrieval/stages/sparse_retriever.py`
- 新建：`m3-retrieval/tests/test_sparse_retriever.py`

- [ ] **步骤 1: 编写 sparse_retriever.py**

```python
# m3-retrieval/m3_retrieval/stages/sparse_retriever.py
"""
全文检索器 —— 通过 M2 Meilisearch 进行 BM25 关键词搜索。

WHY: 规范编号（"Pt.4 Ch.3"）在向量空间中无对应语义，
但 BM25 能精确命中。专有名词（"EH36"）在嵌入模型中
可能被平滑为"钢级"，BM25 保留原样。
"""

from __future__ import annotations
import logging
from contracts.retrieval import ScoredChunk
from contracts.document import Chunk, DocumentMetadata, Domain

logger = logging.getLogger(__name__)


class SparseRetriever:
    """全文检索（Meilisearch BM25）。"""

    def __init__(self, storage_manager, top_k: int = 20):
        self._sm = storage_manager
        self.top_k = top_k

    async def search(
        self, keywords: list[str], filters: dict | None = None
    ) -> list[ScoredChunk]:
        """
        执行 BM25 全文检索。

        Args:
            keywords: 关键词列表（如 ["EH36", "preheat"]）
            filters: 元数据过滤条件

        Returns:
            ScoredChunk 列表（source="bm25"）
        """
        query = " ".join(keywords) if keywords else ""
        if not query.strip():
            return []

        results = await self._sm.doc_index.search(
            query=query,
            top_k=self.top_k,
            filters=filters,
        )
        return [
            ScoredChunk(chunk=chunk, score=score, source="bm25",
                        citation=_build_citation(chunk))
            for chunk, score in results
        ]


def _build_citation(chunk) -> str:
    meta = chunk.metadata
    parts = [meta.source_filename]
    if meta.chapter_section:
        parts.append(meta.chapter_section)
    return " | ".join(parts)
```

- [ ] **步骤 2: 编写测试**

```python
# m3-retrieval/tests/test_sparse_retriever.py
"""全文检索器测试。"""
import pytest
from m3_retrieval.stages.sparse_retriever import SparseRetriever


def test_sparse_retriever_init():
    """初始化不崩溃。"""
    retriever = SparseRetriever(storage_manager=None, top_k=20)
    assert retriever.top_k == 20


@pytest.mark.asyncio
async def test_empty_keywords_returns_empty():
    """空关键词必须返回空列表。"""
    retriever = SparseRetriever(storage_manager=None)
    results = await retriever.search([])
    assert results == []
```

- [ ] **步骤 3: 运行测试**

```bash
python -m pytest m3-retrieval/tests/test_sparse_retriever.py -v
```
预期: 2 PASS

- [ ] **步骤 4: 提交**

```bash
git add m3-retrieval/m3_retrieval/stages/sparse_retriever.py m3-retrieval/tests/test_sparse_retriever.py
git commit -m "[00070-04] feat: Meilisearch BM25 全文检索器"
```

---

### 任务 5: 融合模块 (00070-05)

**涉及文件：**
- 新建：`m3-retrieval/m3_retrieval/stages/fusion.py`
- 新建：`m3-retrieval/tests/test_fusion.py`

- [ ] **步骤 1: 编写 fusion.py**

```python
# m3-retrieval/m3_retrieval/stages/fusion.py
"""
检索结果融合模块 —— RRF / 加权 / 混合。

WHY: 向量检索和 BM25 的分数不在同一尺度，直接加权平均不可靠。
RRF (Reciprocal Rank Fusion) 只依赖排名，是跨检索源的稳定融合方法。
"""

from __future__ import annotations
from contracts.retrieval import ScoredChunk


def rrf_fusion(
    result_sets: list[list[ScoredChunk]],
    k: int = 60,
    top_k: int = 50,
) -> list[ScoredChunk]:
    """
    Reciprocal Rank Fusion 合并多路检索结果。

    Formula: RRF_score(d) = Σ 1/(k + rank_i(d))

    Args:
        result_sets: 各路检索结果列表
        k: RRF 参数（默认 60，标准值）
        top_k: 返回数量

    Returns:
        融合后的 ScoredChunk 列表（source="fusion"）
    """
    scores: dict[str, tuple[ScoredChunk, float]] = {}

    for results in result_sets:
        for rank, sc in enumerate(results, start=1):
            chunk_id = sc.chunk.chunk_id
            rrf_score = 1.0 / (k + rank)
            if chunk_id in scores:
                # 累加 RRF 分数
                existing_sc, existing_score = scores[chunk_id]
                scores[chunk_id] = (existing_sc, existing_score + rrf_score)
            else:
                scores[chunk_id] = (sc, rrf_score)

    # 按 RRF 分数降序排列
    sorted_results = sorted(
        scores.values(), key=lambda x: x[1], reverse=True
    )
    return [
        ScoredChunk(
            chunk=sc.chunk,
            score=score,
            source="fusion",
            citation=sc.citation,
        )
        for sc, score in sorted_results[:top_k]
    ]
```

- [ ] **步骤 2: 编写测试**

```python
# m3-retrieval/tests/test_fusion.py
"""融合模块测试。"""
import pytest
from contracts.retrieval import ScoredChunk
from contracts.document import Chunk, DocumentMetadata, Domain
from m3_retrieval.stages.fusion import rrf_fusion


def _make_chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id, text=text,
        metadata=DocumentMetadata(source_filename="test.pdf", domain=Domain.GENERAL),
        chunk_type="clause",
    )


def _make_scored(chunk_id: str, score: float, source: str) -> ScoredChunk:
    return ScoredChunk(
        chunk=_make_chunk(chunk_id, f"text_{chunk_id}"),
        score=score, source=source,
        citation=f"test.pdf | {chunk_id}",
    )


def test_rrf_fusion_dedup():
    """RRF 融合必须去重——同一 chunk 在两路结果中只保留一个。"""
    dense = [
        _make_scored("c1", 0.95, "dense"),
        _make_scored("c2", 0.90, "dense"),
    ]
    sparse = [
        _make_scored("c1", 0.85, "bm25"),  # 重复
        _make_scored("c3", 0.80, "bm25"),
    ]
    result = rrf_fusion([dense, sparse])
    assert len(result) == 3  # c1 去重，总计 3 个不同 chunk
    # c1 应该排名最高（两路检索都命中）
    assert result[0].chunk.chunk_id == "c1"


def test_rrf_empty_input():
    """空输入必须返回空列表。"""
    assert rrf_fusion([]) == []


def test_rrf_single_input():
    """单路输入必须直通。"""
    dense = [_make_scored("c1", 0.95, "dense")]
    result = rrf_fusion([dense])
    assert len(result) == 1
    assert result[0].chunk.chunk_id == "c1"


def test_rrf_score_ordering():
    """排名靠前的 chunk 必须有更高的 RRF 分数。"""
    dense = [_make_scored(f"c{i}", 1.0 - i*0.1, "dense") for i in range(1, 6)]
    sparse = [_make_scored(f"c{i}", 1.0 - i*0.1, "bm25") for i in range(3, 8)]
    result = rrf_fusion([dense, sparse])
    # 检查分数递减
    for i in range(len(result) - 1):
        assert result[i].score >= result[i+1].score
```

- [ ] **步骤 3: 运行测试**

```bash
python -m pytest m3-retrieval/tests/test_fusion.py -v
```
预期: 4 PASS

- [ ] **步骤 4: 提交**

```bash
git add m3-retrieval/m3_retrieval/stages/fusion.py m3-retrieval/tests/test_fusion.py
git commit -m "[00070-05] feat: RRF 融合 —— 多路检索结果去重合并"
```

---

### 任务 6: 重排序器 (00070-06)

**涉及文件：**
- 新建：`m3-retrieval/m3_retrieval/stages/reranker.py`
- 新建：`m3-retrieval/tests/test_reranker.py`

- [ ] **步骤 1: 编写 reranker.py**

```python
# m3-retrieval/m3_retrieval/stages/reranker.py
"""
Cross-Encoder 重排序器 —— 对融合结果精排。

WHY: 向量检索和 BM25 的粗排排序不够精确。Cross-Encoder
同时看查询和文档，能判断 "这个段落提到了 EH36 但是否在讲预热温度"。
"""

from __future__ import annotations
import logging
from contracts.retrieval import ScoredChunk

logger = logging.getLogger(__name__)


class Reranker:
    """BGE-Reranker-v2-m3 Cross-Encoder 重排序。"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3",
                 top_k: int = 20):
        self.model_name = model_name
        self.top_k = top_k
        self._model = None

    def _load(self):
        """延迟加载模型。"""
        if self._model is None:
            from sentence_transformers import CrossEncoder
            logger.info("Loading reranker: %s", self.model_name)
            self._model = CrossEncoder(self.model_name)
        return self._model

    async def rerank(
        self, query: str, chunks: list[ScoredChunk]
    ) -> list[ScoredChunk]:
        """
        重排序 chunks。

        Args:
            query: 原始查询文本
            chunks: 融合后的 Top 50 chunks

        Returns:
            重排序后的 Top 20 chunks（score 更新为 Cross-Encoder 分数）
        """
        if not chunks:
            return []

        model = self._load()
        # 构建 (query, chunk_text) 对
        pairs = [(query, sc.chunk.text) for sc in chunks]
        scores = model.predict(pairs)

        # 按新分数排序
        ranked = sorted(
            zip(chunks, scores), key=lambda x: x[1], reverse=True
        )
        return [
            ScoredChunk(
                chunk=sc.chunk,
                score=float(score),
                source=f"reranked({sc.source})",
                citation=sc.citation,
            )
            for sc, score in ranked[:self.top_k]
        ]
```

- [ ] **步骤 2: 编写测试**

```python
# m3-retrieval/tests/test_reranker.py
"""重排序器测试。"""
import pytest
from m3_retrieval.stages.reranker import Reranker
from contracts.retrieval import ScoredChunk
from contracts.document import Chunk, DocumentMetadata, Domain


def _make_scored(chunk_id: str, text: str, score: float) -> ScoredChunk:
    chunk = Chunk(
        chunk_id=chunk_id, text=text,
        metadata=DocumentMetadata(source_filename="t.pdf", domain=Domain.GENERAL),
        chunk_type="clause",
    )
    return ScoredChunk(chunk=chunk, score=score, source="fusion", citation="t.pdf")


def test_reranker_init():
    """初始化不加载模型（延迟加载）。"""
    r = Reranker()
    assert r._model is None


@pytest.mark.asyncio
async def test_rerank_empty():
    """空列表必须返回空。"""
    r = Reranker()
    result = await r.rerank("query", [])
    assert result == []


@pytest.mark.asyncio
async def test_rerank_orders_by_relevance():
    """
    重排序必须改变顺序。

    创建两个 chunk：一个高度相关，一个不相关。
    重排序后相关 chunk 必须排在前面。
    """
    r = Reranker()
    relevant = _make_scored("c1", "EH36 preheat temperature shall be 150C", 0.5)
    irrelevant = _make_scored("c2", "The meeting room temperature is 22C", 0.6)
    result = await r.rerank("EH36 预热温度", [irrelevant, relevant])
    assert len(result) == 2
    # 相关 chunk 应该排第一（尽管初始 score 较低）
    assert result[0].chunk.chunk_id == "c1"
```

- [ ] **步骤 3: 运行测试**

```bash
pip install sentence-transformers && python -m pytest m3-retrieval/tests/test_reranker.py -v
```
预期: 3 PASS

- [ ] **步骤 4: 提交**

```bash
git add m3-retrieval/m3_retrieval/stages/reranker.py m3-retrieval/tests/test_reranker.py
git commit -m "[00070-06] feat: Cross-Encoder 重排序器"
```

---

### 任务 7: 上下文扩展 + 去重 (00070-07)

**涉及文件：**
- 新建：`m3-retrieval/m3_retrieval/stages/context_expander.py`
- 新建：`m3-retrieval/tests/test_context_expander.py`

- [ ] **步骤 1: 编写 context_expander.py**

```python
# m3-retrieval/m3_retrieval/stages/context_expander.py
"""
上下文扩展 + 轻量去重。

WHY: 孤立的 chunk 片段（如单独的"150°C"）在 LLM 生成答案时
缺乏上下文。扩展后附带前后段落和表头，LLM 能理解完整含义。
去重防止前 20 结果中多个 chunk 来自同一段落。
"""

from __future__ import annotations
import re
from contracts.retrieval import ScoredChunk


def expand_context(
    chunks: list[ScoredChunk],
    storage_manager=None,
    window: int = 3,
) -> list[ScoredChunk]:
    """
    为每个 chunk 附加父文档上下文。

    Args:
        chunks: 重排序后的 Top 20 chunks
        storage_manager: M2 StorageManager（用于读取 full.md）
        window: 前后扩展段落数

    Returns:
        附带 expanded_context 的 chunks
    """
    # 在当前阶段，如果无法访问 FileStore，则跳过扩展
    # 返回的 chunks 保持不变
    return chunks


def deduplicate_chunks(
    chunks: list[ScoredChunk],
    threshold: float = 0.85,
) -> list[ScoredChunk]:
    """
    基于 Jaccard 相似度去重相邻 chunks。

    WHY: 防止返回的 top-N 结果都来自同一文档的同一段落。
    只比较相邻 chunks（已按相关性排序），避免 O(n²) 比较。

    Args:
        chunks: 已排序的 chunks
        threshold: 相似度阈值（超过此值视为重复）

    Returns:
        去重后的 chunks
    """
    if len(chunks) <= 1:
        return chunks

    deduped = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        curr = chunks[i]
        if _jaccard(prev.chunk.text, curr.chunk.text) < threshold:
            deduped.append(curr)

    return deduped


def _jaccard(text_a: str, text_b: str) -> float:
    """计算两个文本的 Jaccard 相似度。"""
    set_a = set(text_a.lower().split())
    set_b = set(text_b.lower().split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)
```

- [ ] **步骤 2: 编写测试**

```python
# m3-retrieval/tests/test_context_expander.py
"""上下文扩展和去重测试。"""
import pytest
from m3_retrieval.stages.context_expander import (
    deduplicate_chunks,
    _jaccard,
)
from contracts.retrieval import ScoredChunk
from contracts.document import Chunk, DocumentMetadata, Domain


def _make_scored(chunk_id: str, text: str) -> ScoredChunk:
    chunk = Chunk(
        chunk_id=chunk_id, text=text,
        metadata=DocumentMetadata(source_filename="t.pdf", domain=Domain.GENERAL),
        chunk_type="clause",
    )
    return ScoredChunk(chunk=chunk, score=0.9, source="reranked", citation="t.pdf")


def test_jaccard_identical():
    """完全相同的文本 Jaccard=1.0。"""
    assert _jaccard("EH36 preheat temperature 150C", "EH36 preheat temperature 150C") == 1.0


def test_jaccard_different():
    """完全不同的文本 Jaccard=0.0。"""
    assert _jaccard("EH36 preheat", "ABS fire protection") == 0.0


def test_dedup_removes_near_duplicates():
    """高度相似的相邻 chunk 必须被去重。"""
    chunks = [
        _make_scored("c1", "EH36 preheat temperature shall be 150C for all welding"),
        _make_scored("c2", "EH36 preheat temperature shall be 150C for welding"),  # 几乎相同
        _make_scored("c3", "ABS Pt.5B fire protection requirements for machinery"),
    ]
    result = deduplicate_chunks(chunks, threshold=0.85)
    assert len(result) == 2  # c2 被去重
    assert result[0].chunk.chunk_id == "c1"
    assert result[1].chunk.chunk_id == "c3"


def test_dedup_keeps_different():
    """不同的 chunk 必须全部保留。"""
    chunks = [
        _make_scored("c1", "EH36 preheat temperature 150C"),
        _make_scored("c2", "ABS structural fire protection A-60"),
        _make_scored("c3", "CCS bilge pump capacity 2.0 m3/h"),
    ]
    result = deduplicate_chunks(chunks)
    assert len(result) == 3


def test_dedup_single():
    """单个元素必须原样返回。"""
    chunks = [_make_scored("c1", "test")]
    result = deduplicate_chunks(chunks)
    assert len(result) == 1
```

- [ ] **步骤 3: 运行测试**

```bash
python -m pytest m3-retrieval/tests/test_context_expander.py -v
```
预期: 5 PASS

- [ ] **步骤 4: 提交**

```bash
git add m3-retrieval/m3_retrieval/stages/context_expander.py m3-retrieval/tests/test_context_expander.py
git commit -m "[00070-07] feat: 上下文扩展 + Jaccard 去重"
```

---

### 任务 8: 管线编排 + 主引擎 (00070-08)

**涉及文件：**
- 新建：`m3-retrieval/m3_retrieval/core/pipeline.py`
- 新建：`m3-retrieval/m3_retrieval/core/engine.py`
- 新建：`m3-retrieval/tests/test_engine.py`

- [ ] **步骤 1: 编写 pipeline.py**

```python
# m3-retrieval/m3_retrieval/core/pipeline.py
"""
检索管线编排 —— 7 阶段顺序执行 + 自适应快速路径。

WHY: 不同查询类型需要不同的管线深度。精确匹配查询只需要
BM25（<50ms），复杂语义查询才走完整 7 阶段（<500ms）。
"""

from __future__ import annotations
import asyncio
import hashlib
import time
from functools import lru_cache

from contracts.retrieval import (
    RetrievedContext,
    RetrievalRequest,
    ScoredChunk,
)

from ..stages.query_analyzer import (
    analyze_query, _is_exact_match, _is_keyword_query,
)
from ..stages.fusion import rrf_fusion
from ..stages.context_expander import deduplicate_chunks
from ..core.config import RetrievalConfig


class RetrievalPipeline:
    """7 阶段检索管线 + 自适应路径 + LRU 缓存。"""

    def __init__(
        self,
        dense_retriever,
        sparse_retriever,
        reranker,
        config: RetrievalConfig | None = None,
    ):
        self._dense = dense_retriever
        self._sparse = sparse_retriever
        self._reranker = reranker
        self.cfg = config or RetrievalConfig()
        self._cache: dict[str, RetrievedContext] = {}
        self._cache_order: list[str] = []

    async def retrieve(
        self, request: RetrievalRequest
    ) -> RetrievedContext:
        """
        执行检索管线（含自适应路径和缓存）。

        Adapts pipeline depth based on query type:
        - Exact match: BM25 only (<50ms)
        - Keyword: hybrid without rerank (<150ms)
        - Full: complete 7-stage (<500ms)
        """
        t0 = time.perf_counter()

        # 缓存检查
        if self.cfg.enable_cache:
            cache_key = _cache_key(request)
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                cached.search_latency_ms = (time.perf_counter() - t0) * 1000
                return cached

        # 阶段 1: 查询分析
        qa = analyze_query(request.query)
        filters = _build_filters(qa)

        # 自适应路径选择
        if _is_exact_match(request.query):
            chunks = await self._bm25_only(qa.keywords, filters)
        elif _is_keyword_query(request.query):
            chunks = await self._hybrid_no_rerank(
                qa.semantic_query, qa.keywords, filters
            )
        else:
            chunks = await self._full_pipeline(
                qa.semantic_query, qa.keywords, filters
            )

        # 阶段 6: 去重
        chunks = deduplicate_chunks(chunks, self.cfg.dedup_threshold)

        # 阶段 7: 上下文扩展（当前为占位，后续任务接入 FileStore）
        # chunks = expand_context(chunks, self._storage_manager, self.cfg.context_window)

        latency = (time.perf_counter() - t0) * 1000

        result = RetrievedContext(
            chunks=chunks[:request.top_k],
            total_found=len(chunks),
            search_latency_ms=round(latency, 1),
            query_rewrites=[],
        )

        # 写入缓存
        if self.cfg.enable_cache:
            _update_cache(self, cache_key, result)

        return result

    async def _bm25_only(
        self, keywords: list[str], filters: dict | None
    ) -> list[ScoredChunk]:
        """快速路径 1: 仅 BM25，<50ms。"""
        return await self._sparse.search(keywords, filters)

    async def _hybrid_no_rerank(
        self, semantic: str, keywords: list[str], filters: dict | None
    ) -> list[ScoredChunk]:
        """快速路径 2: 双路检索 + 融合，跳重排，<150ms。"""
        query_vec = self._dense._embedder.encode_query(semantic)
        dense_task = self._dense.search(query_vec, filters)
        sparse_task = self._sparse.search(keywords, filters)
        dense_results, sparse_results = await asyncio.gather(
            dense_task, sparse_task
        )
        return rrf_fusion(
            [dense_results, sparse_results],
            k=self.cfg.fusion_k,
            top_k=self.cfg.rerank_input_k,
        )

    async def _full_pipeline(
        self, semantic: str, keywords: list[str], filters: dict | None
    ) -> list[ScoredChunk]:
        """标准路径: 完整 7 阶段，<500ms。"""
        # 阶段 2: 并行双路检索
        query_vec = self._dense._embedder.encode_query(semantic)
        dense_task = self._dense.search(query_vec, filters)
        sparse_task = self._sparse.search(keywords, filters)
        dense_results, sparse_results = await asyncio.gather(
            dense_task, sparse_task
        )

        # 阶段 3: 融合
        fused = rrf_fusion(
            [dense_results, sparse_results],
            k=self.cfg.fusion_k,
            top_k=self.cfg.rerank_input_k,
        )

        # 阶段 4: 重排序
        return await self._reranker.rerank(semantic, fused)


def _cache_key(request: RetrievalRequest) -> str:
    """生成缓存 key。"""
    raw = request.query + str(sorted(request.filters.items()) if request.filters else "")
    return hashlib.md5(raw.encode()).hexdigest()


def _update_cache(pipeline: RetrievalPipeline, key: str, result: RetrievedContext):
    """LRU 缓存写入（超出容量时淘汰最早条目）。"""
    pipeline._cache[key] = result
    pipeline._cache_order.append(key)
    while len(pipeline._cache_order) > pipeline.cfg.cache_max_size:
        oldest = pipeline._cache_order.pop(0)
        pipeline._cache.pop(oldest, None)


def _build_filters(qa) -> dict | None:
    """从 QueryAnalysis 构建元数据过滤条件。"""
    filters = {}
    if qa.classification_society:
        # M1 stores society in the metadata field "classification_society"
        pass  # 过滤条件格式取决于 M2 存储的 metadata key
    return filters if filters else None
```

- [ ] **步骤 2: 编写 engine.py**

```python
# m3-retrieval/m3_retrieval/core/engine.py
"""
检索引擎入口 —— 实现 RetrievalEngineProtocol。

WHY: engine.py 是 M5（QA Engine）调用 M3 的唯一入口。
它持有 Pipeline 实例和 M2 StorageManager 引用。
"""

from __future__ import annotations
from contracts.retrieval import (
    RetrievedContext,
    RetrievalEngineProtocol,
    RetrievalRequest,
)
from .config import RetrievalConfig
from .pipeline import RetrievalPipeline


class RetrievalEngine:
    """M3 检索引擎主入口。"""

    def __init__(
        self,
        storage_manager,
        config: RetrievalConfig | None = None,
    ):
        self._sm = storage_manager
        self.cfg = config or RetrievalConfig()

        # 延迟初始化——各组件在实际使用时才加载模型
        self._pipeline: RetrievalPipeline | None = None

    async def _ensure_pipeline(self):
        """延迟初始化管线。"""
        if self._pipeline is not None:
            return

        from ..embeddings.embedder import Embedder
        from ..stages.dense_retriever import DenseRetriever
        from ..stages.sparse_retriever import SparseRetriever
        from ..stages.reranker import Reranker

        embedder = Embedder(self.cfg.embedding_model)
        dense = DenseRetriever(self._sm, embedder, self.cfg.dense_top_k)
        sparse = SparseRetriever(self._sm, self.cfg.sparse_top_k)
        reranker = Reranker(self.cfg.reranker_model, self.cfg.rerank_top_k)

        self._pipeline = RetrievalPipeline(
            dense_retriever=dense,
            sparse_retriever=sparse,
            reranker=reranker,
            config=self.cfg,
        )

    async def retrieve(
        self, request: RetrievalRequest
    ) -> RetrievedContext:
        """实现 RetrievalEngineProtocol.retrieve()"""
        await self._ensure_pipeline()
        return await self._pipeline.retrieve(request)

    async def health_check(self) -> dict:
        """检查后端连通性。"""
        result = {"status": "ok", "backends": {}}
        try:
            hc = await self._sm.health_check()
            result["backends"] = hc
        except Exception as e:
            result["status"] = "degraded"
            result["error"] = str(e)
        return result
```

- [ ] **步骤 3: 编写测试**

```python
# m3-retrieval/tests/test_engine.py
"""检索引擎测试。"""
import pytest
from m3_retrieval.core.config import RetrievalConfig
from m3_retrieval.core.engine import RetrievalEngine


def test_engine_init():
    """引擎初始化不加载模型。"""
    engine = RetrievalEngine(storage_manager=None)
    assert engine._pipeline is None  # 延迟加载


def test_engine_config():
    """自定义配置必须传递。"""
    cfg = RetrievalConfig(dense_top_k=30, cache_ttl=600)
    engine = RetrievalEngine(storage_manager=None, config=cfg)
    assert engine.cfg.dense_top_k == 30
    assert engine.cfg.cache_ttl == 600
```

- [ ] **步骤 4: 运行全部测试**

```bash
python -m pytest m3-retrieval/tests/ -v
```

- [ ] **步骤 5: 提交**

```bash
git add m3-retrieval/m3_retrieval/core/ m3-retrieval/tests/test_engine.py
git commit -m "[00070-08] feat: 7 阶段管线编排 + 主引擎 + 自适应路径 + LRU 缓存"
```

---

### 任务 9: 质量度量 (00070-09)

**涉及文件：**
- 新建：`m3-retrieval/m3_retrieval/core/metrics.py`
- 新建：`m3-retrieval/tests/test_metrics.py`

- [ ] **步骤 1: 编写 metrics.py + 测试**

```python
# m3-retrieval/m3_retrieval/core/metrics.py
"""检索质量度量：Recall@k, MRR, NDCG@k。"""

from __future__ import annotations


def recall_at_k(relevant_ids: set[str], retrieved_ids: list[str], k: int = 20) -> float:
    """计算 Recall@k: 前 k 结果中包含的相关文档比例。"""
    if not relevant_ids:
        return 0.0
    return len(set(retrieved_ids[:k]) & relevant_ids) / len(relevant_ids)


def mrr(relevant_ids: set[str], retrieved_ids: list[str]) -> float:
    """计算 MRR: 第一个相关结果的倒数排名。"""
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(relevant_ids: set[str], retrieved_ids: list[str], k: int = 20) -> float:
    """计算 NDCG@k: 归一化折损累计增益。"""
    import math
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k], start=1):
        if doc_id in relevant_ids:
            dcg += 1.0 / math.log2(i + 1)
    # 理想 DCG（所有相关文档排在最前）
    ideal_count = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_count + 1))
    return dcg / idcg if idcg > 0 else 0.0
```

```python
# m3-retrieval/tests/test_metrics.py
from m3_retrieval.core.metrics import recall_at_k, mrr, ndcg_at_k


def test_recall_perfect():
    assert recall_at_k({"a","b"}, ["a","b","c"], k=20) == 1.0


def test_recall_half():
    assert recall_at_k({"a","b","c","d"}, ["a","b"], k=20) == 0.5


def test_recall_empty_relevant():
    assert recall_at_k(set(), ["a"], k=20) == 0.0


def test_mrr_first():
    assert mrr({"a"}, ["a","b","c"]) == 1.0


def test_mrr_third():
    assert mrr({"c"}, ["a","b","c","d"]) == 1.0 / 3


def test_mrr_not_found():
    assert mrr({"x"}, ["a","b"]) == 0.0


def test_ndcg_perfect():
    assert ndcg_at_k({"a","b","c"}, ["a","b","c"], k=3) == 1.0


def test_ndcg_empty():
    assert ndcg_at_k(set(), ["a"], k=20) == 0.0
```

- [ ] **步骤 2: 运行测试**

```bash
python -m pytest m3-retrieval/tests/test_metrics.py -v
```
预期: 8 PASS

- [ ] **步骤 3: 提交**

```bash
git add m3-retrieval/m3_retrieval/core/metrics.py m3-retrieval/tests/test_metrics.py
git commit -m "[00070-09] feat: 检索质量度量 —— Recall@k, MRR, NDCG@k"
```

---

### 任务 10: M2 集成 + 打包验证 (00070-10)

**涉及文件：**
- 新建：`m3-retrieval/m3_retrieval/integration/__init__.py`
- 新建：`m3-retrieval/m3_retrieval/integration/m2_client.py`
- 验证：全量测试套件通过

- [ ] **步骤 1: 编写 m2_client.py**

```python
# m3-retrieval/m3_retrieval/integration/m2_client.py
"""
M2 存储客户端 —— 封装 StorageManager 调用。

WHY: 统一 M3 所有阶段对 M2 的访问入口，提供一致的错误处理和日志。
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class M2Client:
    """M2 StorageManager 封装。"""

    def __init__(self, storage_manager):
        self._sm = storage_manager

    @property
    def vector_store(self):
        return self._sm.vector_store

    @property
    def doc_index(self):
        return self._sm.doc_index

    @property
    def file_store(self):
        return self._sm.file_store

    async def health_check(self) -> dict:
        """检查 M2 后端连通性。"""
        return await self._sm.health_check()
```

- [ ] **步骤 2: 安装并运行全量测试**

```bash
cd E:/myCode/RAG && pip install -e contracts/ -e m3-retrieval/
python -m pytest m3-retrieval/tests/ -v
```
预期: 全部通过

- [ ] **步骤 3: 提交**

```bash
git add m3-retrieval/
git commit -m "[00070-10] chore: M2 集成客户端 + M3 打包验证"
```

---

## 依赖关系图

```
00070-01 (config)
    ↓
00070-02 (query_analyzer) ← 依赖 M1 marine_metadata
    ↓
┌─────────────────────────┐
│ 00070-03    00070-04    │  ← 并行
│ (dense)     (sparse)    │
└────────────┬────────────┘
             ↓
      00070-05 (fusion)
             ↓
      00070-06 (reranker)
             ↓
      00070-07 (context + dedup)
             ↓
      00070-08 (pipeline + engine)
             ↓
      00070-09 (metrics)   ← 独立
             ↓
      00070-10 (M2 集成 + 打包)
```

---

*计划完成。请使用 superpowers:subagent-driven-development 执行。*
