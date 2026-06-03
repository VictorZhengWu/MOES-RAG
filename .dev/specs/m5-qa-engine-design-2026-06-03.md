# M5 智能问答引擎 — 详细设计规范

> **日期**：2026-06-03 | **版本**：v2（折中方案） | **状态**：待审批
> **依赖**：contracts/ (00010), M2 (00050), M3 (00070), M4 (00080)
> **定位**：Layer 3 (Brain)，系统总调度中心——检索→图搜索→LLM 生成→引用溯源

---

## 1. 模块定位

M5 是整个系统的"大脑"。接收用户问题，根据用户等级选择运行模式，并行调用 M3（语义检索）和 M4（图谱搜索），融合检索结果送给 LLM 生成答案，附带来源引用。

**核心原则**：

- **一套引擎，三种模式** — 通过 mode 参数切换管线深度，不建三套系统
- **LLM 可插拔** — 单一 LLM 客户端，OpenAI 兼容 API 覆盖 Ollama/DeepSeek/OpenAI/Claude
- **分级服务 + 动态预算** — Basic/Pro/Enterprise 上下文窗口差异化（4K/8K/16K）+ Premium 临时升级
- **引用溯源** — 每条答案绑定来源（文档→章节→条款→摘录）
- **OpenAI 兼容 API** — `/v1/chat/completions` 格式，M6/M7 无缝对接
- **Prompt 数据库管理** — SQLite 存储模板，多语言支持，Phase 3 加版本控制和 A/B 测试
- **可观测性** — 结构化日志 + 延迟/token/模式统计

---

## 2. 三种运行模式

```
用户请求 "EH36 焊接板厚要求"
          │
          ▼
    ┌─ 等级检查 ─────────────────────────────────────┐
    │  Basic → mode="simple"          (4K context)    │
    │  Pro   → mode="pipeline"        (8K context)    │
    │  Enterprise → mode="self_rag"   (16K context)   │
    │  (Premium 次数可临时升级一档)                    │
    └────────────────────────────────────────────────┘
          │
          ▼
mode "simple"     mode "pipeline"      mode "self_rag"
──────────────    ────────────────     ──────────────────
M3 检索           M3 + M4 并行         M3 + M4 并行
    │                  │                    │
    ▼                  ▼                    ▼
M3 chunks → LLM   融合 + 引用溯源       评估相关性
    │                  │                  ⚠️ 不够？
    ▼                  ▼                    └→ 改查询重检索
返回答案           LLM 生成                ✅ 够了
                       │                    │
                       ▼                    ▼
                  返回答案+引用           LLM 生成
                                          ⚠️ 引用弱？
                                            └→ 补充检索
                                          ✅
                                            │
                                            ▼
                                        返回答案+引用
```

### 2.1 各模式延迟与成本

| 模式 | LLM 调用次数 | M3/M4 调用 | 延迟 | 成本/查询 |
|------|:--:|:--:|------|:--:|
| simple | 1 | 1 次 M3 | ~1-3s | ~$0.002 |
| pipeline | 1 | 1 次 M3 + 1 次 M4 | ~2-5s | ~$0.005 |
| self_rag | 2-4 | 2-3 次 M3 | ~5-15s | ~$0.02-0.05 |

---

## 3. 用户等级与 Premium 机制

### 3.1 等级定义

| 等级 | 默认模式 | 上下文窗口 | 每日 Premium 次数 | Premium 模式 |
|------|---------|:--:|:--:|------|
| Basic | simple | 4K | 3 | self_rag |
| Pro | pipeline | 8K | 10 | self_rag |
| Enterprise | self_rag | 16K | 无限 | — |

### 3.2 Premium 配额管理

```python
@dataclass
class PremiumQuota:
    user_id: str
    date: str           # "2026-06-03"
    total: int          # 每日总额
    used: int = 0       # 已用次数

    def can_use(self) -> bool:
        return self.used < self.total

    def consume(self) -> bool:
        if not self.can_use():
            return False
        self.used += 1
        return True
```

- 配额存储在 M2 SQLite 的 `m5_quotas` 表
- 每日零点自动重置
- 前端可通过 API 查询剩余 Premium 次数

---

## 4. 动态 Token 预算分配

按**用户等级**分配比例，不按查询复杂度（避免循环依赖）：

```python
TOKEN_BUDGETS = {
    "basic":      {"retrieval": 0.30, "history": 0.20, "generation": 0.50},  # 4K → 检索 1.2K, 历史 0.8K, 生成 2K
    "pro":        {"retrieval": 0.40, "history": 0.20, "generation": 0.40},  # 8K → 检索 3.2K, 历史 1.6K, 生成 3.2K
    "enterprise": {"retrieval": 0.50, "history": 0.20, "generation": 0.30},  # 16K → 检索 8K, 历史 3.2K, 生成 4.8K
}
```

