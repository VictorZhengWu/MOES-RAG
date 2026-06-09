# M8 API Gateway — Module Memory

> **Last Updated**: 2026-06-09
> **Sessions**: 4
> **Status**: ✅ Redis 限流持久化完成

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | ✅ Complete (Redis rate limit added) |
| Active Tasks | — |
| First Dev Date | 2026-06-04 |
| Last Session Date | 2026-06-09 |
| Total Sessions | 4 |

---

## 2. Session History

### Session 3: 00100-04 + 00100-05 Routes, Middleware, Final Verification (2026-06-04)

- Implemented auth middleware (`get_api_key()` FastAPI dependency) extracting Bearer tokens
- Implemented 3 route modules: `chat.py` (POST /v1/chat/completions), `models.py` (GET /v1/models), `keys.py` (POST/GET/DELETE /admin/keys)
- OpenAI SDK compatibility verified via `test_openai_compat.py` (request header format + error response format)
- 6 new tests (chat auth, keys create/revoke, models list, OpenAI compat x2)
- Full regression: 17/17 passing
- Final packaging: pip install -e . verified, create_app import verified
- Fixed `__init__.py` to export `create_app`

### Session 2: 00100-03 Rate Limiter (2026-06-04)

- Implemented `RateLimiter` class -- in-memory sliding window
- Tiered limits: basic 30/min, pro 120/min, enterprise unlimited (-1)
- 3 tests, all passed. Full regression: 11/11.

### Session 1: 00100-01 + 00100-02 (2026-06-04)

- Created project skeleton: pyproject.toml, config.py, app factory
- Implemented SQLite-backed API key manager (generate, validate, revoke, list, touch)
- 8 tests, all passed.

---

## 3. Key Design Decisions (Module-Internal)

- **Factory pattern for FastAPI app**: `create_app(config)` returns a configured FastAPI instance. This enables test injection -- each TestClient gets its own KeyManager and RateLimiter via `app.state`. No global singletons.
- **Rate limiter dual-backend strategy**: `InMemoryRateLimiter` for Personal/Enterprise (zero deps), `RedisRateLimiter` for SaaS (persistent, multi-instance shared state). Backend auto-selected via `deployment_mode` (SaaS→redis, others→memory), explicitly overridable. Swap via DI — callers never know which backend is active.
- **Sliding window cleanup is lazy**: Expired timestamps removed on each check() call, not via background thread. Keeps the implementation simple with no threading concerns.
- **Lazy QA Engine initialization**: `app.state.qa_engine = None` on startup. The QA Engine requires LLM backend config from M7 admin before it can be initialized. Routes check for None and return 500 with a clear message if the engine isn't ready.
- **Key storage**: SHA256 hashed keys in SQLite (`api_keys` table). Only the prefix (`sk-m8-` + first 8 hex chars) is visible in list operations. Full key is shown once at generation time.
- **OpenAI SDK compatibility**: The `/v1/chat/completions` and `/v1/models` endpoints are structured to match the OpenAI API format. `test_openai_compat.py` verifies request/response format compatibility.
- **Admin key management**: Separate `/admin/keys` endpoints for CRUD operations on API keys. These are internal endpoints (no auth yet -- Phase 1).
- **`contracts` dependency path**: Tests use `sys.path.insert` in conftest.py to find the contracts package. In production deployment, `contracts` should be installed as a proper pip package.

---

## 4. Known Pitfalls & Gotchas

- **FastAPI `on_event` deprecation**: Current code uses `@app.on_event("startup")` / `@app.on_event("shutdown")`. Should migrate to `lifespan` context manager. Non-blocking (DeprecationWarning only).

---

## 5. Interface Contract Deviations

- Extended chat response format includes `citations` field beyond standard OpenAI chat completion response. OpenAI SDK clients that access `.citations` directly will need to handle this as a non-standard extension.

---

## 6. Performance Notes

