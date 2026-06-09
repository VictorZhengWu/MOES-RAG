# M8 Redis 限流持久化 — 详细设计规范

> **日期**：2026-06-09 | **状态**：待审批
> **依赖**：M8 API Gateway (00100)
> **定位**：M8 `rate_limit/` 子模块扩展——从纯内存限流升级为 Redis 持久化 + 内存双后端

---

## 1. 背景与目标

### 1.1 现状

当前 M8 限流器 (`rate_limit/limiter.py`) 是纯内存滑动窗口实现：
- 60 秒窗口，按 API key 计数
- 三级限制：Basic 30/min, Pro 120/min, Enterprise unlimited
- 重启丢失所有计数器
- 单实例部署可接受

### 1.2 目标

增加 Redis 后端，实现：
- **跨重启持久化** — 计数器不随服务重启清零
- **多实例共享** — 多个 M8 实例共用同一套限流计数（SaaS 水平扩展基础）
- **零调用方改动** — 路由和中间件通过 `BaseRateLimiter` 协议调用，完全透明
- **按部署模式自动选择** — Personal/Enterprise 默认内存，SaaS 默认 Redis

### 1.3 设计决策 D035 回顾

> D035: Rate limiting uses an in-memory sliding window (60s) with per-tier limits
> that vary by deployment mode. In-memory suffices for Phase 2; Phase 3 SaaS
> upgrades to Redis for persistence across restarts.

本次实现即兑现 D035 的 Phase 3 升级承诺。

---

## 2. 架构设计

### 2.1 双后端策略模式

```
                    ┌─────────────────────┐
                    │   BaseRateLimiter   │  ← NEW: 抽象基类
                    │   (Protocol/ABC)    │
                    ├─────────────────────┤
                    │ + check(prefix,tier)│
                    │ + get_usage(prefix) │
                    └─────────┬───────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
   ┌──────────┴──────────┐      ┌────────────┴──────────┐
   │ InMemoryRateLimiter │      │   RedisRateLimiter    │
   │ (refactored from    │      │   (NEW)               │
   │  current RateLimiter)│     │                       │
   ├─────────────────────┤      ├───────────────────────┤
   │ self._windows: dict │      │ self._redis: Redis    │  ← DI 注入
   │ self._limits: dict  │      │ self._strict_mode     │
   └─────────────────────┘      │ self._memory_fallback │
                                └───────────────────────┘
```

### 2.2 部署模式 → 后端映射

| 部署模式 | 默认后端 | Redis 降级策略 |
|---------|---------|--------------|
| Personal | `memory` | N/A（不连接 Redis） |
| Enterprise | `memory` | 可选启用 Redis + `strict_mode=false` |
| SaaS | `redis` | `strict_mode=true`（Redis 不可用则拒绝请求） |

### 2.3 降级策略

| 场景 | strict_mode=true (SaaS) | strict_mode=false (Enterprise) |
|------|------------------------|-------------------------------|
| Redis 连接初始化失败 | 抛 RuntimeError，启动即失败 | 降级到 InMemoryRateLimiter，WARNING 日志 |
| Redis 运行时断开 | return False (拒绝), CRITICAL 日志 | 降级到内存计数, ERROR 日志 |
| redis 包未安装 | 抛 RuntimeError | 降级到内存, WARNING 日志 |

---

## 3. 组件设计

### 3.1 文件结构

```
m8-api-gateway/m8_gateway/rate_limit/
├── __init__.py          # 导出 BaseRateLimiter + InMemoryRateLimiter + create_rate_limiter()
├── base.py              # NEW: BaseRateLimiter 抽象基类
├── limiter.py           # REFACTOR: RateLimiter → InMemoryRateLimiter(BaseRateLimiter)
├── redis_limiter.py     # NEW: RedisRateLimiter(BaseRateLimiter)
└── redis_client.py      # NEW: Redis 连接工厂（纯函数，无全局变量）
```

### 3.2 BaseRateLimiter (base.py)

```python
class BaseRateLimiter(ABC):
    """Abstract base for rate limiter implementations.

    WHAT: Defines the interface that both InMemoryRateLimiter and
          RedisRateLimiter must implement. All callers (routes,
          middleware) depend on this interface, never on concrete
          implementations.

    WHY: Enables swapping between memory and Redis backends without
         changing a single line in route handlers or middleware.
    """

    @abstractmethod
    def check(self, key_prefix: str, tier: str) -> bool:
        """Return True if request is within rate limit."""
        ...

    @abstractmethod
    def get_usage(self, key_prefix: str) -> int:
        """Return current request count in the sliding window."""
        ...
```

### 3.3 InMemoryRateLimiter (limiter.py — 重构)

```
现有 RateLimiter 类重命名为 InMemoryRateLimiter，继承 BaseRateLimiter。
行为完全不变。新增 window_seconds 配置参数（默认 60）。
```

