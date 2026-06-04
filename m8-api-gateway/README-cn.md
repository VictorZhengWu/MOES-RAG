# M8 API 网关

海洋与海洋工程专家系统的 OpenAI 兼容 API 网关。提供安全、支持速率限制的 M5 问答引擎访问，使用标准 API 密钥认证。

## 概述

M8 是海洋与海洋工程专家系统的**外部 API 表面**。它负责：

- 暴露 **OpenAI 兼容 API** (`/v1/chat/completions`, `/v1/models`)
- 管理 **API 密钥认证**，使用 SHA-256 哈希存储
- 强制执行**分层速率限制**（Basic: 30/分钟, Pro: 120/分钟, Enterprise: 无限制）
- 将请求转发到 **M5 问答引擎**以获取 RAG 增强响应
- 支持多种**部署模式**（个人模式、企业模式、SaaS 模式）

## 架构

```
外部客户端 (OpenAI SDK)
    ↓ (Bearer: sk-m8-xxxxx)
M8 API 网关 (FastAPI, 端口 8000)
    ↓ (认证 → 速率限制 → 协议转换)
M5 问答引擎 (RAG 管道)
    ↓ (向量搜索 + LLM)
M2 向量存储 + M4 文档存储
```

### 关键设计决策

1. **独立 API 密钥系统**：M8 管理自己的密钥（格式：`sk-m8-{16hex}`），与 M5 用户认证分离。密钥以 SHA-256 哈希形式存储——原始密钥仅在生成时显示一次。

2. **内存速率限制**：使用滑动窗口算法，按 API 密钥执行。服务器重启时计数器重置（个人/企业模式可接受）。SaaS 部署应升级到基于 Redis 的持久化。

3. **OpenAI 兼容性**：所有端点遵循 OpenAI API 格式。任何 OpenAI SDK 客户端（Python、JavaScript 等）只需更改 `base_url` 和 `api_key` 即可连接。

4. **基于协议的通信**：M8 使用 `contracts/` 数据类与 M5 通信，确保模块独立性和版本安全。

## 安装

```bash
# 从项目根目录
cd m8-api-gateway

# 安装依赖
pip install -r requirements.txt

# 或以开发模式安装
pip install -e .
```

## 配置

创建 `deploy.yaml` 文件或使用环境变量：

```yaml
# deploy.yaml
host: "0.0.0.0"
port: 8000
db_path: "./data/m8_gateway.db"
deployment_mode: "personal"  # personal | enterprise | saas
```

### 部署模式

| 模式 | 描述 | 速率限制 |
|------|------|----------|
| `personal` | 单用户，本地开发 | Basic: 100/分钟, Pro: 无限制, Enterprise: 无限制 |
| `enterprise` | 内部团队，生产环境 | Basic: 30/分钟, Pro: 120/分钟, Enterprise: 无限制 |
| `saas` | 多租户公共服务 | Basic: 30/分钟, Pro: 120/分钟, Enterprise: 无限制 |

## 运行服务器

```bash
# 直接使用 uvicorn
uvicorn m8_gateway.core.app:create_app --factory --host 0.0.0.0 --port 8000

# 或使用配置文件
python -m m8_gateway.main --config deploy.yaml
```

服务器将在 `http://localhost:8000` 启动。

## API 端点

### OpenAI 兼容端点

#### `POST /v1/chat/completions`

支持 RAG 增强响应的聊天完成端点。

**请求：**
```json
{
  "model": "marine-rag",
  "messages": [
    {"role": "user", "content": "什么是 DNV Pt.4 Ch.3?"}
  ],
  "temperature": 0.7,
  "max_tokens": 4096,
  "domain_filter": "classification",
  "vessel_type_filter": "offshore"
}
```

**响应：**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "marine-rag",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "DNV Pt.4 Ch.3 指的是..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 50,
    "total_tokens": 70
  },
  "citations": [
    {
      "document_id": "doc-123",
      "chunk_id": "chunk-456",
      "text": "DNV Pt.4 Ch.3...",
      "metadata": {...}
    }
  ]
}
```

#### `GET /v1/models`

列出可用模型（OpenAI SDK 兼容性必需）。

**响应：**
```json
{
  "object": "list",
  "data": [
    {"id": "marine-rag", "object": "model"}
  ]
}
```

### 管理端点

#### `POST /admin/keys`

生成新的 API 密钥。

**请求：**
```json
{
  "user_id": "user-001",
  "tier": "pro"
}
```

**响应：**
```json
{
  "key": "sk-m8-a1b2c3d4e5f6g7h8",
  "prefix": "sk-m8-a1b2",
  "tier": "pro"
}
```

⚠️ **重要**：立即保存原始密钥。以后无法恢复。

#### `GET /admin/keys?user_id=user-001`

列出 API 密钥，可选择按用户过滤。

**响应：**
```json
[
  {
    "key_prefix": "sk-m8-a1b2",
    "user_id": "user-001",
    "tier": "pro",
    "created_at": 1234567890.0,
    "is_active": true,
    "last_used_at": 1234567900.0
  }
]
```

#### `DELETE /admin/keys/{key_prefix}`

通过前缀撤销 API 密钥。

**响应：**
```json
{
  "status": "revoked",
  "key_prefix": "sk-m8-a1b2"
}
```

#### `POST /admin/initialize-engine`

使用 LLM 后端配置初始化问答引擎。

**请求：**
```json
{
  "llm_backend": "deepseek",
  "api_key": "sk-...",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat"
}
```

**响应：**
```json
{
  "status": "ok",
  "message": "QA Engine initialized successfully"
}
```

#### `PUT /admin/initialize-engine`

使用新设置重新配置问答引擎。

### 监控端点

#### `GET /health`

健康检查端点。

**响应：**
```json
{
  "status": "ok",
  "deployment_mode": "personal",
  "qa_engine_ready": true
}
```

## 使用示例

### 使用 OpenAI Python SDK

```python
import openai

