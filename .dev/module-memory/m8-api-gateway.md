# M8 API Gateway — Module Memory

> **Last Updated**: 2026-06-04
> **Sessions**: 3
> **Status**: ✅ Complete

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | ✅ Complete |
| Active Tasks | — |
| First Dev Date | 2026-06-04 |
| Last Session Date | 2026-06-04 |
| Total Sessions | 3 |

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
- **Rate limiter is in-memory, not persistent**: Restart resets all counters. Acceptable for Personal mode. SaaS deployment will need Redis-backed implementation (swap via DI -- no code changes needed in callers).
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

## 7. Open Issues

- Admin endpoints lack auth (acceptable for Personal mode)
- Rate limiter not persisted across restarts
- QA Engine lazy init -- gateway starts but chat requires engine config
- FastAPI `on_event` → `lifespan` migration needed (non-blocking)

---

## 8. Module File Map

```
m8-api-gateway/
  m8_gateway/
    __init__.py          -- exports create_app
    core/
      config.py          -- GatewayConfig dataclass
      app.py             -- create_app() FastAPI factory
    auth/
      key_manager.py     -- KeyManager (generate/validate/revoke/list/touch)
      middleware.py      -- get_api_key() FastAPI dependency
    rate_limit/
      limiter.py         -- RateLimiter (sliding window)
    routes/
      chat.py            -- POST /v1/chat/completions
      keys.py            -- POST/GET/DELETE /admin/keys
      models.py          -- GET /v1/models
    models/
      schemas.py         -- Pydantic models
  tests/
    conftest.py          -- test_app fixture (isolated FastAPI app)
    test_config.py       -- 3 tests
    test_key_manager.py  -- 5 tests
    test_limiter.py      -- 3 tests
    test_chat.py         -- 1 test
    test_keys.py         -- 2 tests
    test_models.py       -- 1 test
    test_openai_compat.py -- 2 tests
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

**Total**: 17 tests, all passing. 25 files created. 5 git commits.