**改动范围**：
- 类名 `RateLimiter` → `InMemoryRateLimiter`
- 继承 `BaseRateLimiter`
- `__init__` 新增 `window_seconds: int = 60` 参数
- 硬编码 `60.0` 替换为 `float(self._window_seconds)`

### 3.4 RedisRateLimiter (redis_limiter.py)

**Redis 数据结构**：Sorted Set (ZSET)

```
Key:   rate_limit:{key_prefix}
       例: rate_limit:sk-m8-a1b2c3d4

操作序列 (check 方法):
1. ZREMRANGEBYSCORE key 0 {now - window_seconds}   # 清理过期条目
2. ZCARD key                                         # 获取当前窗口内计数
3. 若 count >= limit → return False                  # 超限拒绝
4. ZADD key {now} "{now}-{uuid_hex[:8]}"             # 记录本次请求
5. EXPIRE key {window_seconds * 2}                   # 自动清理闲置 key
6. return True
```

**Member 随机后缀原因**：Redis Sorted Set 的 member 是唯一的。同一纳秒内两个请求
打相同时间戳会导致 `ZADD` 覆盖而非追加。加 8 位随机 hex 避免碰撞。

**EXPIRE 2×窗口原因**：闲置 key 不再有新请求后，等待 2 个窗口周期自动回收，不留垃圾。

**降级逻辑**：

```python
def check(self, key_prefix: str, tier: str) -> bool:
    try:
        return self._check_redis(key_prefix, tier)
    except Exception as e:
        logger.error(f"Redis check failed: {e}")
        if self._strict_mode:
            return False  # SaaS: reject, enforce cost control
        return self._check_memory(key_prefix, tier)  # Enterprise: degrade
```

### 3.5 Redis 客户端工厂 (redis_client.py)

```python
def create_redis_client(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    password: str = "",
    max_connections: int = 50,
    socket_timeout: int = 5,
) -> Redis | None:
    """Create a Redis client with connection pooling. Returns None on failure.

    WHAT: Pure factory function that creates and verifies a Redis connection.
          No global state — caller owns the returned Redis instance.

    WHY: DI-friendly: tests can inject fakeredis, production injects real Redis.
         Each RedisRateLimiter instance owns its Redis client — clear lifecycle.
    """
```

- 无模块级全局变量
- 调用方负责 `close()` 生命周期
- 连接池参数均可配置

---

## 4. 配置模型

### 4.1 RedisConfig (config.py 扩展)

```python
@dataclass
class RedisConfig:
    """Redis connection and rate limiting parameters.
    All fields configurable via M7 Admin UI → Storage → Rate Limit tab.
    """
    # Connection
    host: str = "localhost"       # M7: text input
    port: int = 6379             # M7: number input, range 1-65535
    db: int = 0                  # M7: number input, range 0-15
    password: str = ""           # M7: password input (masked)
    max_connections: int = 50    # M7: number input, range 5-200

    # Rate limiting behavior
    backend: str = "memory"      # M7: dropdown ["memory", "redis"]
    strict_mode: bool = False    # M7: toggle switch
    window_seconds: int = 60     # M7: number input, range 10-300
```

### 4.2 GatewayConfig 集成

```python
@dataclass
class GatewayConfig:
    # ... existing fields ...
    rate_limit_backend: str = "memory"           # "memory" | "redis"
    rate_limit_redis: RedisConfig = field(default_factory=RedisConfig)
```

### 4.3 配置来源

1. **首次启动**：`deploy.yaml` 或环境变量（`REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`）
2. **运行时修改**：M7 Admin UI → Storage → Rate Limit 标签页 → 热生效
3. **热生效机制**：配置变更时创建新的 `RateLimiter` 实例替换 `app.state.limiter`

### 4.4 deploy.yaml 配置段

```yaml
# deploy/saas/deploy.yaml
deployment_mode: saas
rate_limit:
  backend: redis
  redis:
    host: redis           # Docker Compose 服务名
    port: 6379
    db: 0
    password: ${REDIS_PASSWORD}
    max_connections: 50
    strict_mode: true
    window_seconds: 60
```

### 4.5 Docker Compose 扩展

```yaml
# deploy/docker-compose.yml (追加)
services:
  redis:
    image: redis:7-alpine
    container_name: marine-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped

  m8:
    environment:
      - REDIS_HOST=redis
      - REDIS_PASSWORD=${REDIS_PASSWORD:-}
    depends_on:
      - redis

volumes:
  redis_data:
```

---

## 5. Factory 与 App 集成

### 5.1 Factory (rate_limit/__init__.py)