- Basic 偏重生成（检索少、回答简洁）
- Pro 均衡分配
- Enterprise 偏重检索（海量上下文 → 深度推理）

---

## 5. 模块目录结构

```
m5-qa-engine/
├── m5_qa/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # QAConfig: LLM backend, tier, token budget
│   │   ├── engine.py              # QAEngine 主类（实现 QAEngineProtocol）
│   │   ├── tier.py                # UserTier + PremiumQuota
│   │   └── router.py              # 模式路由器
│   │
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── llm_client.py          # 统一 LLM 客户端（OpenAI 兼容，覆盖 4 种后端）
│   │   ├── prompt_manager.py      # Prompt 管理器（DB 存储，中英文，Phase 3 加版本控制）
│   │   └── streaming.py           # SSE 流式生成
│   │
│   ├── pipelines/
│   │   ├── __init__.py
│   │   ├── simple.py              # Simple 模式：M3 检索 → LLM 生成
│   │   ├── pipeline.py            # Pipeline 模式：M3+M4 并行 → 融合+引用 → LLM
│   │   └── self_rag.py            # Self-RAG 模式：评估 → 重检索 → 回溯（最多 3 次）
│   │
│   ├── context/
│   │   ├── __init__.py
│   │   ├── retriever.py           # M3/M4 并行调用封装
│   │   ├── fusion.py              # 检索结果 + 图搜索结果融合
│   │   ├── citation_builder.py    # 引用溯源
│   │   └── token_budget.py        # Token 估算 + 动态预算分配
│   │
│   ├── conversation/
│   │   ├── __init__.py
│   │   ├── manager.py             # 对话 CRUD（M2 SQLite）
│   │   └── compressor.py          # 上下文压缩
│   │
│   └── monitoring/
│       ├── __init__.py
│       ├── metrics.py             # 延迟/token/模式统计
│       └── logger.py              # 结构化日志
│
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_tier.py
│   ├── test_router.py
│   ├── test_llm_client.py
│   ├── test_prompt_manager.py
│   ├── test_citation_builder.py
│   ├── test_token_budget.py
│   ├── test_retriever.py
│   ├── test_fusion.py
│   ├── test_simple.py
│   ├── test_pipeline.py
│   ├── test_self_rag.py
│   ├── test_conversation_manager.py
│   ├── test_compressor.py
│   ├── test_engine.py
│   ├── test_streaming.py
│   └── test_metrics.py
│
├── pyproject.toml
└── requirements.txt
```

### 5.1 与对方方案的取舍

| 对方方案组件 | 是否采纳 | 说明 |
|------|:--:|------|
| `prompt_manager.py` (DB 存储) | ✅ 采纳 | 加 `prompt_manager.py`，SQLite 存模板，中英文。先不做版本/A/B（Phase 3） |
| 动态 Token 预算 | ✅ 采纳 | 按用户等级分配比例，不按查询复杂度（避免循环依赖） |
| `monitoring/` | ✅ 采纳 | 加 `metrics.py` + `logger.py` |
| 上下文窗口差异化 | ✅ 采纳 | Basic 4K / Pro 8K / Enterprise 16K |
| `llm/providers/` 独立文件 | ❌ 拒绝 | 保持单个 `llm_client.py`，统一 OpenAI 兼容 API |
| Prompt A/B 测试 | ⚠️ 推迟 | Phase 3 |
| 查询类型判断 | ⚠️ 推迟 | Phase 3 |

---

## 6. Prompt 管理器（prompt_manager.py）

### 6.1 存储

M2 SQLite 新表 `m5_prompts`：

```sql
CREATE TABLE m5_prompts (
    prompt_id TEXT PRIMARY KEY,       -- "system_en", "system_cn", "citation_en", ...
    name TEXT NOT NULL,               -- "System Prompt (EN)", "系统提示 (CN)"
    language TEXT NOT NULL,           -- "en" | "cn"
    content TEXT NOT NULL,            -- 完整 Prompt 模板文本
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.2 接口

```python
class PromptManager:
    """DB-backed prompt template store with multi-language support."""

    def __init__(self, db_path: str):
        ...

    async def get_prompt(self, prompt_id: str) -> str:
        """Fetch a single prompt template by ID."""
        ...

    async def get_prompt_by_language(self, base_id: str, language: str) -> str:
        """Fetch prompt with fallback: language → en → hardcoded default."""
        ...

    async def set_prompt(self, prompt_id: str, name: str, language: str, content: str) -> None:
        """Insert or update a prompt template."""
        ...

    async def list_prompts(self) -> list[dict]:
        """List all stored prompts."""
        ...