# 配置客户端使用 M8 而不是 OpenAI
client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-m8-a1b2c3d4e5f6g7h8"  # 你的 M8 API 密钥
)

# 使用标准 OpenAI SDK 方法
response = client.chat.completions.create(
    model="marine-rag",
    messages=[
        {"role": "user", "content": "解释 EH36 钢材预热要求"}
    ]
)

print(response.choices[0].message.content)
```

### 使用 curl

```bash
# 聊天完成
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-m8-a1b2c3d4e5f6g7h8" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "marine-rag",
    "messages": [{"role": "user", "content": "什么是 DNV Pt.4 Ch.3?"}]
  }'

# 列出模型
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer sk-m8-a1b2c3d4e5f6g7h8"

# 健康检查
curl http://localhost:8000/health
```

## 错误处理

M8 返回 OpenAI 兼容的错误响应：

### 401 未授权
```json
{
  "detail": "Invalid or revoked API key"
}
```

### 429 速率限制超出
```json
{
  "detail": "Rate limit exceeded. Please retry after the current window resets (60 seconds from first request)."
}
```

### 500 内部服务器错误
```json
{
  "detail": "QA Engine not initialized. Set app.state.qa_engine before accepting requests."
}
```

## 速率限制

速率限制使用滑动窗口算法（60 秒窗口）按 API 密钥强制执行。

| 层级 | 每分钟请求数 | 适用于 |
|------|-------------|--------|
| `basic` | 30 (个人模式: 100) | 个人开发者、测试 |
| `pro` | 120 | 生产应用程序、小团队 |
| `enterprise` | 无限制 | 大型部署、内部系统 |

### 重启行为

⚠️ **重要**：速率限制计数器存储在内存中，服务器重启时重置为零。这对于个人和企业部署是可以接受的。对于需要跨重启持久化速率限制的 SaaS 部署，请升级到基于 Redis 的实现。

## 安全考虑

### API 密钥存储

- API 密钥在存储前进行 **SHA-256 哈希**
- 原始密钥仅在生成时**显示一次**
- 数据库转储不会暴露可用的 API 密钥

### 管理端点安全

⚠️ **关键**：管理端点（`/admin/keys`, `/admin/initialize-engine`）目前**没有认证**。在生产环境中：

1. 将它们置于单独的管理认证中间件之后
2. 仅限制对本地主机或私有网络的访问
3. 使用防火墙规则或反向代理认证

### 传输安全

在生产环境中始终使用 HTTPS。`Authorization` 标头包含 API 密钥，必须在传输过程中加密。

## 开发

### 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio httpx

# 运行所有测试
pytest tests/

# 运行特定测试文件
pytest tests/test_openai_compat.py -v

# 运行覆盖率测试
pytest tests/ --cov=m8_gateway --cov-report=html
```

### 项目结构

```
m8-api-gateway/
├── m8_gateway/
│   ├── auth/
│   │   ├── key_manager.py      # API 密钥生命周期（生成、验证、撤销）
│   │   └── middleware.py        # FastAPI 依赖（认证、速率限制）
│   ├── core/
│   │   ├── app.py              # FastAPI 应用工厂
│   │   └── config.py           # 网关配置数据类
│   ├── models/
│   │   └── schemas.py          # Pydantic 请求/响应模型
│   ├── rate_limit/
│   │   └── limiter.py          # 滑动窗口速率限制器
│   └── routes/
│       ├── chat.py             # /v1/chat/completions 端点
│       ├── models.py           # /v1/models 端点
│       └── keys.py             # 管理端点（/admin/keys, /admin/initialize-engine）
├── tests/
│   ├── conftest.py             # 共享测试夹具
│   ├── test_chat.py           # 聊天端点测试
│   ├── test_key_manager.py    # 密钥管理器测试
│   ├── test_limiter.py        # 速率限制器测试
│   ├── test_openai_compat.py  # OpenAI SDK 兼容性测试
│   └── test_*.py              # 其他测试文件
├── contracts/                  # 共享接口定义（指向 ../contracts/ 的符号链接）
└── README.md                  # 本文件
```

### 代码质量标准

- **所有代码包含英文注释**，解释 WHAT 和 WHY
- **类型提示**贯穿始终
- **Pydantic 模型**验证所有 API 请求
- **协议数据类**确保模块独立性
- **全面的测试**覆盖认证、速率限制和 OpenAI 兼容性

## 故障排除

### "QA Engine not initialized"

问答引擎必须在接受聊天请求之前初始化：

```bash
# 通过管理 API 初始化
curl -X POST http://localhost:8000/admin/initialize-engine \
  -H "Content-Type: application/json" \
  -d '{
    "llm_backend": "deepseek",
    "api_key": "sk-...",
    "model": "deepseek-chat"
  }'
```

### 速率限制不工作

检查路由处理程序中是否存在 `check_rate_limit` 依赖：

```python
@router.post("/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
    rate_ok: bool = Depends(check_rate_limit),  # ← 必需
):
    ...
```

### OpenAI SDK 连接错误

验证：
1. `base_url` 指向 `http://localhost:8000/v1`（不是 `/v1/chat/completions`）
2. API 密钥格式正确（`sk-m8-...`）
3. 问答引擎已初始化（调用 `/health` 检查）

## 许可证

海洋与海洋工程专家系统项目的一部分。

## 相关模块

- **M5 问答引擎**：M8 将请求转发到的 RAG 管道引擎
- **M7 管理门户**：用于管理 API 密钥和问答引擎配置的 Web UI
- **Contracts**：共享接口定义（`contracts/qa_engine.py`）