- Rate limiter: O(1) check with per-key deque cleanup. Memory scales with number of active keys.
- Key validation: Single SQLite query by sha256 hash. Sub-millisecond latency.
- Gateway overhead (excluding QA Engine): < 2ms for auth + rate limit check.

---

### Session 4: 00100-10~13 Redis Rate Limit Persistence + Test Connection Endpoints (2026-06-09)

- Implemented `BaseRateLimiter` abstract class + `InMemoryRateLimiter` refactoring + `RedisRateLimiter` (ZSET sliding window)
- DI-friendly factory `create_rate_limiter()` auto-selects backend based on `deployment_mode`
- `RedisConfig` (8 fields: host/port/db/password/max_connections/backend/strict_mode/window_seconds)
- `GET/PATCH /admin/config/rate-limit` — hot-swap limiter with `threading.Lock`, health check, atomic replacement
- 3 Storage Test Connection endpoints: `POST /admin/config/storage/test-{postgresql,elasticsearch,minio}`
- Docker Compose: Redis 7 Alpine service (maxmemory 256mb + allkeys-lru + AOF + RDB)
- deploy/saas/deploy.yaml: `rate_limit.redis` config section
- 12 new redis limiter tests (fakeredis + mock), 58 total passed

---

## 7. Open Issues

- Admin endpoints lack auth (acceptable for Personal mode)
- QA Engine lazy init -- gateway starts but chat requires engine config
- FastAPI `on_event` → `lifespan` migration needed (non-blocking)

---

## 8. Module File Map

```
m8-api-gateway/
  m8_gateway/
    __init__.py          -- exports create_app
    core/
      config.py          -- GatewayConfig + RedisConfig dataclass
      app.py             -- create_app() FastAPI factory
    auth/
      key_manager.py     -- KeyManager (generate/validate/revoke/list/touch)
      middleware.py      -- get_api_key() + check_rate_limit DI
    rate_limit/
      base.py            -- BaseRateLimiter abstract (check/get_usage/close/health_check)
      limiter.py         -- InMemoryRateLimiter (sliding window)
      redis_limiter.py   -- RedisRateLimiter (ZSET sliding window)
      redis_client.py    -- create_redis_client() factory
      __init__.py        -- create_rate_limiter() factory
    routes/
      chat.py            -- POST /v1/chat/completions
      keys.py            -- POST/GET/DELETE /admin/keys
      models.py          -- GET /v1/models
      admin.py           -- GET/PATCH /admin/config/rate-limit + all config endpoints
    models/
      schemas.py         -- Pydantic models
  tests/
    conftest.py          -- test_app fixture
    test_config.py       -- 8 tests
    test_key_manager.py  -- 5 tests
    test_limiter.py      -- 9 tests
    test_redis_client.py -- 8 tests
    test_redis_limiter.py -- 12 tests
    test_chat.py         -- 1 test
    test_keys.py         -- 2 tests
    test_models.py       -- 1 test
    test_openai_compat.py -- 2 tests
    test_conversations.py -- 4 tests
    test_documents.py     -- 6 tests
  pyproject.toml
  requirements.txt
```

### Tasks Completed

| Task | Description | Tests | Status |
|------|-------------|-------|--------|
| 00100-01 | Project skeleton + config + FastAPI factory | 3 | ✅ |
| 00100-02 | API Key manager (generate/validate/revoke/list/touch) | 5 | ✅ |
| 00100-03 | Sliding window rate limiter with tiered limits | 3 | ✅ |
| 00100-04 | Routes + auth middleware + OpenAI SDK compat | 6 | ✅ |
| 00100-05 | Final packaging verification | — | ✅ |
| 00100-10 | Redis 基础层 (base.py + redis_client.py + RedisConfig) | 13 | ✅ |
| 00100-11 | RedisRateLimiter + InMemory 重构 + Factory | 9 | ✅ |
| 00100-12 | App 集成 + Config 端点 + Docker Compose | — | ✅ |
| 00100-13 | Redis 限流测试 + 全量回归 | 12 | ✅ |

**Total**: 58 tests, all passing. 8 new files created. 4 new commits.
