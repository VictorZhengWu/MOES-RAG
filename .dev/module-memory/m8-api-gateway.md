# M8 — API Gateway 模块记忆

> **Purpose**: Record all development sessions, decisions, gotchas, and lessons learned for M8. Read this file before starting ANY new M8 development session.

---

## 1. Module Status

| Field | Value |
|-------|-------|
| Status | 🔄 In Progress |
| Active Tasks | 00100-03 (rate limiter) |
| First Dev Date | 2026-06-04 |
| Last Session Date | 2026-06-04 |
| Total Sessions | 2 |

---

## 2. Session History

### Session 2: 00100-03 Rate Limiter (2026-06-04)
- Implemented `RateLimiter` class — in-memory sliding window
- Tiered limits: basic 30/min, pro 120/min, enterprise unlimited (-1)
- 3 tests, all passed. Full regression: 11/11.

### Session 1: 00100-01 + 00100-02 (2026-06-04)
- Created project skeleton: pyproject.toml, config.py, app factory
- Implemented SQLite-backed API key manager (generate, validate, revoke)
- 8 tests, all passed.

---

## 3. Key Design Decisions (Module-Internal)

- **Rate limiter is in-memory, not persistent**: Restart resets all counters. Acceptable for Personal mode. SaaS deployment will need Redis-backed implementation (swap via DI — no code changes needed in callers).
- **Sliding window cleanup is lazy**: Expired timestamps removed on each check() call, not via background thread. Keeps the implementation simple with no threading concerns.

---

## 4. Known Pitfalls & Gotchas

> *No pitfalls recorded yet.*

---

## 5. Interface Contract Deviations

> *Record any API behaviors that differ from the OpenAI API spec (e.g., extended response fields for citations).*

---

## 6. Performance Notes

> *Gateway latency overhead, rate limiting throughput.*

---

## 7. Open Issues

> *Unresolved problems.*
