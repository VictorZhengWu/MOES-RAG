"""
M8 API Gateway — Authentication Routes.

WHAT: User registration, login (email+password + OAuth), password reset.
      On success, an M8 API key (sk-m8-xxx) is returned for Bearer auth.

WHY: M6 frontend needs real authentication — email/password (Phase 2),
     OAuth (Phase 3), and password reset (Phase 3). All return the same
     API key format so the M6 auth store works identically regardless
     of login method.

Security: bcrypt for password hashing (upgraded from SHA-256 in Phase 3).
          OAuth uses standard authorization code flow. Reset tokens are
          single-use, 24h expiry, SHA-256 hashed in DB.
          Brute-force protection: 5 failed attempts = 15min lockout.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import time
import aiosqlite
import httpx

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

from m8_gateway.auth.key_manager import KeyManager

router = APIRouter(prefix="/auth", tags=["authentication"])

# Brute-force protection
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 900  # 15 minutes
_login_attempts: dict[str, list[float]] = {}  # key → timestamps of failed attempts

# OAuth CSRF protection: SQLite-backed for persistence across restarts.
# 10-minute expiry. Auto-cleaned on each oauth_login call.
OAUTH_STATE_TTL = 600  # 10 minutes

# Reset token brute force protection
MAX_RESET_ATTEMPTS = 5
_reset_attempts: dict[str, int] = {}  # token_hash → failed attempts

# Forgot password rate limit (per email, 5-minute cooldown)
_forgot_password_throttle: dict[str, float] = {}

# Email regex — RFC 5322 simplified
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Banned usernames (prevent impersonation, profanity, system names)
_BANNED_USERNAMES: set[str] = {
    "admin", "administrator", "root", "system", "support", "api",
    "moderator", "mod", "staff", "help", "info", "noreply", "no-reply",
    "abuse", "security", "postmaster", "webmaster", "hostmaster",
}

# ---------------------------------------------------------------------------
# Configuration (from environment)
# ---------------------------------------------------------------------------

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
OAUTH_REDIRECT_BASE = os.environ.get("OAUTH_REDIRECT_BASE", "http://localhost:8000")
OAUTH_GOOGLE_CLIENT_ID = os.environ.get("OAUTH_GOOGLE_CLIENT_ID", "")
OAUTH_GOOGLE_CLIENT_SECRET = os.environ.get("OAUTH_GOOGLE_CLIENT_SECRET", "")
OAUTH_MICROSOFT_CLIENT_ID = os.environ.get("OAUTH_MICROSOFT_CLIENT_ID", "")
OAUTH_MICROSOFT_CLIENT_SECRET = os.environ.get("OAUTH_MICROSOFT_CLIENT_SECRET", "")
OAUTH_WECHAT_APP_ID = os.environ.get("OAUTH_WECHAT_APP_ID", "")
OAUTH_WECHAT_APP_SECRET = os.environ.get("OAUTH_WECHAT_APP_SECRET", "")
OAUTH_FACEBOOK_APP_ID = os.environ.get("OAUTH_FACEBOOK_APP_ID", "")
OAUTH_FACEBOOK_APP_SECRET = os.environ.get("OAUTH_FACEBOOK_APP_SECRET", "")
OAUTH_X_CLIENT_ID = os.environ.get("OAUTH_X_CLIENT_ID", "")
OAUTH_X_CLIENT_SECRET = os.environ.get("OAUTH_X_CLIENT_SECRET", "")
OAUTH_APPLE_CLIENT_ID = os.environ.get("OAUTH_APPLE_CLIENT_ID", "")
OAUTH_APPLE_TEAM_ID = os.environ.get("OAUTH_APPLE_TEAM_ID", "")
OAUTH_APPLE_KEY_ID = os.environ.get("OAUTH_APPLE_KEY_ID", "")
OAUTH_APPLE_PRIVATE_KEY = os.environ.get("OAUTH_APPLE_PRIVATE_KEY", "")
DB_PATH = os.environ.get("M8_DB_PATH", "./data/m8_gateway.db")
M6_BASE_URL = os.environ.get("M6_BASE_URL", "http://localhost:3000")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    tier: str = Field(default="basic", pattern="^(basic|pro|enterprise)$")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format with regex."""
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email format")
        return v.lower().strip()

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username: no banned names, alphanumeric + underscore only."""
        if v.lower() in _BANNED_USERNAMES:
            raise ValueError(f"Username '{v}' is reserved")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username can only contain letters, numbers, hyphens, and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Enforce minimum password strength: length + character variety."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase for consistent lookup."""
        return v.lower().strip()


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=200)