```

### 6.3 模板变量

Prompt 模板使用 `{variable}` 占位符，运行时填充：

```python
SYSTEM_PROMPT_EN = """You are a Marine & Offshore Engineering expert assistant.
Answer questions based STRICTLY on the provided context documents.
If the context does not contain sufficient information, say so.
Always cite the source regulation and clause when answering.

## Context Documents
{retrieved_context}

## Knowledge Graph Insights
{graph_context}

## Instructions
- Answer in the same language as the question
- Include specific technical values when available
- Cite sources using [number] format matching the citations list
- For regulatory questions, note the classification society and clause"""
```

---

## 7. 动态 Token 预算（token_budget.py）

```python
@dataclass
class TokenBudget:
    total: int            # 总 token 预算（由等级决定）
    retrieval_ratio: float
    history_ratio: float
    generation_ratio: float

    @property
    def retrieval_limit(self) -> int:
        return int(self.total * self.retrieval_ratio)

    @property
    def history_limit(self) -> int:
        return int(self.total * self.history_ratio)

    @property
    def generation_limit(self) -> int:
        return int(self.total * self.generation_ratio)

def estimate_tokens(text: str) -> int:
    """Rough: 1 token ≈ 4 chars for English, ≈ 2 chars for Chinese."""
    return len(text) // 4

def allocate_budget(tier: str) -> TokenBudget:
    """Allocate token budget based on user tier."""
    budgets = {
        "basic":      (4000,  0.30, 0.20, 0.50),
        "pro":        (8000,  0.40, 0.20, 0.40),
        "enterprise": (16000, 0.50, 0.20, 0.30),
    }
    total, ret, hist, gen = budgets.get(tier, budgets["basic"])
    return TokenBudget(total=total, retrieval_ratio=ret, history_ratio=hist, generation_ratio=gen)
```

---

## 8. 核心接口设计

### 8.1 QAEngine（实现 QAEngineProtocol）

```python
class QAEngine:
    """The 'brain' of the Marine & Offshore Expert System."""

    def __init__(self, config: QAConfig | None = None):
        self._config = config or QAConfig()
        self._router = ModeRouter()
        self._llm_client = LLMClient(self._config.llm)
        self._prompt_manager = PromptManager(self._config.db_path)
        self._metrics = MetricsCollector()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        t0 = time.perf_counter()
        # 1. Determine mode from user tier + Premium quota
        mode, tier_info = self._router.select_mode(request.user)
        budget = allocate_budget(tier_info.level)
        # 2. Execute pipeline
        result = await self._execute(mode, request, budget)
        # 3. Collect metrics
        self._metrics.record_query(
            mode=mode, latency_ms=(time.perf_counter()-t0)*1000,
            tokens_used=result.usage.total_tokens if result.usage else 0,
        )
        return result

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        ...

    # --- Conversation management ---
    async def list_conversations(self, user_id, limit=50, offset=0) -> list[ConversationSummary]:
        ...
    async def get_conversation(self, conversation_id, user_id) -> list[Message]:
        ...
    async def delete_conversation(self, conversation_id, user_id) -> bool:
        ...

    # --- Model management ---
    async def list_models(self) -> list[dict[str, Any]]:
        ...
    async def health_check(self) -> dict[str, Any]:
        ...
```

### 8.2 数据模型

```python
@dataclass
class RetrievalContext:
    """Merged context from both M3 and M4 retrievals."""
    chunks: list[ScoredChunk]        # From M3
    graph: Subgraph | None            # From M4 (None if simple mode)
    cross_refs: list[CrossReferenceResult]

@dataclass  
class PromptContext:
    """Fully built prompt ready for LLM."""
    system_prompt: str
    messages: list[Message]           # System + history + current user query
    citations: list[Citation]
    token_count: int
```

---

## 9. LLM 客户端（llm_client.py）

### 9.1 统一接口

单一客户端，通过 base_url 区分后端：

```python
@dataclass
class LLMBackend:
    provider: str    # "ollama" | "deepseek" | "openai" | "claude"
    model: str       # "DeepSeek-V3" | "gpt-4o" | "claude-sonnet-4-20250514"
    api_key: str | None = None
    base_url: str | None = None

