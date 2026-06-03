# M5 智能问答引擎 — 详细设计规范

> **日期**：2026-06-03 | **状态**：待审批
> **依赖**：contracts/ (00010), M2 (00050), M3 (00070), M4 (00080)
> **定位**：Layer 3 (Brain)，系统总调度中心——检索→图搜索→LLM 生成→引用溯源

---

## 1. 模块定位

M5 是整个系统的"大脑"。接收用户问题，根据用户等级选择运行模式，并行调用 M3（语义检索）和 M4（图谱搜索），把检索结果融合后送给 LLM 生成答案，附带来源引用。

**核心原则**：

- **一套引擎，三种模式** — 不建三套系统，通过 mode 参数切换管线深度
- **LLM 可插拔** — 通过 M7 配置选本地模型或远程 API
- **分级服务** — Basic/Pro/Enterprise 默认模式不同，Premium 次数可临时升级
- **引用溯源** — 每条答案绑定来源（文档→章节→条款→摘录）
- **OpenAI 兼容 API** — `/v1/chat/completions` 格式，M6/M7 无缝对接

---

## 2. 三种运行模式

```
用户请求 "EH36 焊接板厚要求"
          │
          ▼
    ┌─ 等级检查 ─────────────────────────────────────┐
    │  Basic → mode="simple"                          │
    │  Pro   → mode="pipeline"                        │
    │  Enterprise → mode="self_rag"                   │
    │  (Premium 次数可临时升级一档)                    │
    └────────────────────────────────────────────────┘
          │
          ▼
mode "simple"     mode "pipeline"      mode "self_rag"
──────────────    ────────────────     ──────────────────
M3 检索           M3 + M4 并行         M3 + M4 并行
    │                  │                    │
    ▼                  ▼                    ▼
拼接上下文        融合 + 引用溯源       评估相关性
    │                  │                  ⚠️ 不够？
    ▼                  ▼                    └→ 改查询重检索
LLM 生成           LLM 生成                ✅ 够了
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

| 等级 | 默认模式 | 每日 Premium 次数 | Premium 模式 |
|------|---------|:--:|------|
| Basic | simple | 3 | self_rag |
| Pro | pipeline | 10 | self_rag |
| Enterprise | self_rag | 无限 | — |

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
- 前端可以通过 API 查询剩余 Premium 次数

---

## 4. 模块目录结构

```
m5-qa-engine/
├── m5_qa/
│   ├── __init__.py                 # 公开 API：QAEngine
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              # QAConfig: LLM backend, tier, quota settings
│   │   ├── engine.py              # QAEngine 主类（实现 QAEngineProtocol）
│   │   ├── tier.py                # UserTier 副本 + Premium 配额逻辑
│   │   └── router.py              # 模式路由器（根据等级选 simple/pipeline/self_rag）
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── simple.py              # Simple 模式：M3 检索 → LLM 生成
│   │   ├── pipeline.py            # Pipeline 模式：M3+M4 并行 → 融合 → LLM
│   │   └── self_rag.py            # Self-RAG 模式：评估 → 重检索 → 回溯
│   │
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── llm_client.py          # LLM 客户端（OpenAI 兼容 API，覆盖 Ollama/DeepSeek/Claude）
│   │   ├── prompt_builder.py      # Prompt 构建（系统提示、上下文拼接、历史对话）
│   │   └── streaming.py           # SSE 流式生成
│   │
│   ├── context/
│   │   ├── __init__.py
│   │   ├── retriever.py           # M3/M4 并行调用封装
│   │   ├── fusion.py              # 检索结果 + 图搜索结果融合
│   │   └── citation_builder.py    # 引用溯源（从 chunk 元数据构建 Citation）
│   │
│   └── conversation/
│       ├── __init__.py
│       ├── manager.py             # 对话管理（CRUD + 历史上下文窗口）
│       └── compressor.py          # 上下文压缩（总结旧对话、token 预算分配）
│
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_tier.py
│   ├── test_router.py
│   ├── test_simple.py
│   ├── test_pipeline.py
│   ├── test_self_rag.py
│   ├── test_llm_client.py
│   ├── test_prompt_builder.py
│   ├── test_citation_builder.py
│   ├── test_retriever.py
│   ├── test_fusion.py
│   ├── test_conversation_manager.py
│   ├── test_compressor.py
│   ├── test_engine.py
│   └── test_streaming.py
│
├── pyproject.toml
└── requirements.txt
```

---

## 5. 核心接口设计

### 5.1 QAEngine（实现 QAEngineProtocol）

```python
class QAEngine:
    """The 'brain' of the Marine & Offshore Expert System."""

    def __init__(self, config: QAConfig | None = None):
        ...

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Non-streaming chat completion."""
        # 1. Determine mode from user tier + Premium quota
        mode = self._router.select_mode(request.user, request.messages[-1].content)
        # 2. Execute pipeline
        result = await self._execute(mode, request)
        # 3. Build response with citations
        return ChatResponse(...)

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Streaming chat completion (SSE)."""
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
        """Verify M3, M4, LLM backend, and conversation store."""
        ...