class AuthResponse(BaseModel):
    user_id: str
    username: str
    email: str
    tier: str
    api_key: str
    key_prefix: str


# ---------------------------------------------------------------------------
# Password hashing (bcrypt with SHA-256 backward compatibility)
# ---------------------------------------------------------------------------


def _hash_password(password: str) -> str:
    """Hash password with bcrypt. Returns bcrypt hash string."""
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash (bcrypt or legacy SHA-256)."""
    import bcrypt

    # bcrypt hashes start with $2b$ or $2a$
    if stored_hash.startswith("$2"):
        return bcrypt.checkpw(password.encode(), stored_hash.encode())

    # Legacy SHA-256 (Phase 2 accounts): verify, then auto-upgrade
    # Stored format: "salt:hash" (48 chars salt + ":" + 64 chars hex)
    if ":" in stored_hash:
        salt, pw_hash = stored_hash.split(":", 1)
        computed = hashlib.sha256((salt + password).encode()).hexdigest()
        return computed == pw_hash

    return False


def _record_failed_attempt(email: str) -> None:
    """Record a failed login attempt for brute-force tracking."""
    _clean_expired_attempts(email)
    if email not in _login_attempts:
        _login_attempts[email] = []
    _login_attempts[email].append(time.time())


def _clean_expired_attempts(email: str) -> None:
    """Remove expired failed attempt records."""
    if email not in _login_attempts:
        return
    cutoff = time.time() - LOGIN_LOCKOUT_SECONDS
    _login_attempts[email] = [t for t in _login_attempts[email] if t > cutoff]
    if not _login_attempts[email]:
        del _login_attempts[email]


def _maybe_upgrade_password(user_id: str, password: str, stored_hash: str) -> None:
    """If the stored hash is legacy SHA-256, upgrade it to bcrypt in-place."""
    if stored_hash.startswith("$2"):
        return  # Already bcrypt

    import asyncio
    async def _upgrade():
        new_hash = _hash_password(password)
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                "UPDATE users SET password_hash = ?, password_salt = '' WHERE user_id = ?",
                (new_hash, user_id),
            )
            await conn.commit()
    asyncio.create_task(_upgrade())  # Fire-and-forget upgrade


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _ensure_users_table(conn):
    """Create users table if not exists."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL DEFAULT '',
            tier TEXT NOT NULL DEFAULT 'basic',
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        )
    """)
    await conn.commit()


async def _ensure_oauth_table(conn):
    """Create OAuth accounts + states tables if not exists."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS oauth_accounts (
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            email TEXT,
            name TEXT,
            avatar_url TEXT,
            created_at REAL NOT NULL,
            PRIMARY KEY (provider, provider_user_id)
        )
    """)
    await conn.commit()


async def _ensure_reset_tokens_table(conn):
    """Create password reset tokens table if not exists."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at REAL NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        )
    """)
    await conn.commit()


async def _generate_api_key(user_id: str, tier: str) -> tuple[str, str]:
    """Generate an M8 API key and return (raw_key, key_prefix)."""
    km = KeyManager(DB_PATH)
    raw = await km.generate_key(user_id, tier)
    return raw, raw[:10]


# ---------------------------------------------------------------------------
# Admin login (API key + admin role check)
# ---------------------------------------------------------------------------


class AdminLoginRequest(BaseModel):
    api_key: str = Field(..., min_length=19)


@router.post("/admin-login")
async def admin_login(body: AdminLoginRequest):
    """POST /auth/admin-login — Validate API key + check admin role."""
    km = KeyManager(DB_PATH)
    api_key_obj = await km.validate_key(body.api_key)
    if api_key_obj is None:
        raise HTTPException(401, "Invalid API key")

    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_users_table(conn)
        # Add is_admin column if not exists (migration)
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            await conn.commit()
        except aiosqlite.OperationalError:
            pass

        cursor = await conn.execute(
            "SELECT username, email, tier, is_admin FROM users WHERE user_id = ?",
            (api_key_obj.user_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(401, "User not found")

        username, email, tier, is_admin = row
        if not is_admin and tier not in ("admin", "editor"):
            raise HTTPException(403, "Admin access required. Your tier: " + tier)

        km.touch_key(api_key_obj.key_prefix)

    return {
        "user_id": api_key_obj.user_id,
        "username": username,
        "email": email,
        "tier": tier,
        "api_key": body.api_key,
        "key_prefix": api_key_obj.key_prefix,
    }


# ---------------------------------------------------------------------------
# Email/Password routes
# ---------------------------------------------------------------------------


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest):
    """POST /auth/register — Create a new user account with bcrypt password."""
    user_id = f"user-{secrets.token_hex(8)}"
    pw_hash = _hash_password(body.password)

    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_users_table(conn)

        # Atomic insert with duplicate check — prevents TOCTOU race condition
        # where two concurrent registers with same email both pass the SELECT
        # check. SQLite UNIQUE constraint is the ultimate arbiter.
        try:
            await conn.execute(
                "INSERT INTO users (user_id, username, email, password_hash, tier, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, body.username, body.email, pw_hash, body.tier, time.time()),
            )
            await conn.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(409, "Username or email already exists")

    raw_key, prefix = await _generate_api_key(user_id, body.tier)

    return AuthResponse(
        user_id=user_id, username=body.username, email=body.email,
        tier=body.tier, api_key=raw_key, key_prefix=prefix,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    """POST /auth/login — Authenticate with email+password. Returns API key.

    Brute-force protection: 5 failed attempts = 15-minute lockout per email.
    Cleared on successful login.
    """
    # Check brute-force lockout
    _clean_expired_attempts(body.email)
    recent = _login_attempts.get(body.email, [])
    if len(recent) >= MAX_LOGIN_ATTEMPTS:
        wait_sec = int(LOGIN_LOCKOUT_SECONDS - (time.time() - min(recent)))
        raise HTTPException(
            429,
            f"Too many login attempts. Please try again in {wait_sec // 60} minutes.",
        )

    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_users_table(conn)
        cursor = await conn.execute(
            "SELECT user_id, username, email, password_hash, tier "
            "FROM users WHERE email = ?",
            (body.email,),
        )
        row = await cursor.fetchone()
        if row is None:
            _record_failed_attempt(body.email)
            raise HTTPException(401, "Invalid email or password")

        user_id, username, email, stored_hash, tier = row

        if not _verify_password(body.password, stored_hash):
            _record_failed_attempt(body.email)
            raise HTTPException(401, "Invalid email or password")

        # Clear failed attempts on successful login
        _login_attempts.pop(body.email, None)

        # Auto-upgrade legacy SHA-256 accounts to bcrypt
        _maybe_upgrade_password(user_id, body.password, stored_hash)

    raw_key, prefix = await _generate_api_key(user_id, tier)

    return AuthResponse(
        user_id=user_id, username=username, email=email,
        tier=tier, api_key=raw_key, key_prefix=prefix,
    )


# ---------------------------------------------------------------------------
# Password Reset routes
# ---------------------------------------------------------------------------


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    """
    POST /auth/forgot-password — Send password reset email.

    WHAT: Generates a single-use reset token (24h expiry), stores its
          SHA-256 hash, and sends an email with a reset link to the user.

    WHY: Always returns 200 {"ok": True} even if the email doesn't exist —
         prevents email enumeration attacks. The actual email send only
         happens if a matching user is found.
    """
    # Rate limit: 5-minute cooldown per email
    now_fp = time.time()
    last_fp = _forgot_password_throttle.get(body.email, 0)
    if now_fp - last_fp < 300:
        raise HTTPException(429, "Too many reset requests. Please wait 5 minutes.")
    _forgot_password_throttle[body.email] = now_fp
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_users_table(conn)
        cursor = await conn.execute(
            "SELECT user_id, username, email FROM users WHERE email = ?",
            (body.email,),
        )
        row = await cursor.fetchone()
        if row is None:
            return {"ok": True}  # Don't reveal email doesn't exist

        user_id, username, email = row

        # Generate reset token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = time.time() + 86400  # 24 hours

        await _ensure_reset_tokens_table(conn)
        # Invalidate old tokens for this user
        await conn.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE user_id = ?",
            (user_id,),
        )
        await conn.execute(
            "INSERT INTO password_reset_tokens (token_hash, user_id, expires_at, created_at) "
            "VALUES (?, ?, ?, ?)",
            (token_hash, user_id, expires_at, time.time()),
        )
        await conn.commit()

    # Send email (non-blocking — fire-and-forget)
    if SMTP_HOST:
        _send_reset_email.background(email, username, raw_token)
    else:
        import logging
        logging.getLogger("m8_gateway").warning(
            "SMTP not configured. Reset token for %s: %s (first 8 chars shown for dev)",
            email, raw_token[:8],
        )

    return {"ok": True}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    """
    POST /auth/reset-password — Reset password with a valid token.

    WHAT: Validates the reset token (hash match + not expired + not used),
          updates the user's password to bcrypt, and marks the token as used.

    WHY: Token is single-use and time-limited to prevent replay attacks.
    """
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()

    # Rate limit: max 5 attempts per token
    attempts = _reset_attempts.get(token_hash, 0)
    if attempts >= MAX_RESET_ATTEMPTS:
        raise HTTPException(429, "Too many attempts for this token")
    _reset_attempts[token_hash] = attempts + 1

    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_reset_tokens_table(conn)
        cursor = await conn.execute(
            "SELECT user_id, expires_at, used FROM password_reset_tokens "
            "WHERE token_hash = ?",
            (token_hash,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(400, "Invalid or expired reset token")

        user_id, expires_at, used = row
        if used:
            raise HTTPException(400, "This reset link has already been used")
        if time.time() > expires_at:
            raise HTTPException(400, "This reset link has expired (24h limit)")

        # Update password
        pw_hash = _hash_password(body.new_password)
        await _ensure_users_table(conn)
        await conn.execute(
            "UPDATE users SET password_hash = ?, password_salt = '' WHERE user_id = ?",
            (pw_hash, user_id),
        )
        # Mark token used
        await conn.execute(
            "UPDATE password_reset_tokens SET used = 1 WHERE token_hash = ?",
            (token_hash,),
        )
        await conn.commit()

    return {"ok": True}


# ---------------------------------------------------------------------------
# OAuth routes
# ---------------------------------------------------------------------------

OAUTH_PROVIDERS = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "client_id": OAUTH_GOOGLE_CLIENT_ID,
        "client_secret": OAUTH_GOOGLE_CLIENT_SECRET,
        "scope": "openid email profile",
    },
    "microsoft": {
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "client_id": OAUTH_MICROSOFT_CLIENT_ID,
        "client_secret": OAUTH_MICROSOFT_CLIENT_SECRET,
        "scope": "openid email profile",
    },
    "wechat": {
        "auth_url": "https://open.weixin.qq.com/connect/qrconnect",
        "token_url": "https://api.weixin.qq.com/sns/oauth2/access_token",
        "userinfo_url": "https://api.weixin.qq.com/sns/userinfo",
        "client_id": OAUTH_WECHAT_APP_ID,
        "client_secret": OAUTH_WECHAT_APP_SECRET,
        "scope": "snsapi_login",
    },
    "facebook": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "userinfo_url": "https://graph.facebook.com/me?fields=id,name,email,picture",
        "client_id": OAUTH_FACEBOOK_APP_ID,
        "client_secret": OAUTH_FACEBOOK_APP_SECRET,
        "scope": "email public_profile",
    },
    "x": {
        "auth_url": "https://x.com/i/oauth2/authorize",
        "token_url": "https://api.x.com/2/oauth2/token",
        "userinfo_url": "https://api.x.com/2/users/me",
        "client_id": OAUTH_X_CLIENT_ID,
        "client_secret": OAUTH_X_CLIENT_SECRET,
        "scope": "users.read tweet.read",
    },
    "apple": {
        "auth_url": "https://appleid.apple.com/auth/authorize",
        "token_url": "https://appleid.apple.com/auth/token",
        "userinfo_url": "",  # Apple returns user info in the id_token
        "client_id": OAUTH_APPLE_CLIENT_ID,
        "client_secret": OAUTH_APPLE_PRIVATE_KEY,  # Apple uses signed JWT, not static secret
        "scope": "name email",
        "team_id": OAUTH_APPLE_TEAM_ID,
        "key_id": OAUTH_APPLE_KEY_ID,
    },
}


@router.get("/oauth/login")
async def oauth_login(provider: str = Query(...)):
    """
    GET /auth/oauth/login?provider=google — Redirect to OAuth provider.

    WHAT: Builds the OAuth authorization URL and redirects the user's
          browser to the provider's consent screen.

    WHY: M6 SocialButtons component links to this endpoint instead of
         fake localStorage login.
    """
    cfg = OAUTH_PROVIDERS.get(provider)
    if not cfg or not cfg.get("client_id", ""):
        raise HTTPException(400, f"OAuth provider '{provider}' is not configured")

    redirect_uri = f"{OAUTH_REDIRECT_BASE}/auth/oauth/callback?provider={provider}"
    state = secrets.token_urlsafe(16)

    # Store state in SQLite for CSRF validation (persists across restarts)
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_oauth_table(conn)
        # Clean expired states
        await conn.execute("DELETE FROM oauth_states WHERE expires_at < ?", (now,))
        await conn.execute(
            "INSERT INTO oauth_states (state, provider, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (state, provider, now, now + OAUTH_STATE_TTL),
        )
        await conn.commit()

    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": cfg["scope"],
        "state": state,
    }
    if provider == "wechat":
        params["appid"] = params.pop("client_id")
        del params["response_type"]

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"{cfg['auth_url']}?{query_string}"

    return RedirectResponse(url=auth_url)


@router.get("/oauth/callback")
async def oauth_callback(
    provider: str = Query(...),
    code: str = Query(...),
    state: str = Query(default=""),
):
    """
    GET /auth/oauth/callback?provider=google&code=xxx — Handle OAuth callback.

    WHAT: Exchanges the authorization code for an access token, fetches
          the user's profile, creates or links a local user account, and
          redirects to the M6 frontend with the API key.

    WHY: Standard OAuth 2.0 authorization code flow. The final redirect
         to M6 includes the API key as a query parameter so the frontend
         can call useAuthStore.login() and store it.
    """
    cfg = OAUTH_PROVIDERS.get(provider)
    if not cfg or not cfg["client_id"]:
        return RedirectResponse(
            url=f"{M6_BASE_URL}/login?error=provider_not_configured"
        )

    # Validate CSRF state from SQLite (persists across restarts)
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_oauth_table(conn)
        cursor = await conn.execute(
            "SELECT provider, expires_at FROM oauth_states WHERE state = ?",
            (state,),
        )
        row = await cursor.fetchone()
        if row is None:
            return RedirectResponse(url=f"{M6_BASE_URL}/login?error=invalid_state")
        stored_provider, expires_at = row
        if stored_provider != provider or time.time() > expires_at:
            await conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
            await conn.commit()
            return RedirectResponse(url=f"{M6_BASE_URL}/login?error=state_mismatch")
        # One-time use: delete after validation
        await conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        await conn.commit()

    redirect_uri = f"{OAUTH_REDIRECT_BASE}/auth/oauth/callback?provider={provider}"

    # Step 1: Exchange code for access token
    token_data = {
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if provider == "wechat":
        token_data["appid"] = token_data.pop("client_id")
        token_data["secret"] = token_data.pop("client_secret")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(cfg["token_url"], data=token_data)
            if token_resp.status_code != 200:
                return RedirectResponse(
                    url=f"{M6_BASE_URL}/login?error=oauth_token_failed"
                )
            token_json = token_resp.json()
            access_token = token_json.get("access_token", "")
    except Exception:
        return RedirectResponse(
            url=f"{M6_BASE_URL}/login?error=oauth_network_error"
        )

    if not access_token:
        return RedirectResponse(
            url=f"{M6_BASE_URL}/login?error=oauth_no_token"
        )

    # Step 2: Fetch user info
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "wechat":
                # WeChat: access_token + openid from token response
                openid = token_json.get("openid", "")
                user_resp = await client.get(
                    cfg["userinfo_url"],
                    params={"access_token": access_token, "openid": openid},
                )
            else:
                user_resp = await client.get(
                    cfg["userinfo_url"],
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            if user_resp.status_code != 200:
                return RedirectResponse(
                    url=f"{M6_BASE_URL}/login?error=oauth_userinfo_failed"
                )
            user_json = user_resp.json()
    except Exception:
        return RedirectResponse(
            url=f"{M6_BASE_URL}/login?error=oauth_network_error"
        )

    # Step 3: Find or create user
    provider_user_id = str(
        user_json.get("id", user_json.get("sub", user_json.get("openid", ""))
    )

    # Extract email (provider-specific field names)
    email = (
        user_json.get("email")
        or user_json.get("userPrincipalName")
        or user_json.get("mail")
        or ""
    )

    # Extract display name (provider-specific field names)
    name = (
        user_json.get("name")
        or user_json.get("displayName")
        or user_json.get("nickname")
        or ""
    )

    # Extract avatar URL (provider-specific field names)
    avatar_url = ""
    if provider == "facebook":
        pic = user_json.get("picture", {})
        if isinstance(pic, dict):
            data = pic.get("data", {})
            avatar_url = data.get("url", "")
    elif provider == "x":
        data_wrapper = user_json.get("data", {})
        avatar_url = data_wrapper.get("profile_image_url", "")
        if not name:
            name = data_wrapper.get("name", data_wrapper.get("username", ""))
    else:
        avatar_url = (
            user_json.get("picture")
            or user_json.get("avatar_url")
            or user_json.get("headimgurl")
            or ""
        )

    if not provider_user_id:
        return RedirectResponse(
            url=f"{M6_BASE_URL}/login?error=oauth_no_user_id"
        )

    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_oauth_table(conn)
        await _ensure_users_table(conn)

        # Check existing OAuth link
        cursor = await conn.execute(
            "SELECT user_id FROM oauth_accounts WHERE provider = ? AND provider_user_id = ?",
            (provider, provider_user_id),
        )
        row = await cursor.fetchone()

        if row:
            user_id = row[0]
        else:
            # Check if email exists (link accounts)
            if email:
                cursor = await conn.execute(
                    "SELECT user_id, tier FROM users WHERE email = ?", (email,)
                )
                row = await cursor.fetchone()
                if row:
                    user_id = row[0]
                else:
                    # Create new user
                    user_id = f"user-{secrets.token_hex(8)}"
                    username = name or f"{provider}_user_{provider_user_id[:8]}"
                    await conn.execute(
                        "INSERT INTO users (user_id, username, email, password_hash, tier, created_at) "
                        "VALUES (?, ?, ?, '', 'basic', ?)",
                        (user_id, username, email or "", time.time()),
                    )
            else:
                user_id = f"user-{secrets.token_hex(8)}"
                username = name or f"{provider}_user_{provider_user_id[:8]}"
                await conn.execute(
                    "INSERT INTO users (user_id, username, email, password_hash, tier, created_at) "
                    "VALUES (?, ?, ?, '', 'basic', ?)",
                    (user_id, username, "", time.time()),
                )

            # Link OAuth account with avatar
            await conn.execute(
                "INSERT INTO oauth_accounts (provider, provider_user_id, user_id, email, name, avatar_url, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (provider, provider_user_id, user_id, email, name, avatar_url, time.time()),
            )
            await conn.commit()

    # Step 4: Generate API key and redirect to M6
    raw_key, prefix = await _generate_api_key(user_id, "basic")

    return RedirectResponse(
        url=(
            f"{M6_BASE_URL}/auth/callback"
            f"?token={raw_key}"
            f"&user_id={user_id}"
            f"&username={name or 'user'}"
            f"&email={email or ''}"
            f"&tier=basic"
        )
    )


# ---------------------------------------------------------------------------
# Email helper (fire-and-forget)
# ---------------------------------------------------------------------------


def _send_reset_email(email: str, username: str, raw_token: str) -> None:
    """Send password reset email via SMTP. Runs synchronously in a thread."""
    import smtplib
    from email.mime.text import MIMEText

    reset_link = f"{M6_BASE_URL}/reset-password?token={raw_token}"
    body = (
        f"Hi {username},\n\n"
        f"You requested a password reset for your Marine & Offshore Expert System account.\n\n"
        f"Click here to reset your password (valid for 24 hours):\n{reset_link}\n\n"
        f"If you did not request this, please ignore this email.\n"
    )

    try:
        msg = MIMEText(body)
        msg["Subject"] = "Password Reset — Marine & Offshore Expert System"
        msg["From"] = SMTP_USER
        msg["To"] = email

        import ssl
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:
        import logging
        logging.getLogger("m8_gateway").warning(
            "Failed to send reset email to %s", email
        )


# Thread-pool wrapper for fire-and-forget email
_send_reset_email.background = lambda email, username, token: (
    __import__("threading").Thread(
        target=_send_reset_email, args=(email, username, token), daemon=True
    ).start()
)
