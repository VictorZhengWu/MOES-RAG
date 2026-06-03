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
- **模块独立** — M4 只提供独立接口（graph_search, cross_reference），联合检索由 M5 负责

---

## 2. 模块目录结构

```
m4-knowledge-graph/
├── m4_kg/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # ExtractionConfig + LLMBackend
│   │   ├── engine.py              # KG 引擎（KGEngineProtocol）
│   │   └── tier.py                # 用户分级策略
│   │
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── rule_extractor.py      # 规则抽取（正则 + 否定词检测）
│   │   ├── llm_extractor.py       # LLM 抽取（Prompt + 格式归一化 + token 分批）
│   │   ├── merger.py              # 合并去重（LLM 优先 + 实体消歧义）
│   │   └── prompt_templates.py    # Prompt 模板（中英文）
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── kuzu_store.py          # Kuzu 图数据库（Schema + 索引 + CRUD）
│   │   ├── schema.py              # 图 Schema + 索引创建
│   │   └── traversal.py           # BFS 图遍历
│   │
│   └── search/
│       ├── __init__.py
│       ├── graph_search.py        # 图谱搜索
│       └── cross_reference.py     # 跨规范交叉引用（图遍历 + LLM 混合）
│
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_rule_extractor.py
│   ├── test_llm_extractor.py
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

## 3. M1 集成机制

### 3.1 异步触发

M1 解析完成时不阻塞用户响应。M1 通过钩子异步触发 M4：

```python
# M1 converter.py 最后阶段
async def on_parse_complete(parsed_doc: ParsedDocument):
    """M1 parse complete hook — async trigger M4 KG extraction."""
    kg_engine = get_kg_engine()
    asyncio.create_task(kg_engine.extract_entities(
        document_id=parsed_doc.doc_id,
        chunks=parsed_doc.chunks,
    ))
```

- M1 立即返回解析结果给用户（JSON 响应中多一个 `"kg_status": "building"`）
- M4 在后台建图，完成后更新标志为 `"ready"`
- 前端轮询状态 / 查 M2 RelationalDB 中 `m4_graphs` 表

### 3.2 增量更新策略

| 操作 | 图策略 |
|------|--------|
| 新增文档 | 提取实体+关系，写入 Kuzu |
| 删除文档 | CASCADE_DELETE: 删该文档专属实体；SHARED 实体保留，只减 ref_count |
| 重新解析 | 先 CASCADE_DELETE 旧实体，再提取新实体 |
| 多文档共享实体 | EH36 被 5 个文档引用，删 1 个不减 EH36，只减 ref_count |

```python
class GraphUpdateStrategy:
    CASCADE_DELETE = "cascade"  # 删除文档时删除其专属实体（ref_count == 1）
    SHARED_RETAIN = "shared"   # 多文档共享的实体保留（ref_count > 1）
    MERGE_UPDATE = "merge"     # 重新解析时合并实体
```

每个实体节点带 `ref_count`。ref_count == 1 且文档被删 → 删除实体。ref_count > 1 → 只减计数。

---

## 4. 建图管线（5 阶段）

```
M1 解析完成的文档 chunks
      │   on_parse_complete()  异步触发
      ▼
阶段 1: 规则抽取 (rule_extractor.py)
      │  正则 + 字典匹配，快速覆盖 70% 实体
      │  否定词检测：过滤 "except/excluding" 后的目标
      │  实体类型: regulation_clause, steel_grade, equipment, system_type, parameter, ship_type
      │
      ▼
阶段 2: LLM 深度抽取 (llm_extractor.py)
      │  Token 感知分批（每批 ≤ 6000 tokens，不是固定 20 个 chunk）
      │  并发控制：asyncio.Semaphore(2) 限制本地模型并发
      │  格式归一化：三层解析（json.loads → regex → 规则回退）
      │
      ▼
阶段 3: 合并去重 + 消歧义 (merger.py)
      │  同名+同类型实体合并，LLM 结果优先
      │  消歧义：regulation_clause 和 equipment 类型加船级社前缀
      │  例："§5.2" → DNV 文档中存为 "DNV-§5.2"
      │
      ▼