```

### 5.2 检索上下文融合器

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
    user_prompt: str
    citations: list[Citation]
    token_count: int
```

---

## 6. Prompt 构建

### 6.1 系统 Prompt

```python
SYSTEM_PROMPT = """You are a Marine & Offshore Engineering expert assistant.
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

### 6.2 上下文窗口分配

```
Token budget (total: 8K for Pro):
├── System prompt:      ~300 tokens
├── Retrieved chunks:   ~4K tokens (M3)
├── Graph context:      ~1K tokens (M4)
├── Conversation hist:  ~2K tokens (last N messages)
└── Generation reserve: ~700 tokens (answer)
```

---

## 7. LLM 客户端

```python
@dataclass
class LLMBackend:
    provider: str    # "ollama" | "deepseek" | "openai" | "claude"
    model: str       # "DeepSeek-V3" | "gpt-4o" | "claude-sonnet-4-20250514"
    api_key: str | None = None
    base_url: str | None = None

class LLMClient:
    """Unified LLM interface via OpenAI-compatible API."""

    async def complete(self, messages: list[Message], **kwargs) -> ChatResponse:
        """Non-streaming completion."""
        ...

    async def complete_stream(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        """Streaming completion (SSE chunks)."""
        ...
```

--- 

## 8. 对话管理

### 8.1 存储

使用 M2 SQLite 存储对话：

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
```

### 8.2 上下文压缩

对话超过 token 预算时压缩旧消息：

```python
class ContextCompressor:
    def compress(self, messages: list[Message], max_tokens: int) -> list[Message]:
        """Keep last N messages + summarize older messages."""
        ...
```

---

## 9. Self-RAG 循环

最复杂的模式，包含 4 个检查点：

```
for iteration in range(max_iterations=3):
    1. 检索 (M3 + M4)
       ↓
    2. 评估器: 检索结果与问题的相关性 ≥ 阈值？
       NO → 改查询措辞，回到步骤 1
       YES ↓
    3. 生成器: LLM 生成答案
       ↓
    4. 引用验证器: 每句有引用？ 引用覆盖率 ≥ 80%？
       NO → 补充检索，回到步骤 1
       YES → 返回最终答案
```

### 9.1 评估器

```python
class RelevanceEvaluator:
    """Judge whether retrieved context is sufficient."""

    async def evaluate(self, query: str, context: RetrievalContext) -> EvaluationResult:
        """
        Returns:
          - score: 0.0-1.0 relevance score
          - insufficient_aspects: list of missing info (e.g., ["temperature", "plate thickness"])
          - suggestion: rewritten query for re-retrieval
        """
        ...
```

### 9.2 引用验证器

```python
class CitationVerifier:
    """Check if generated answer has sufficient citation coverage."""

    def verify(self, answer: str, citations: list[Citation]) -> VerificationResult:
        """
        Checks:
          1. Citation coverage: % of factual claims with citations
          2. Citation density: avg sentences per citation
          3. Hallucination risk: claims that match no chunk text
        """
        ...
```

---

## 10. M3/M4 集成

### 10.1 并行调用

```python
async def retrieve_context(query: str, mode: str) -> RetrievalContext:
    """Fetch context from M3 and optionally M4 in parallel."""
    if mode == "simple":
        m3_result = await m3_engine.retrieve(RetrievalRequest(query=query))
        return RetrievalContext(chunks=m3_result.chunks, graph=None, cross_refs=[])

    # pipeline / self_rag: parallel M3 + M4
    m3_task = m3_engine.retrieve(RetrievalRequest(query=query))
    m4_task = m4_engine.graph_search(topic=query, depth=depth_for_tier)
    m3_result, m4_result = await asyncio.gather(m3_task, m4_task)
    return RetrievalContext(chunks=m3_result.chunks, graph=m4_result, cross_refs=[])
```

---

## 11. 子任务列表（9 个）

| 编号 | 名称 | 类型 | 依赖 |
|------|------|------|------|
| 00090-01 | 骨架 + 配置 + 等级系统 | 原子 | 无 |
| 00090-02 | LLM 客户端 | 模块 | -01 |
| 00090-03 | Prompt 构建器 | 原子 | 无 |
| 00090-04 | 引用溯源 | 原子 | 无 |
| 00090-05 | 检索融合（M3+M4 并行调用） | 模块 | -03, -04 |
| 00090-06 | 三种管线（simple/pipeline/self_rag） | 模块 | -02, -05 |
| 00090-07 | 对话管理 + 上下文压缩 | 模块 | -01 |
| 00090-08 | 主引擎 + OpenAI 兼容 API | 集成 | -06, -07 |
| 00090-09 | 打包验证 | 集成 | -01~-08 |

```
依赖关系图：

00090-01 (config+tier)
    ├──→ 00090-03 (prompt builder)
    ├──→ 00090-04 (citation builder)
    ├──→ 00090-07 (conversation)
    └──→ 00090-02 (LLM client)
              │
              ▼
         00090-05 (retriever — M3+M4 integration)
              │
              ▼
         00090-06 (pipelines — simple/pipeline/self_rag)
              │
              ▼
         00090-08 (engine — OpenAI-compatible API)
              │
              ▼
         00090-09 (packaging + verification)
```

可以并行执行的任务：
- 00090-03 (prompt) + 00090-04 (citation) + 00090-07 (conversation) — 各自独立
- 00090-01 完成后：00090-02 可并行于上述三个

---

## 12. 技术选型汇总

| 组件 | 选型 | 原因 |
|------|------|------|
| LLM API | OpenAI 兼容 SDK | 统一接口覆盖 Ollama/DeepSeek/OpenAI/Claude |
| 流式生成 | SSE (Server-Sent Events) | 标准和 M6 前端已支持 |
| 对话存储 | M2 SQLite | 一致的技术栈 |
| 配额存储 | M2 SQLite (`m5_quotas` 表) | 轻量、一致 |
| Token 估算 | 字符数 ÷ 4 | 快速近似，和 M4 一致 |

---

## 13. 开发决策记录

| ID | 日期 | 决策 |
|----|------|------|
| M5-D01 | 2026-06-03 | 一套引擎三种模式（simple/pipeline/self_rag），不建三套系统 |
| M5-D02 | 2026-06-03 | Basic 每日 3 次 Premium（self_rag），Pro 每日 10 次 |
| M5-D03 | 2026-06-03 | 采用 OpenAI 兼容 API 格式，与 M6/M7 前端对齐 |
| M5-D04 | 2026-06-03 | 评估器和引用验证器在 Phase 2 用规则实现，Phase 3 升级为 LLM 评估 |
| M5-D05 | 2026-06-03 | 对话存储于 M2 SQLite，不使用 Redis（personal 模式无需） |
| M5-D06 | 2026-06-03 | 上下文窗口分配：chunks 4K + graph 1K + history 2K + reserve 0.7K |
| M5-D07 | 2026-06-03 | Self-RAG 循环最多 3 次迭代，防止无限循环 |

---

*设计规范结束。待审批后生成实现计划和任务分解。*
