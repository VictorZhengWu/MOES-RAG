# Phase 3 — OAuth + Security Upgrade

> **改动范围**：M8 (auth.py) + M6 (SocialButtons) | **改动量**：中

---

## 1. 安全升级：SHA-256 → bcrypt

当前 M8 `auth.py` 使用 SHA-256 + random salt。升到 bcrypt：

```python
import bcrypt

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _verify_password(password: str, stored_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), stored_hash.encode())
```

- Phase 2 的 SHA-256 hash 继续有效（兼容模式：检查长度，短 hash 走 SHA-256 验证，验证通过后自动升级为 bcrypt）
- 新注册直接用 bcrypt

## 2. 忘记密码 / 重置密码

流程：用户输入 email → 生成 reset token（24h 有效期）→ 发邮件（含 reset link）→ 用户点链接设新密码。

```python
# M8 routes/auth.py
POST /auth/forgot-password  → 生成 token, 发邮件
POST /auth/reset-password   → 验证 token, 更新密码
```

M8 新增 `password_reset_tokens` 表：token_hash, user_id, expires_at。

SMTP 配置从环境变量：`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`。

## 3. OAuth 接入

Google / Microsoft / WeChat 三个 provider。统一流程：

```
M6 点 Google 登录
  → 重定向到 Google OAuth
    → 用户授权
      → 回调到 M8 /auth/oauth/callback?provider=google&code=xxx
        → M8 用 code 换 access_token → 获取用户信息
          → 查找或创建用户 → 生成 API key → 重定向到 M6 前端（带 token）
```

M8 新增路由：
- `GET /auth/oauth/login?provider=google` → 重定向到 provider
- `GET /auth/oauth/callback?provider=google&code=xxx` → code 换 token → 回 M6

M8 新增 `oauth_accounts` 表：provider, provider_user_id, user_id。

## 4. 改动清单

| 文件 | 改动 |
|------|------|
| `m8_gateway/routes/auth.py` | bcrypt + forgot/reset + OAuth login/callback |
| `m8_gateway/requirements.txt` | +bcrypt |
| `deploy/.env.example` | +SMTP + OAuth env vars |
| `m6-user-portal/src/components/auth/social-[buttons.py](http://buttons.py)` | 真实 OAuth URL 替换 console.log |

## 5. 环境变量（新增）

```
# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=marine-expert@example.com
SMTP_PASSWORD=app-password

# OAuth
OAUTH_GOOGLE_CLIENT_ID=
OAUTH_GOOGLE_CLIENT_SECRET=
OAUTH_MICROSOFT_CLIENT_ID=
OAUTH_MICROSOFT_CLIENT_SECRET=
OAUTH_WECHAT_APP_ID=
OAUTH_WECHAT_APP_SECRET=
OAUTH_REDIRECT_BASE=http://localhost:8000
```

---

*开始实现。*
