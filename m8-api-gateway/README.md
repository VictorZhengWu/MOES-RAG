# M8 API Gateway

OpenAI-compatible API gateway for the Marine & Offshore Expert System. Provides secure, rate-limited access to the M5 QA Engine with standard API key authentication.

## Overview

M8 is the **external API surface** for the Marine & Offshore Expert System. It:

- Exposes an **OpenAI-compatible API** (`/v1/chat/completions`, `/v1/models`)
- Manages **API key authentication** with SHA-256 hashed storage
- Enforces **tier-based rate limiting** (Basic: 30/min, Pro: 120/min, Enterprise: unlimited)
- Forwards requests to the **M5 QA Engine** for RAG-augmented responses
- Supports multiple **deployment modes** (Personal, Enterprise, SaaS)

## Architecture

```
External Client (OpenAI SDK)
    ↓ (Bearer: sk-m8-xxxxx)
M8 API Gateway (FastAPI, Port 8000)
    ↓ (auth → rate limit → contract conversion)
M5 QA Engine (RAG pipeline)
    ↓ (vector search + LLM)
M2 Vector Store + M4 Document Store
```

### Key Design Decisions

1. **Independent API Key System**: M8 manages its own keys (format: `sk-m8-{16hex}`) separate from M5 user authentication. Keys are stored as SHA-256 hashes — the raw key is shown only once at generation time.

2. **In-Memory Rate Limiting**: Uses a sliding window algorithm per API key. Counters reset on server restart (acceptable for Personal/Enterprise modes). SaaS deployments should upgrade to Redis-based persistence.

3. **OpenAI Compatibility**: All endpoints follow OpenAI API formats. Any OpenAI SDK client (Python, JavaScript, etc.) can connect by changing `base_url` and `api_key`.

4. **Contract-Based Communication**: M8 uses `contracts/` dataclasses to communicate with M5, ensuring module independence and version safety.

## Installation

```bash
# From the project root
cd m8-api-gateway

# Install dependencies
pip install -r requirements.txt

# Or in development mode
pip install -e .
```

## Configuration

Create a `deploy.yaml` file or use environment variables:

```yaml
# deploy.yaml
host: "0.0.0.0"
port: 8000
db_path: "./data/m8_gateway.db"
deployment_mode: "personal"  # personal | enterprise | saas
```

### Deployment Modes

| Mode | Description | Rate Limits |
|------|-------------|-------------|
| `personal` | Single user, local development | Basic: 100/min, Pro: unlimited, Enterprise: unlimited |
| `enterprise` | Internal team, production | Basic: 30/min, Pro: 120/min, Enterprise: unlimited |
| `saas` | Multi-tenant public service | Basic: 30/min, Pro: 120/min, Enterprise: unlimited |

## Running the Server

```bash
# Using uvicorn directly
uvicorn m8_gateway.core.app:create_app --factory --host 0.0.0.0 --port 8000

# Or using the configuration file
python -m m8_gateway.main --config deploy.yaml
```

The server will start on `http://localhost:8000`.

## API Endpoints

### OpenAI-Compatible Endpoints

#### `POST /v1/chat/completions`

Chat completion endpoint with RAG-augmented responses.

**Request:**
```json
{
  "model": "marine-rag",
  "messages": [
    {"role": "user", "content": "What is DNV Pt.4 Ch.3?"}
  ],
  "temperature": 0.7,
  "max_tokens": 4096,
  "domain_filter": "classification",
  "vessel_type_filter": "offshore"
}
```

**Response:**
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
      "content": "DNV Pt.4 Ch.3 refers to..."
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

Lists available models (required for OpenAI SDK compatibility).

**Response:**
```json
{
  "object": "list",
  "data": [
    {"id": "marine-rag", "object": "model"}
  ]
}
```

### Admin Endpoints

#### `POST /admin/keys`

Generate a new API key.

**Request:**
```json
{
  "user_id": "user-001",
  "tier": "pro"
}
```

**Response:**
```json
{
  "key": "sk-m8-a1b2c3d4e5f6g7h8",
  "prefix": "sk-m8-a1b2",
  "tier": "pro"
}
```

⚠️ **Important**: Save the raw key immediately. It cannot be recovered later.

#### `GET /admin/keys?user_id=user-001`

List API keys, optionally filtered by user.

**Response:**
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

Revoke an API key by its prefix.

**Response:**
```json
{
  "status": "revoked",
  "key_prefix": "sk-m8-a1b2"
}
```

#### `POST /admin/initialize-engine`

Initialize the QA Engine with LLM backend configuration.

**Request:**
```json
{
  "llm_backend": "deepseek",
  "api_key": "sk-...",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat"
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "QA Engine initialized successfully"
}
```

#### `PUT /admin/initialize-engine`

Reconfigure the QA Engine with new settings.

### Monitoring Endpoints

#### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "deployment_mode": "personal",
  "qa_engine_ready": true
}
```

## Usage Examples

### Using the OpenAI Python SDK

```python
import openai

# Configure the client to use M8 instead of OpenAI
client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-m8-a1b2c3d4e5f6g7h8"  # Your M8 API key
)