class LLMClient:
    """Unified LLM interface via OpenAI-compatible API.

    Covers Ollama (localhost:11434/v1), DeepSeek (api.deepseek.com/v1),
    OpenAI (api.openai.com/v1), Claude (via Anthropic-compatible proxy).
    """

    def __init__(self, backend: LLMBackend):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            api_key=backend.api_key or "not-needed",
            base_url=backend.base_url or "http://localhost:11434/v1",
        )
        self._model = backend.model

    async def complete(self, messages: list, **kwargs) -> ChatResponse:
        ...

    async def complete_stream(self, messages: list, **kwargs) -> AsyncIterator[str]:
        ...
```

### 9.2 为什么不用独立 provider 文件

Ollama、DeepSeek、OpenAI 都支持 OpenAI 兼容的 `/v1/chat/completions` 端点——唯一的区别是 `base_url` 和 `api_key`。Claude 也可通过兼容代理。4 个文件 → 1 个文件，减少维护成本。

---

## 10. 对话管理

### 10.1 存储（M2 SQLite）

```sql
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,   -- "user" | "assistant" | "system"
    content TEXT NOT NULL,
    citations_json TEXT,  -- JSON array of Citation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
);

CREATE TABLE m5_quotas (
    user_id TEXT NOT NULL,
    date TEXT NOT NULL,           -- "2026-06-03"
    tier TEXT NOT NULL,
    premium_used INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, date)
);
```

### 10.2 上下文压缩

```python
class ContextCompressor:
    def compress(self, messages: list[Message], max_tokens: int) -> list[Message]:
        """Keep last N full messages within budget; truncate old messages."""
        ...
```

---

## 11. Self-RAG 循环

最多 3 次迭代，包含 4 个检查点：

```
for iteration in range(max_iterations=3):
    1. 检索 (M3 + M4)
       ↓
    2. 评估器: 检索结果与问题的关键词命中率 ≥ 0.3？
       NO → 改查询措辞，回到步骤 1
       YES ↓
    3. 生成器: LLM 生成答案
       ↓
    4. 引用验证器: chunk 文本在答案中的覆盖率 ≥ 0.3？
       NO → 补充检索新关键词，回到步骤 1
       YES → 返回最终答案
```

### 11.1 评估器（规则版，Phase 2）

```python
class RelevanceEvaluator:
    """Phase 2: rule-based relevance check using keyword hit rate."""

    def evaluate(self, query: str, chunks: list[ScoredChunk]) -> EvaluationResult:
        keywords = set(query.lower().split())
        hits = sum(1 for c in chunks if any(kw in c.chunk.text.lower() for kw in keywords))
        score = hits / max(len(chunks), 1)
        return EvaluationResult(
            score=score,
            sufficient=score >= 0.3,
            missing_keywords=[] if score >= 0.3 else list(keywords)[:5],
        )
```

### 11.2 引用验证器（规则版，Phase 2）

```python
class CitationVerifier:
    """Phase 2: rule-based citation coverage check."""

    def verify(self, answer: str, chunks: list[ScoredChunk]) -> VerificationResult:
        covered = sum(1 for c in chunks if c.chunk.text[:50] in answer)
        coverage = covered / max(len(chunks), 1) if chunks else 0.0
        return VerificationResult(coverage=coverage, sufficient=coverage >= 0.3)
```

Phase 3 升级为 LLM 评估器（更准确，但有成本）。

---

## 12. M3/M4 集成

### 12.1 并行调用

```python
async def retrieve_context(query: str, mode: str, tier_level: str) -> RetrievalContext:
    """Fetch context from M3 and optionally M4 in parallel."""
    if mode == "simple":
        m3_result = await m3_engine.retrieve(RetrievalRequest(query=query))
        return RetrievalContext(chunks=m3_result.chunks, graph=None, cross_refs=[])

    # pipeline / self_rag: parallel M3 + M4
    m3_task = m3_engine.retrieve(RetrievalRequest(query=query))
    m4_task = m4_engine.graph_search(topic=query, depth=TRAVERSAL_DEPTH[tier_level])
    m3_result, m4_result = await asyncio.gather(m3_task, m4_task)
    return RetrievalContext(chunks=m3_result.chunks, graph=m4_result, cross_refs=[])
```

---

## 13. 监控（monitoring/）

### 13.1 度量收集

```python
@dataclass
class QueryMetrics:
    mode: str               # "simple" | "pipeline" | "self_rag"
    latency_ms: float
    tokens_used: int
    tier: str               # "basic" | "pro" | "enterprise"
    timestamp: float

class MetricsCollector:
    def record_query(self, **kwargs):
        """Log structured metrics for later analysis."""
        ...

    def get_summary(self) -> dict:
        """Return aggregated metrics: avg latency, mode distribution."""
        ...
