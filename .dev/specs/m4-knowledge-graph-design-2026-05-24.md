# M4 知识图谱引擎 — 详细设计规范

> **日期**：2026-05-24 | **状态**：待审批
> **依赖**：contracts/ (00010), M2 (00050), M1 (00060)
> **定位**：Layer 2 (Processing)，从文档中提取实体和关系构建知识图谱

---

## 1. 模块定位

M4 是系统的知识图谱引擎。从 M1 已解析的文档 chunks 中抽取实体和关系，构建图数据库，支持图遍历查询和跨规范交叉引用。

**核心原则**：

- **建图离线、搜索在线** — LLM 提取只在入库时执行一次，搜索是毫秒级图遍历
- **嵌入式存储** — Kuzu 图数据库，零服务、一文件、MIT 许可证
- **LLM 可插拔** — 通过 M7 配置选择本地模型（Ollama/vLLM/LM Studio）或远程 API（DeepSeek/OpenAI/Claude）
- **用户分级** — Basic/Pro/Enterprise 控制图遍历深度和返回实体数

---

## 2. 模块目录结构

```
m4-knowledge-graph/
├── m4_kg/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── engine.py              # KG 引擎入口（KGEngineProtocol）
│   │   ├── config.py              # 配置：LLM 后端、用户等级、遍历深度
│   │   └── tier.py                # 用户分级策略（Basic/Pro/Enterprise）
│   │
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── llm_extractor.py       # LLM 实体+关系抽取（Prompt + 格式归一化）
│   │   ├── rule_extractor.py      # 规则抽取（正则兜底，钢级/规范条目/设备型号）
│   │   ├── merger.py              # 规则结果 + LLM 结果合并去重
│   │   └── prompt_templates.py    # 抽取 Prompt 模板（中英文）
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── kuzu_store.py          # Kuzu 图数据库封装（创建/写入/查询）
│   │   ├── schema.py              # 图 Schema 定义（节点类型、边类型）
│   │   └── traversal.py           # 图遍历查询（BFS/DFS/子图搜索）
│   │
│   ├── search/
│   │   ├── __init__.py
│   │   ├── graph_search.py        # 图谱搜索入口（实体搜索 + 子图扩展）
│   │   └── cross_reference.py     # 跨规范交叉引用（DNV↔ABS↔CCS 等价映射）
│   │
│   └── integration/
│       ├── __init__.py
│       ├── m2_bridge.py           # M2 存储桥接（FileStore 读取 chunk, RelationalDB 存图谱元数据）
│       └── m3_bridge.py           # M3 联合检索（向量+图）
│
├── tests/
│   ├── conftest.py
│   ├── test_llm_extractor.py
│   ├── test_rule_extractor.py
│   ├── test_merger.py
│   ├── test_kuzu_store.py
│   ├── test_traversal.py
│   ├── test_graph_search.py
│   ├── test_cross_reference.py
│   ├── test_engine.py
│   └── test_tier.py
│
├── requirements.txt
└── pyproject.toml
```

---

## 3. 建图管线（5 阶段）

```
M1 解析完成的文档 chunks
      │
      ▼
阶段 1: 规则抽取 (rule_extractor.py)
      │  正则 + 字典匹配，快速覆盖 70% 实体
      │  实体类型: regulation_clause, vessel_type, steel_grade, equipment_model
      │
      ▼
阶段 2: LLM 深度抽取 (llm_extractor.py)
      │  覆盖剩余 30% 的复杂语义
      │  实体: 隐含的约束条件、隐含的系统间关系
      │  关系: applies_to, requires, prohibits, equivalent_to 等 6 种
      │
      ▼
阶段 3: 合并去重 (merger.py)
      │  规则和 LLM 结果合并，同名实体去重
      │  LLM 结果覆盖规则结果（LLM 精度更高）
      │
      ▼
阶段 4: 图谱写入 (kuzu_store.py)
      │  创建节点（Entity）和边（Relation）
      │  每条边带 confidence 和 source_doc_id
      │
      ▼
阶段 5: 图谱就绪
      │  可被 graph_search() 和 cross_reference() 查询
```

---

## 4. LLM 抽取设计

### 4.1 Prompt 模板