# Use standard OpenAI SDK methods
response = client.chat.completions.create(
    model="marine-rag",
    messages=[
        {"role": "user", "content": "Explain EH36 steel preheating requirements"}
    ]
)

print(response.choices[0].message.content)
```

### Using curl

```bash
# Chat completion
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-m8-a1b2c3d4e5f6g7h8" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "marine-rag",
    "messages": [{"role": "user", "content": "What is DNV Pt.4 Ch.3?"}]
  }'

# List models
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer sk-m8-a1b2c3d4e5f6g7h8"

# Health check
curl http://localhost:8000/health
```

## Error Handling

M8 returns OpenAI-compatible error responses:

### 401 Unauthorized
```json
{
  "detail": "Invalid or revoked API key"
}
```

### 429 Rate Limit Exceeded
```json
{
  "detail": "Rate limit exceeded. Please retry after the current window resets (60 seconds from first request)."
}
```

### 500 Internal Server Error
```json
{
  "detail": "QA Engine not initialized. Set app.state.qa_engine before accepting requests."
}
```

## Rate Limiting

Rate limits are enforced per API key using a sliding window algorithm (60-second window).

| Tier | Requests per Minute | Suitable For |
|------|-------------------|--------------|
| `basic` | 30 (Personal: 100) | Individual developers, testing |
| `pro` | 120 | Production applications, small teams |
| `enterprise` | Unlimited | Large deployments, internal systems |

### Restart Behavior

⚠️ **Important**: Rate limit counters are stored in-memory and reset to zero on server restart. This is acceptable for personal and enterprise deployments. For SaaS deployments requiring persistent rate limiting across restarts, upgrade to a Redis-based implementation.

## Security Considerations

### API Key Storage

- API keys are **SHA-256 hashed** before storage
- The raw key is shown **only once** at generation time
- Database dumps do not expose usable API keys

### Admin Endpoint Security

⚠️ **Critical**: The admin endpoints (`/admin/keys`, `/admin/initialize-engine`) currently have **no authentication**. In production:

1. Place them behind a separate admin auth middleware
2. Restrict access to localhost or private networks only
3. Use firewall rules or reverse proxy authentication

### Transport Security

Always use HTTPS in production. The `Authorization` header contains the API key and must be encrypted in transit.

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_openai_compat.py -v

# Run with coverage
pytest tests/ --cov=m8_gateway --cov-report=html
```

### Project Structure

```
m8-api-gateway/
├── m8_gateway/
│   ├── auth/
│   │   ├── key_manager.py      # API key lifecycle (generate, validate, revoke)
│   │   └── middleware.py        # FastAPI dependencies (auth, rate limit)
│   ├── core/
│   │   ├── app.py              # FastAPI application factory
│   │   └── config.py           # Gateway configuration dataclass
│   ├── models/
│   │   └── schemas.py          # Pydantic request/response models
│   ├── rate_limit/
│   │   └── limiter.py          # Sliding window rate limiter
│   └── routes/
│       ├── chat.py             # /v1/chat/completions endpoint
│       ├── models.py           # /v1/models endpoint
│       └── keys.py             # Admin endpoints (/admin/keys, /admin/initialize-engine)
├── tests/
│   ├── conftest.py             # Shared test fixtures
│   ├── test_chat.py           # Chat endpoint tests
│   ├── test_key_manager.py    # Key manager tests
│   ├── test_limiter.py        # Rate limiter tests
│   ├── test_openai_compat.py  # OpenAI SDK compatibility tests
│   └── test_*.py              # Other test files
├── contracts/                  # Shared interface definitions (symlink to ../contracts/)
└── README.md                  # This file
```

### Code Quality Standards

- **All code includes English comments** explaining WHAT and WHY
- **Type hints** are used throughout
- **Pydantic models** validate all API requests
- **Contract dataclasses** ensure module independence
- **Comprehensive tests** cover auth, rate limiting, and OpenAI compatibility

## Troubleshooting

### "QA Engine not initialized"

The QA Engine must be initialized before accepting chat requests:

```bash
# Initialize via admin API
curl -X POST http://localhost:8000/admin/initialize-engine \
  -H "Content-Type: application/json" \
  -d '{
    "llm_backend": "deepseek",
    "api_key": "sk-...",
    "model": "deepseek-chat"
  }'
```

### Rate Limit Not Working

Check that the `check_rate_limit` dependency is in the route handler:

```python
@router.post("/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
    rate_ok: bool = Depends(check_rate_limit),  # ← Required
):
    ...
```

### OpenAI SDK Connection Errors

Verify:
1. The `base_url` points to `http://localhost:8000/v1` (not `/v1/chat/completions`)
2. The API key format is correct (`sk-m8-...`)
3. The QA Engine is initialized (call `/health` to check)

## License

Part of the Marine & Offshore Expert System project.

## Related Modules

- **M5 QA Engine**: RAG pipeline engine that M8 forwards requests to
- **M7 Admin Portal**: Web UI for managing API keys and QA Engine configuration
- **Contracts**: Shared interface definitions (`contracts/qa_engine.py`)