```

### 13.2 结构化日志

```python
# logger.py
import logging, json

class StructuredLogger:
    @staticmethod
    def log_query(user_id, query, mode, latency_ms, token_count):
        logging.info(json.dumps({
            "event": "query", "user_id": user_id,
            "mode": mode, "latency_ms": latency_ms,
            "token_count": token_count, "query_preview": query[:100],
        }))
```

---

## 14. 子任务列表（9 个）

| 编号 | 名称 | 类型 | 依赖 |
|------|------|------|------|
| 00090-01 | 骨架 + 配置 + 等级系统（config/tier/router + pyproject.toml） | 原子 | 无 |
| 00090-02 | LLM 客户端 + 流式（llm_client.py + streaming.py） | 模块 | -01 |
| 00090-03 | Prompt 管理器（prompt_manager.py + SQLite 模板库） | 原子 | 无 |
| 00090-04 | 引用溯源 + Token 预算（citation_builder.py + token_budget.py） | 原子 | 无 |
| 00090-05 | 检索融合 + 上下文构建（retriever.py + fusion.py） | 模块 | 无 |
| 00090-06 | 三种管线（simple/pipeline/self_rag） | 模块 | -02, -05 |
| 00090-07 | 对话管理 + 上下文压缩（manager.py + compressor.py） | 模块 | -01 |
| 00090-08 | 主引擎 + 监控（engine.py + monitoring/metrics.py + logger.py） | 集成 | -03, -04, -06, -07 |
| 00090-09 | 打包验证 | 集成 | -01~-08 |

```
依赖关系图：

00090-01 (config+tier)
    ├──→ 00090-02 (LLM client) ──┐
    ├──→ 00090-07 (conversation)  │
    │                              │
00090-03 (prompt manager) ←—— 可并行于 02/04/05/07
00090-04 (citation+token) ←—— 可并行于 02/03/05/07
00090-05 (retriever)     ←—— 可并行于 02/03/04/07
                                   │
                                   ▼
                            00090-06 (pipelines)
                                   │
                                   ▼
                            00090-08 (engine + monitoring)
                                   │
                                   ▼
                            00090-09 (packaging)
```

00090-02、00090-03、00090-04、00090-05、00090-07 全部可并行——5 个 agent 同时开工。

---

## 15. 技术选型汇总

| 组件 | 选型 | 原因 |
|------|------|------|
| LLM API | `openai.AsyncOpenAI` | 统一覆盖 Ollama/DeepSeek/OpenAI/Claude |
| 流式生成 | SSE | M6 前端已支持 |
| Prompt 存储 | M2 SQLite (`m5_prompts`) | 零新增依赖 |
| 对话存储 | M2 SQLite (`conversations`, `messages`) | 一致技术栈 |
| 配额存储 | M2 SQLite (`m5_quotas`) | 轻量 |
| Token 估算 | 字符数 ÷ 4 | 快速近似 |
| 评估器/验证器 | 规则版（关键词命中率） | Phase 3 升级 LLM |
| 监控 | `MetricsCollector` + 结构化 JSON 日志 | 无额外依赖 |

---

## 16. 开发决策记录

| ID | 日期 | 决策 |
|----|------|------|
| M5-D01 | 2026-06-03 | 一套引擎三种模式（simple/pipeline/self_rag），不建三套系统 |
| M5-D02 | 2026-06-03 | Basic 每日 3 次 Premium，Pro 每日 10 次 |
| M5-D03 | 2026-06-03 | OpenAI 兼容 API 格式，与 M6/M7 前端对齐 |
| M5-D04 | 2026-06-03 | 评估器和引用验证器 Phase 2 用规则实现，Phase 3 升级 LLM |
| M5-D05 | 2026-06-03 | 对话和 Prompt 存 M2 SQLite，不引入新数据库 |
| M5-D06 | 2026-06-03 | 动态 Token 预算：按用户等级分配比例，不按查询复杂度 |
| M5-D07 | 2026-06-03 | Self-RAG 循环最多 3 次迭代 |
| M5-D08 | 2026-06-03 | 上下文窗口差异化：Basic 4K / Pro 8K / Enterprise 16K |
| M5-D09 | 2026-06-03 | 单一 LLM 客户端覆盖所有后端，不建独立 provider 文件 |
| M5-D10 | 2026-06-03 | Prompt 管理器 DB 存储中英文模板，Phase 3 加版本控制 |
| M5-D11 | 2026-06-03 | 结构化日志 + MetricsCollector 监控延迟/token/模式 |

---

*设计规范 v2 结束。待审批后开始编码。*