```python
EXTRACTION_PROMPT = """
Extract entities and relations from the following marine engineering document text.

## Entity Types
- regulation_clause: normative rule (e.g., "DNV Pt.4 Ch.3 §2.1")
- steel_grade: steel material grade (e.g., "EH36", "AH32")
- equipment: specific equipment model (e.g., "DNV Type-A valve")
- system_type: ship system category (e.g., "bilge system", "ballast system")
- parameter: quantitative requirement (e.g., "preheat temperature 150°C", "plate thickness ≤50mm")
- ship_type: vessel classification (e.g., "bulk carrier", "oil tanker")

## Relation Types
- requires: entity A mandates entity B
- applies_to: entity A is applicable to entity B  
- prohibits: entity A forbids entity B
- replaces: entity A supersedes entity B
- references: entity A cites entity B
- constrains: entity A limits value of entity B

## Output Format
Return ONLY valid JSON:
{
  "entities": [
    {"id": "e1", "name": "...", "type": "steel_grade", "properties": {...}},
    ...
  ],
  "relations": [
    {"source": "e1", "target": "e2", "type": "constrains", "properties": {"condition": "t≤50mm"}},
    ...
  ]
}

## Text
{document_text}
"""
```

### 4.2 批量处理

一次送 20 个 chunk，减少 API 调用次数。本地模型使用 `asyncio.Semaphore(2)` 控制并发（RTX 2060 6GB 只能同时跑 2 个推理）。

### 4.3 格式归一化

LLM 输出不稳定——有时返回带 Markdown 代码块的 JSON，有时返回裸 JSON，有时多了个解释性文字。`_normalize_output()` 做三层解析：
1. 尝试 `json.loads()` 直接解析
2. 如果失败，正则提取 `{...}` JSON 块
3. 如果仍失败，记录错误并回退到规则抽取结果

### 4.4 成本控制

```python
@dataclass
class LLMBackend:
    provider: str  # "ollama" | "deepseek" | "openai" | "claude"
    model: str     # "DeepSeek-V3" | "gpt-4o" | etc.
    api_key: str | None = None
    base_url: str | None = None  # http://localhost:11434/v1 for Ollama

@dataclass
class ExtractionConfig:
    llm: LLMBackend | None = None
    max_chunks_per_doc: int = 200   # 最多处理 200 个 chunk
    batch_size: int = 20            # 每批 20 个 chunk
    max_concurrent: int = 2         # 本地模型并发数
    fallback_to_rules: bool = True  # LLM 失败时回退规则抽取
```

---

## 5. Kuzu 图数据库

### 5.1 Schema 定义

```cypher
CREATE NODE TABLE Entity(
    entity_id STRING PRIMARY KEY,
    name STRING,
    entity_type STRING,
    properties STRING,       -- JSON string
    source_doc_id STRING,
    created_at TIMESTAMP
);

CREATE REL TABLE Rel(
    FROM Entity TO Entity,
    relation_type STRING,
    properties STRING,        -- JSON string
    confidence DOUBLE,
    source_doc_id STRING
);
```

### 5.2 查询示例

```cypher
-- 查找 EH36 的所有关联实体（1 跳）
MATCH (e:Entity)-[r:Rel]->(target)
WHERE e.name = 'EH36'
RETURN e, r, target;

-- 查找 DNV 和 ABS 对焊接预热温度的等价要求（2 跳）
MATCH (dnv:Entity)-[r1:Rel*1..2]->(common)<-[r2:Rel*1..2]-(abs:Entity)
WHERE dnv.name CONTAINS 'DNV' AND abs.name CONTAINS 'ABS'
  AND common.name CONTAINS 'temperature'
RETURN dnv, abs, common, r1, r2;
```

---

## 6. 图谱搜索与 M3 联合检索

### 6.1 两路并行

M5 查询时，M3 和 M4 同时响应：

```
M5 查询："EH36 焊接要求"
    │
    ├──→ M3 检索（向量 + BM25）→ 语义相关的文档 chunk
    │        延迟: <500ms
    │
    └──→ M4 图谱搜索（图遍历）→ EH36 关联的实体和关系
             延迟: <50ms
    │
    ▼
M5 综合两路结果 → 生成答案
```

### 6.2 联合查询接口

```python
@dataclass
class CombinedRetrievalResult:
    chunks: list[ScoredChunk]        # 来自 M3
    graph: Subgraph                   # 来自 M4
    cross_refs: list[CrossReferenceResult]
    latency_ms: float
```

