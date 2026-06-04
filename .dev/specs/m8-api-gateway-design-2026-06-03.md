# M8 API 网关 — 详细设计规范

> **日期**：2026-06-03 | **状态**：待审批
> **依赖**：contracts/ (00010), M5 (00090)
> **定位**：Layer 5 (Gateway)，外部 API 入口——认证→限流→路由→M5

---

## 1. 模块定位

M8 是系统的 API 网关。对外暴露 OpenAI 兼容 API，管理自己的 API Key（`sk-m8-xxx`），验证后转发到 M5 引擎。

**核心原则**：

- **独立进程** — FastAPI 独立服务（端口 8000），不嵌入 M5
- **自有 Key 系统** — `sk-m8-{16位hex}`，存储在 M8 SQLite，与 LLM 提供商的 key 无关
- **分级限流** — 绑定 M5 的 UserTier：Basic 30/min, Pro 120/min, Enterprise unlimited
- **OpenAI 兼容** — `/v1/chat/completions`, `/v1/models`，第三方应用无缝对接

### 1.1 Key 体系对比

```
M8 的 Key:                     LLM 提供商的 Key:
─────────────────────────────   ─────────────────────
sk-m8-a1b2c3d4e5f6g7h8        sk-deepseek-xxxx
由 M8 生成和管理               用户在 M7 后台配置
验证者: M8 Auth 中间件          使用者: M5 LLMClient
存储在 M8 SQLite               存储在 M5 QAConfig
控制: 谁能调我们的 API          控制: M5 用哪个 LLM
```

### 1.2 请求流程

```
外部应用
  │  curl -H "Authorization: Bearer sk-m8-a1b2c3d4e5f6g7h8"
  │       -d '{"model":"m5-qa","messages":[...]}'
  │       http://api.example.com:8000/v1/chat/completions
  ▼
M8 Gateway (port 8000)
  ├─ 1. Auth 中间件: 提取 Bearer token → 查 SQLite → 找到对应 user_id + tier
  ├─ 2. Rate Limiter: 检查该 key 的请求速率 → Basic 30/min, Pro 120/min
  ├─ 3. 路由: POST /v1/chat/completions → M5 QAEngine.chat()
  │         GET  /v1/models              → M5 QAEngine.list_models()
  ▼
M5 QAEngine (import 调用，同进程)
  └─ 返回 ChatResponse (含 citations)
  ▼
M8 返回 OpenAI 兼容 JSON 给外部应用
```

---

## 2. 模块目录结构

```
m8-api-gateway/
├── m8_gateway/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # GatewayConfig: port, db_path, rate limits
│   │   └── app.py              # FastAPI app 工厂 + 生命周期
│   │
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── key_manager.py      # API Key 生成/验证/撤销
│   │   └── middleware.py       # FastAPI 中间件（提取 Bearer token）
│   │
│   ├── rate_limit/
│   │   ├── __init__.py
│   │   └── limiter.py          # 滑动窗口限流（per key, per tier）
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py             # POST /v1/chat/completions → M5
│   │   ├── models.py           # GET  /v1/models → M5
│   │   └── keys.py             # POST /admin/keys (管理端点)
│   │
│   └── models/
│       ├── __init__.py
│       └── schemas.py          # Pydantic: APIKeyCreate, APIKeyInfo, ErrorResponse
│
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_key_manager.py
│   ├── test_limiter.py
│   ├── test_chat.py
│   ├── test_models.py
│   └── test_integration.py
│
├── pyproject.toml
└── requirements.txt
```

---

## 3. 核心设计

### 3.1 API Key 管理

```python
@dataclass
class APIKey:
    key_hash: str         # sha256(key) — 存哈希，不存明文
    key_prefix: str       # "sk-m8-a1b2" — 前 10 字符用于显示
    user_id: str          # 关联的用户
    tier: str             # "basic" | "pro" | "enterprise"
    created_at: float     # Unix timestamp
    is_active: bool       # 可撤销
    last_used_at: float | None

class KeyManager:
    """M8 API Key lifecycle management."""

    def __init__(self, db_path: str):
        self._db_path = db_path

    async def generate_key(self, user_id: str, tier: str) -> str:
        """Generate sk-m8-{16hex}, store hash, return raw key (shown ONCE)."""
        raw = f"sk-m8-{secrets.token_hex(8)}"
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        # Store (key_hash, user_id, tier) in SQLite
        return raw

    async def validate_key(self, raw_key: str) -> APIKey | None:
        """Look up key by hash. Return APIKey if active, None if invalid/revoked."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        # SELECT from api_keys WHERE key_hash=? AND is_active=1
        ...

    async def revoke_key(self, key_prefix: str) -> bool:
        """Revoke a key by its visible prefix."""
        ...

    async def list_keys(self, user_id: str | None = None) -> list[dict]:
        """List keys (masked: only prefix shown)."""
        ...
```

### 3.2 Rate Limiting（滑动窗口）