阶段 4: 图谱写入 (kuzu_store.py)
      │  创建节点（Entity）和边（Relation）
      │  每条边带 confidence 和 source_doc_id
      │  自动创建索引（name, entity_type, doc_society, relation_type）
      │
      ▼
阶段 5: 图谱就绪
      │  可被 graph_search() 和 cross_reference() 查询
```

---

## 5. 规则抽取（rule_extractor.py）

### 5.1 实体模式

| 实体类型 | 正则/字典 | 示例 |
|---------|-----------|------|
| steel_grade | `[A-Z]{2,4}\d{2,3}` | EH36, AH32, DH40 |
| regulation_clause | `(Pt|Part)\.?\s*\d+.*?(Ch|Chapter)\.?\s*\d+` | Pt.4 Ch.3 |
| equipment | `[A-Z]{2,4}\s+Type-[A-Z]\d+` | DNV Type-A1 |
| parameter | `\d{2,4}\s*°?[CF]\b` (温度), `\d+\.?\d*\s*mm\b` (厚度), `\d+\.?\d*\s*MPa\b` (压力) | 150°C, 50mm, 355MPa |
| ship_type | 字典匹配 | bulk carrier, oil tanker |

### 5.2 否定词检测

避免误报——"applies to all systems **except** emergency systems" 不应抽取 `applies_to(emergency)`：

```python
NEGATION_PATTERNS = [
    r"except\s+(?P<target>[^.]+)",
    r"excluding\s+(?P<target>[^.]+)",
    r"not applicable to\s+(?P<target>[^.]+)",
    r"does not apply to\s+(?P<target>[^.]+)",
]

def apply_negation_filter(text: str, matches: list) -> list:
    """Remove matches that appear within negation scope."""
    neg_targets = []
    for pattern in NEGATION_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            neg_targets.append(m.group("target").strip().lower())
    return [m for m in matches if m["target"].strip().lower() not in neg_targets]