---

## 7. 用户分级策略

| 等级 | 图遍历深度 | 返回实体数 | 交叉引用 | M5 上下文上限 | 成本/查询 |
|------|:--:|:--:|:--:|:--:|:--:|
| Basic | 1 | 20 | ❌ | 2K tokens | ~$0.002 |
| Pro | 2-3 | 50 | ✅ 同规范内 | 8K tokens | ~$0.01 |
| Enterprise | 5 | 200 | ✅ 跨规范全量 | 32K tokens | ~$0.05 |

### 7.1 配置注入

```python
@dataclass
class UserTier:
    level: str = "basic"  # basic | pro | enterprise
    traversal_depth: int = 1
    max_entities: int = 20
    enable_cross_ref: bool = False
    context_token_limit: int = 2048

USER_TIERS = {
    "basic": UserTier(level="basic", traversal_depth=1, max_entities=20, enable_cross_ref=False, context_token_limit=2048),
    "pro": UserTier(level="pro", traversal_depth=3, max_entities=50, enable_cross_ref=True, context_token_limit=8192),
    "enterprise": UserTier(level="enterprise", traversal_depth=5, max_entities=200, enable_cross_ref=True, context_token_limit=32768),
}
```

---

## 8. 交叉引用（Cross Reference）

这是 M4 最具海洋工程特色的功能——在 DNV、ABS、CCS 等不同船级社之间找等价规范条目。

### 8.1 实现方式

```python
async def cross_reference(
    self, source_clause: str, source_society: str, target_society: str
) -> CrossReferenceResult | None:
    """
    1. 在图谱中搜索 source_clause 的实体节点
    2. 从该节点出发，沿 references/similar_to 边遍历
    3. 筛选目标船级社名称包含 target_society 的节点
    4. 返回匹配度最高的结果
    """
```

### 8.2 示例

用户问："ABS 哪个条目和 DNV Pt.4 Ch.3 §2.1 焊接预热要求对应？"

```
图谱搜索: DNV_Pt4_Ch3_S2.1 --[similar_to]--> ABS_Pt5B_S3.2
返回: ABS Pt.5B §3.2 Hull Structural Fire Protection (confidence: 0.85)
```

---

## 9. M2 集成

| M2 后端 | M4 用途 |
|---------|--------|
| FileStore | 读取已解析的 `full.md`，获取所有 chunk 文本 |
| RelationalDB | 存储图谱构建状态（`m4_graphs` 表：doc_id → graph_db_path → entity_count → build_at） |
| Kuzu (新增) | 存储实体和关系（独立 .db 文件，每个系统一个） |

Kuzu 数据库文件默认存放：`./data/graph/marine_rag.db`

---

## 10. 技术选型汇总

| 组件 | 选型 | 原因 |
|------|------|------|
| 图数据库 | Kuzu | 嵌入式、MIT 许可证、Cypher 查询、零服务 |
| 实体抽取 | LLM (可插拔) + 规则兜底 | 精度优先，规则保证最低可用 |
| LLM 后端 | Ollama/DeepSeek/OpenAI/Claude | 通过 M7 配置切换 |
| 格式归一化 | 三层解析（JSON → regex → fallback） | LLM 输出不稳定，需要容错 |
| 用户分级 | Basic/Pro/Enterprise | 成本控制，按需付费 |
| 交叉引用 | 图遍历 + 实体匹配 | 利用图结构，无需额外模型 |

---

## 11. 开发决策记录

| ID | 日期 | 决策 |
|----|------|------|
| M4-D01 | 2026-05-24 | Kuzu 为图数据库（MIT 嵌入式），Neo4j 留待 Phase 3 Enterprise |
| M4-D02 | 2026-05-24 | 纯 LLM 提取实体+关系，规则兜底（LLM 失败时回退） |
| M4-D03 | 2026-05-24 | 用户分三级（Basic/Pro/Enterprise），控制遍历深度和上下文量 |
| M4-D04 | 2026-05-24 | 建图离线（LLM 花费），搜索在线（图遍历免费） |
| M4-D05 | 2026-05-24 | LLM 后端通过 M7 配置选择（本地/API），支持并发控制 |
| M4-D06 | 2026-05-24 | 交叉引用通过图遍历实现，不额外调 LLM |

---

*设计规范结束。待审批后生成实现计划和任务分解。*