```python
RATE_LIMITS = {
    "basic":      30,   # 每分钟
    "pro":       120,
    "enterprise": -1,   # 无限制
}

class RateLimiter:
    """Per-key sliding window rate limiter (in-memory)."""

    def __init__(self):
        self._windows: dict[str, list[float]] = {}  # key_prefix → timestamps

    def check(self, key_prefix: str, tier: str) -> bool:
        """Return True if request is within rate limit."""
        limit = RATE_LIMITS.get(tier, 30)
        if limit == -1:  # enterprise: unlimited
            return True

        now = time.time()
        window_start = now - 60.0  # 1-minute sliding window

        # Get or create window for this key
        if key_prefix not in self._windows:
            self._windows[key_prefix] = []
        timestamps = self._windows[key_prefix]

        # Remove expired entries
        self._windows[key_prefix] = [t for t in timestamps if t > window_start]

        # Check limit
        if len(self._windows[key_prefix]) >= limit:
            return False

        # Record this request
        self._windows[key_prefix].append(now)
        return True
```

### 3.3 FastAPI 路由

```python
# routes/chat.py
@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatRequest,
    api_key: APIKey = Depends(get_api_key),  # Auth middleware injected
    rate_ok: bool = Depends(check_rate_limit),
):
    """OpenAI-compatible chat endpoint."""
    if not rate_ok:
        raise HTTPException(429, detail="Rate limit exceeded")

    engine = get_qa_engine()  # From app state
    response = await engine.chat(request)
    return response  # ChatResponse → JSON (via FastAPI serialization)

# routes/models.py
@router.get("/v1/models")
async def list_models(api_key: APIKey = Depends(get_api_key)):
    """OpenAI-compatible models list."""
    engine = get_qa_engine()
    models = await engine.list_models()
    return {"object": "list", "data": models}

# routes/keys.py (admin endpoints)
@router.post("/admin/keys")
async def create_key(body: APIKeyCreate):
    """Generate a new API key. Returns raw key (shown once)."""
    ...

@router.get("/admin/keys")
async def list_keys(user_id: str | None = None):
    """List API keys (masked)."""
    ...

@router.delete("/admin/keys/{key_prefix}")
async def revoke_key(key_prefix: str):
    """Revoke an API key."""
    ...
```

### 3.4 鉴权中间件

```python
# auth/middleware.py
async def get_api_key(
    request: Request,
    key_manager: KeyManager = Depends(get_key_manager),
) -> APIKey:
    """FastAPI dependency: extract Bearer token, validate, return APIKey."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, detail="Missing or invalid Authorization header")

    raw_key = auth_header[7:]  # Strip "Bearer "
    api_key = await key_manager.validate_key(raw_key)
    if api_key is None:
        raise HTTPException(401, detail="Invalid or revoked API key")

    # Update last_used_at
    await key_manager.touch_key(api_key.key_prefix)
    return api_key
```

---

## 4. 数据库

M8 自管理 SQLite `m8_gateway.db`：

```sql
CREATE TABLE api_keys (
    key_hash TEXT PRIMARY KEY,        -- sha256 of raw key
    key_prefix TEXT NOT NULL,         -- "sk-m8-a1b2c3d4"
    user_id TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'basic',
    created_at REAL NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    last_used_at REAL
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
```

---

## 5. 配置

```python
@dataclass
class GatewayConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "./data/m8_gateway.db"
    rate_limits: dict[str, int] = field(default_factory=lambda: {
        "basic": 30, "pro": 120, "enterprise": -1,
    })
```

---

## 6. 子任务列表（5 个）

| 编号 | 名称 | 类型 | 依赖 |
|------|------|------|------|
| 00100-01 | 骨架 + 配置 + FastAPI 工厂 | 原子 | 无 |
| 00100-02 | API Key 管理（生成/验证/撤销） | 模块 | -01 |
| 00100-03 | 限流器（滑动窗口 + 分级） | 原子 | -01 |
| 00100-04 | 路由（chat + models + keys）+ 中间件 | 模块 | -02, -03 |
| 00100-05 | 打包与最终验证 | 集成 | -01~-04 |

```
依赖关系：

00100-01 (config+app)
    ├──→ 00100-02 (key manager) ──┐
    └──→ 00100-03 (rate limiter) ─┤
                                   ├──→ 00100-04 (routes + middleware)
                                   │         │
                                   │         ▼
                                   └──→ 00100-05 (packaging)
```

00100-02 和 00100-03 可并行。

---

## 7. 技术选型

| 组件 | 选型 | 原因 |
|------|------|------|
| HTTP 框架 | FastAPI + uvicorn | 与 M1 web_server 一致，OpenAPI 自动文档 |
| 认证 | Bearer token + sha256 hash | 简单安全，不存明文 |
| 限流 | 内存滑动窗口 | Personal 模式无需 Redis |
| 存储 | SQLite (`m8_gateway.db`) | 与 M1/M5 一致 |
| Key 格式 | `sk-m8-{16hex}` | 可辨识的命名空间前缀 |

---

## 8. 开发决策

| ID | 日期 | 决策 |
|----|------|------|
| M8-D01 | 2026-06-03 | M8 独立 FastAPI 进程（端口 8000），不嵌入 M5 |
| M8-D02 | 2026-06-03 | API Key 格式 `sk-m8-{16hex}`，存 sha256 哈希不存明文 |
| M8-D03 | 2026-06-03 | 限流绑定 M5 UserTier：Basic 30/min, Pro 120/min, Enterprise unlimited |
| M8-D04 | 2026-06-03 | 限流用内存滑动窗口（Personal 模式），Phase 3 SAS 升级 Redis |
| M8-D05 | 2026-06-03 | M8 M5 同进程 import 调用，不跨 HTTP（避免序列化开销） |

---

*设计规范结束。待审批后生成任务分解。*