```python
def create_rate_limiter(config: GatewayConfig) -> BaseRateLimiter:
    """Select and construct the appropriate rate limiter based on config.

    WHAT: Reads config.rate_limit_backend and returns the matching
          BaseRateLimiter implementation. If backend="redis", attempts
          to create a Redis client and pass it to RedisRateLimiter.

    WHY: Factory isolates backend selection to a single point. Callers
         (app.py, tests) don't know which backend is active.
    """
    limits = config.rate_limits
    
    if config.rate_limit_backend == "redis":
        redis_client = create_redis_client(
            host=config.rate_limit_redis.host,
            port=config.rate_limit_redis.port,
            db=config.rate_limit_redis.db,
            password=config.rate_limit_redis.password or None,
            max_connections=config.rate_limit_redis.max_connections,
        )
        if redis_client:
            return RedisRateLimiter(
                redis_client=redis_client,
                rate_limits=limits,
                strict_mode=config.rate_limit_redis.strict_mode,
                window_seconds=config.rate_limit_redis.window_seconds,
            )
        if config.rate_limit_redis.strict_mode:
            raise RuntimeError("Redis required but unavailable (strict_mode=true)")
    
    return InMemoryRateLimiter(
        rate_limits=limits,
        window_seconds=config.rate_limit_redis.window_seconds,
    )
```

### 5.2 App 集成 (app.py 变更)

单行替换，其余零改动：

```python
# 旧:
from m8_gateway.rate_limit.limiter import RateLimiter
app.state.limiter = RateLimiter(cfg.rate_limits)

# 新:
from m8_gateway.rate_limit import create_rate_limiter
app.state.limiter = create_rate_limiter(cfg)
```

路由和中间件通过 `request.app.state.limiter.check()` 调用，接口不变，完全透明。

---

## 6. 错误处理

| 场景 | strict_mode=true (SaaS) | strict_mode=false (Enterprise) |
|------|------------------------|-------------------------------|
| Redis 连接初始化失败 | 抛 RuntimeError，启动即失败 | 降级到 InMemoryRateLimiter，WARNING |
| Redis 运行时断开 | return False (拒绝), CRITICAL | 降级到内存计数, ERROR |
| redis 包未安装 | 抛 RuntimeError | 降级到内存, WARNING |

所有日志使用 `logger.getLogger("m8_gateway.rate_limit.redis")`。

---

## 7. 依赖

```python
# requirements.txt 新增
redis>=5.0.0          # Redis client with async support
fakeredis>=2.20.0     # In-memory Redis mock for testing (dev dependency)
```

---

## 8. M7 界面预留

M7 Admin Portal → Settings → Storage 标签页下新增 Rate Limiter 子标签：

```
Rate Limiter
├── Backend:        [memory ▼] [redis ▼]
├── Redis Host:     [localhost        ]
├── Redis Port:     [6379             ]
├── Redis Password: [••••••••         ]
├── DB Number:      [0                ]
├── Max Connections:[50               ]
├── Strict Mode:    [○ off  ● on      ]
├── Window Seconds: [60               ]
└── [Test Connection] [Save]
```

**本次会话范围**：后端实现 + 配置端点。M7 UI 作为后续 Task 单独处理。

---

## 9. 测试策略

| 测试文件 | 内容 | 后端 |
|---------|------|------|
| `test_limiter.py` | 现有 3 测试，更新 import 路径 | InMemory |
| `test_redis_limiter.py` | 新增 5 测试 | fakeredis (内存模拟) |

**测试用例 (test_redis_limiter.py)**：

1. `test_basic_rate_limit` — 前 N 个通过，第 N+1 拒绝
2. `test_unlimited_tier` — Enterprise 无限流，200 请求全部通过
3. `test_sliding_window_expiry` — 手动推进 fakeredis 时间，验证窗口滑动
4. `test_strict_mode_rejects` — strict_mode=True，模拟 Redis 异常 → return False
5. `test_non_strict_fallback` — strict_mode=False，模拟 Redis 异常 → 内存放行

---

## 10. 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| NEW | `m8_gateway/rate_limit/base.py` | BaseRateLimiter 抽象基类 |
| NEW | `m8_gateway/rate_limit/redis_limiter.py` | RedisRateLimiter 实现 |
| NEW | `m8_gateway/rate_limit/redis_client.py` | Redis 连接工厂函数 |
| NEW | `tests/test_redis_limiter.py` | Redis 限流测试 (5 tests) |
| MODIFY | `m8_gateway/rate_limit/__init__.py` | 导出更新 + create_rate_limiter 工厂 |
| MODIFY | `m8_gateway/rate_limit/limiter.py` | RateLimiter → InMemoryRateLimiter + window_seconds |
| MODIFY | `m8_gateway/core/config.py` | 新增 RedisConfig + GatewayConfig 扩展 |
| MODIFY | `m8_gateway/core/app.py` | 工厂对接 (单行替换) |
| MODIFY | `requirements.txt` | 新增 redis, fakeredis 依赖 |
| MODIFY | `tests/test_limiter.py` | 更新 import 路径 |
| MODIFY | `deploy/docker-compose.yml` | 新增 redis 服务 |
| MODIFY | `deploy/saas/deploy.yaml` | 新增 rate_limit.redis 配置段 |