```

---

## 6. LLM 抽取（llm_extractor.py）

### 6.1 Prompt 模板

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

### 6.2 格式归一化

LLM 输出不稳定——有时返回带 Markdown 代码块的 JSON，有时返回裸 JSON，有时多了个解释性文字。`_normalize_output()` 做三层解析：

1. 尝试 `json.loads()` 直接解析
2. 如果失败，正则提取 `{...}` JSON 块
3. 如果仍失败，记录错误并回退到规则抽取结果

### 6.3 Token 感知分批

固定 20 chunk/批不安全——长 chunk 可能超出 LLM 上下文。改用 token 估算：

```python
def estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ≈ 4 chars for English."""
    return len(text) // 4

async def batch_by_tokens(chunks: list, max_tokens: int = 6000) -> list[list]:
    """Group chunks so each batch stays within token budget."""
    batches, current_batch, current_tokens = [], [], 0
    for chunk in chunks:
        ct = estimate_tokens(chunk.text)
        if current_tokens + ct > max_tokens and current_batch:
            batches.append(current_batch)
            current_batch, current_tokens = [chunk], ct
        else:
            current_batch.append(chunk)
            current_tokens += ct
    if current_batch:
        batches.append(current_batch)
    return batches
```

### 6.4 成本控制配置

```python
@dataclass
class LLMBackend:
    provider: str   # "ollama" | "deepseek" | "openai" | "claude"
    model: str      # "DeepSeek-V3" | "gpt-4o" | etc.
    api_key: str | None = None
    base_url: str | None = None  # http://localhost:11434/v1 for Ollama

@dataclass
class ExtractionConfig:
    llm: LLMBackend | None = None
    max_chunks_per_doc: int = 200
    max_tokens_per_batch: int = 6000
    max_concurrent: int = 2           # 本地模型并发数
    fallback_to_rules: bool = True    # LLM 失败时回退规则抽取
```

---

## 7. 合并去重 + 实体消歧义（merger.py）

### 7.1 合并策略

- 规则结果 + LLM 结果合并
- 同名+同类型实体合并，**LLM 结果优先**（置信度更高）
- 规则结果补充 LLM 漏掉的实体
- 关系去重：同一对 (source, target, relation_type) 只保留一条

### 7.2 实体消歧义

同一名称在不同文档中可能指代不同实体。"§5.2" 在 DNV 文档和 ABS 文档中是不同的规范条目：

```python
def disambiguate_name(name: str, doc_society: str) -> str:
    """Qualify entity names with classification society to prevent cross-doc collision."""
    if not doc_society:
        return name
    return f"{doc_society}-{name}"  # "DNV-§5.2" vs "ABS-§5.2"

def disambiguate_entity(entity: Entity, doc_metadata: dict) -> Entity:
    """Apply disambiguation to regulation_clause and equipment entities only."""
    if entity.entity_type in ("regulation_clause", "equipment"):
        return Entity(
            entity_id=entity.entity_id,
            name=disambiguate_name(entity.name, doc_metadata.get("classification_society", "")),
            entity_type=entity.entity_type,
            properties={**entity.properties, "original_name": entity.name},
            source_doc_id=entity.source_doc_id,
        )
    return entity  # steel_grade, ship_type, etc. are global — keep as-is
```

---

## 8. Kuzu 图数据库

### 8.1 Schema

```cypher
CREATE NODE TABLE Entity(
    entity_id STRING PRIMARY KEY,
    name STRING,
    entity_type STRING,       -- "regulation_clause" | "steel_grade" | "equipment" | "system_type" | "parameter" | "ship_type"
    properties STRING,        -- JSON string: {"original_name":"§5.2", "value":"150°C", ...}
    source_doc_id STRING,
    doc_society STRING,       -- 船级社标识，用于消歧义和过滤（"DNV", "ABS", ...）
    ref_count INT64 DEFAULT 1, -- 被多少文档引用（增量更新用）
    created_at TIMESTAMP DEFAULT current_timestamp()
);

CREATE REL TABLE Rel(
    FROM Entity TO Entity,
    relation_type STRING,     -- "requires" | "applies_to" | "prohibits" | "replaces" | "references" | "constrains"
    properties STRING,        -- JSON string: {"condition":"t≤50mm", "chapter":"Pt.4 Ch.3", ...}
    confidence DOUBLE,        -- 0.0 ~ 1.0
    source_doc_id STRING,
    created_at TIMESTAMP DEFAULT current_timestamp()
);
```

### 8.2 索引

```python
async def create_indexes(conn) -> None:
    """Create Kuzu indexes for query performance."""
    await conn.execute("CREATE INDEX ON Entity(name)")         # 名称搜索（graph_search 主入口）
    await conn.execute("CREATE INDEX ON Entity(entity_type)")   # 类型过滤
    await conn.execute("CREATE INDEX ON Entity(doc_society)")  # 船级社过滤（cross_reference）
    await conn.execute("CREATE INDEX ON Rel(relation_type)")    # 关系类型过滤
    await conn.execute("CREATE INDEX ON Rel(source_doc_id)")   # 按文档删除（增量更新）
```

### 8.3 查询示例

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

## 9. 图谱搜索（独立接口）

### 9.1 M4 只提供独立接口

M4 不负责与 M3 的联合——那是 M5 的职责。保持模块独立性。

| 接口 | 输入 | 输出 | 用途 |
|------|------|------|------|
| `graph_search(topic, depth)` | 主题词 + 遍历深度 | `Subgraph` | 图谱探索 |
| `cross_reference(clause, src_soc, tgt_soc)` | 规范条目 + 两个船级社 | `CrossReferenceResult` | 跨规范映射 |

### 9.2 M5 并行调用 M3+M4

```
M5 查询："EH36 焊接要求"
    │
    ├──→ M3 retrieve()      → 语义相关的文档 chunk
    │        延迟: <500ms
    │
    └──→ M4 graph_search()  → EH36 关联的实体和关系
             延迟: <50ms
    │
    ▼
M5 综合两路结果 → 生成答案
```

CombinedRetrievalResult 定义在 M5 的 contracts 中，不在 M4：

```python
# In contracts/retrieval.py (M5), not in M4:
@dataclass
class CombinedRetrievalResult:
    chunks: list[ScoredChunk]        # 来自 M3
    graph: Subgraph                   # 来自 M4
    cross_refs: list[CrossReferenceResult]
    latency_ms: float
```

图遍历本身**不消耗 LLM token**——只查 Kuzu。遍历结果越多 → M5 喂给 LLM 的上下文越多 → Token 消耗越大。

---

## 10. 交叉引用（Cross Reference）

### 10.1 混合策略

| 策略 | 机制 | 准确率 | 覆盖率 |
|------|------|:--:|:--:|
| 图遍历 | 查已有 `similar_to` 边 | 高 | 低（需预标注） |
| LLM 实时 | 比较两个条目的语义 | 中高 | 高 |
| 混合（默认） | 先图后 LLM，结果缓存为图边 | 高 | 高 |

```python
async def cross_reference(self, source_clause, source_society, target_society):
    """Find equivalent clause across classification societies."""
    # Step 1: Graph lookup (fast, free)
    result = await self._graph_lookup(source_clause, target_society)
    if result and result.confidence > 0.8:
        return result

    # Step 2: LLM fallback (slow, costs tokens — one-time)
    result = await self._llm_cross_reference(source_clause, source_society, target_society)
    if result and result.confidence > 0.6:
        # Cache as graph edge for future queries
        await self._add_similar_to_edge(source_clause, result.target_clause, result.confidence)
    return result
```

### 10.2 示例

用户问："ABS 哪个条目和 DNV Pt.4 Ch.3 §2.1 焊接预热要求对应？"

```
图谱搜索: DNV_Pt4_Ch3_S2.1 --[similar_to]--> ABS_Pt5B_S3.2
返回: ABS Pt.5B §3.2 Hull Structural Fire Protection (confidence: 0.85)
```

---

## 11. 用户分级策略

| 等级 | 图遍历深度 | 返回实体数 | 交叉引用 | M5 上下文上限 | 预估成本/查询 |
|------|:--:|:--:|:--:|:--:|:--:|
| Basic | 1 | 20 | ❌ | 2K tokens | ~$0.002 |
| Pro | 3 | 50 | ✅ 同规范内 | 8K tokens | ~$0.01 |
| Enterprise | 5 | 200 | ✅ 跨规范全量 | 32K tokens | ~$0.05 |

### 11.1 配置注入

```python
@dataclass
class UserTier:
    level: str = "basic"
    traversal_depth: int = 1
    max_entities: int = 20
    enable_cross_ref: bool = False
    context_token_limit: int = 2048

USER_TIERS = {
    "basic":      UserTier(level="basic", traversal_depth=1, max_entities=20, enable_cross_ref=False, context_token_limit=2048),
    "pro":        UserTier(level="pro", traversal_depth=3, max_entities=50, enable_cross_ref=True, context_token_limit=8192),
    "enterprise": UserTier(level="enterprise", traversal_depth=5, max_entities=200, enable_cross_ref=True, context_token_limit=32768),
}
```

---

## 12. M2 集成

| M2 后端 | M4 用途 |
|---------|--------|
| FileStore | 读取已解析的文档 chunk 文本 |
| RelationalDB | 存储图谱构建状态（`m4_graphs` 表：doc_id → graph_db_path → entity_count → built_at → status） |
| Kuzu（新增，独立文件） | 主图谱存储（`./data/graph/marine_rag.db`） |

---

## 13. 技术选型汇总

| 组件 | 选型 | 原因 |
|------|------|------|
| 图数据库 | Kuzu | 嵌入式、MIT、Cypher、零服务 |
| 实体抽取 | LLM（可插拔）+ 规则兜底 | 精度优先，规则保证最低可用 |
| LLM 后端 | Ollama / DeepSeek / OpenAI / Claude | 通过 M7 配置切换 |
| 格式归一化 | 三层解析（JSON → regex → fallback） | LLM 输出不稳定 |
| Token 分批 | 按字符估算（1 tok ≈ 4 chars），≤6000/批 | 防止超上下文 |
| 实体消歧义 | 船级社前缀（regulation_clause, equipment） | 防止跨文档命名冲突 |
| 否定词检测 | 正则过滤 except/excluding/not applicable to | 防止误报 |
| 增量更新 | CASCADE_DELETE + SHARED_RETAIN (ref_count) | 支持文档增删改 |
| 交叉引用 | 图遍历 + LLM fallback + 结果缓存 | 先免费后付费 |
| 联合检索 | M5 并行调用 M3+M4 | 保持模块独立性 |
| 用户分级 | Basic / Pro / Enterprise（深度+实体数限制） | 成本控制 |

---

## 14. 开发决策记录

| ID | 日期 | 决策 |
|----|------|------|
| M4-D01 | 2026-05-24 | Kuzu 为图数据库（MIT 嵌入式），Neo4j 留待 Phase 3 Enterprise |
| M4-D02 | 2026-05-24 | 纯 LLM 提取实体+关系，规则兜底（LLM 失败时回退） |
| M4-D03 | 2026-05-24 | 用户分三级（Basic/Pro/Enterprise），控制遍历深度和上下文量 |
| M4-D04 | 2026-05-24 | 建图离线（LLM 花费），搜索在线（图遍历免费） |
| M4-D05 | 2026-05-24 | LLM 后端通过 M7 配置选择（本地/API），支持并发控制 |
| M4-D06 | 2026-05-24 | 交叉引用混合策略：先图遍历 → 无结果则 LLM → 结果缓存为图边 |
| M4-D07 | 2026-05-24 | M4 不实现 combined_search — M5 并行调用 M3+M4 并合并 |
| M4-D08 | 2026-05-24 | M1 解析完成后异步触发 M4 建图，不阻塞用户响应 |
| M4-D09 | 2026-05-24 | 增量更新：CASCADE_DELETE 删专属实体，SHARED_RETAIN 保留共享实体（ref_count） |
| M4-D10 | 2026-05-24 | 实体消歧义：regulation_clause 和 equipment 加船级社前缀（"DNV-§5.2"） |
| M4-D11 | 2026-05-24 | 否定词检测：规则抽取前过滤 except/excluding/not applicable to |
| M4-D12 | 2026-05-24 | Token 感知分批：按字符估算（1 tok ≈ 4 chars），每批 ≤ 6000 tokens |

---

## 15. 子任务列表（9 个）

| 编号 | 名称 | 类型 | 依赖 |
|------|------|------|------|
| 00080-01 | 骨架 + 配置（config.py + tier.py + pyproject.toml） | 原子 | 无 |
| 00080-02 | 规则抽取器（rule_extractor.py + 否定词检测） | 模块 | 无 |
| 00080-03 | LLM 抽取器（llm_extractor.py + prompt_templates.py + token 分批） | 模块 | -02 |
| 00080-04 | 合并去重 + 实体消歧义（merger.py） | 原子 | -02, -03 |
| 00080-05 | Kuzu 存储（kuzu_store.py + schema.py + 索引） | 模块 | -04 |
| 00080-06 | 图遍历（traversal.py + 深度限制） | 原子 | -05 |
| 00080-07 | 图谱搜索 + 交叉引用（graph_search.py + cross_reference.py 混合策略） | 模块 | -06 |
| 00080-08 | 主引擎 + M1 异步集成（engine.py + m2_bridge.py + on_parse_complete 钩子） | 集成 | -07, M1, M2 |
| 00080-09 | 打包验证（requirements.txt + 全量测试） | 集成 | -01~-08 |

```
依赖关系图：
00080-01 (config) ──→ 00080-08 (engine)
00080-02 (rules)  ──→ 00080-04 (merge) ──→ 00080-05 (Kuzu) ──→ 00080-06 (traversal) ──→ 00080-07 (search) ──→ 00080-09 (packaging)
00080-03 (LLM)    ──→
```
