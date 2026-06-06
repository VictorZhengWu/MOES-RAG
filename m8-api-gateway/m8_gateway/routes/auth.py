"""
M8 API Gateway — Authentication Routes.

WHAT: User registration and login endpoints. On success, an M8 API key
      (sk-m8-xxx) is generated and returned for use as a Bearer token.

WHY: M6 frontend's login/register UI currently uses localStorage-based
     fake login. These endpoints provide real authentication — a valid
     API key is returned that can be used for all subsequent API calls
     (chat, conversations, document upload, etc.).

Security: Passwords are hashed with SHA-256 (salt+password). This is
          appropriate for Phase 2 personal mode. Phase 3 SaaS should
          upgrade to bcrypt/argon2 with proper salt generation.
"""

import hashlib
import secrets
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from m8_gateway.auth.key_manager import KeyManager

router = APIRouter(prefix="/auth", tags=["authentication"])

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """Request body for user registration."""
    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=6, max_length=200)
    tier: str = Field(default="basic", pattern="^(basic|pro|enterprise)$")


class LoginRequest(BaseModel):
    """Request body for user login."""
    email: str
    password: str


class AuthResponse(BaseModel):
    """Response returned on successful register/login."""
    user_id: str
    username: str
    email: str
    tier: str
    api_key: str        # Full key — store this for Bearer auth
    key_prefix: str      # "sk-m8-xxxx" for display


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_password(password: str, salt: str = "") -> tuple[str, str]:
    """
    Hash a password with SHA-256 and a random salt.
    Returns (salt, hash_hex).
    Phase 2: SHA-256 is sufficient for personal mode single-user.
    Phase 3: upgrade to bcrypt or argon2id for SaaS multi-tenant.
    """
    if not salt:
        salt = secrets.token_hex(16)
    combined = salt + password
    hash_hex = hashlib.sha256(combined.encode()).hexdigest()
    return salt, hash_hex


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest):
    """
    POST /auth/register — Create a new user account.

    WHAT:
      1. Checks username/email uniqueness.
      2. Hashes password with random salt.
      3. Creates user in M8's SQLite users table.
      4. Generates an M8 API key with the chosen tier.
      5. Returns the API key — the client should store it immediately.

    WHY: M6 frontend Sign Up form needs a real backend. Previously
         registration was client-side only with no server state.
    """
    import aiosqlite
    from m8_gateway.core.config import GatewayConfig

    # Get KeyManager from app state (accessible via dependency injection,
    # but for auth routes that don't have auth middleware, we create one)
    db_path = "./data/m8_gateway.db"
    km = KeyManager(db_path)

    user_id = f"user-{secrets.token_hex(8)}"
    salt, pw_hash = _hash_password(body.password)

    async with aiosqlite.connect(db_path) as conn:
        # Ensure tables exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'basic',
                created_at REAL NOT NULL
            )
        """)
        await conn.commit()

        # Check uniqueness
        cursor = await conn.execute(
            "SELECT 1 FROM users WHERE username = ? OR email = ?",
            (body.username, body.email),
        )
        if await cursor.fetchone():
            raise HTTPException(409, "Username or email already exists")

        # Insert user
        await conn.execute(
            "INSERT INTO users (user_id, username, email, password_hash, password_salt, tier, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, body.username, body.email, pw_hash, salt, body.tier, time.time()),
        )
        await conn.commit()

    # Generate API key for the new user
    raw_key = await km.generate_key(user_id, body.tier)

    return AuthResponse(
        user_id=user_id,
        username=body.username,
        email=body.email,
        tier=body.tier,
        api_key=raw_key,
        key_prefix=raw_key[:10],
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    """
    POST /auth/login — Authenticate and return an API key.

    WHAT:
      1. Looks up user by email.
      2. Validates password against stored hash.
      3. Generates a new API key for this session.
      4. Returns the key for Bearer auth on subsequent requests.

    WHY: M6 frontend Sign In form needs real credential validation.
         On success the client stores the API key and uses it for all
         API calls via the Authorization header.
    """
    import aiosqlite

    db_path = "./data/m8_gateway.db"
    km = KeyManager(db_path)

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'basic',
                created_at REAL NOT NULL
            )
        """)
        await conn.commit()

        cursor = await conn.execute(
            "SELECT user_id, username, email, password_hash, password_salt, tier "
            "FROM users WHERE email = ?",
            (body.email,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(401, "Invalid email or password")

        user_id, username, email, stored_hash, salt, tier = row

        # Verify password
        _, computed_hash = _hash_password(body.password, salt)
        if computed_hash != stored_hash:
            raise HTTPException(401, "Invalid email or password")

    # Generate a new API key for this login session
    raw_key = await km.generate_key(user_id, tier)

    return AuthResponse(
        user_id=user_id,
        username=username,
        email=email,
        tier=tier,
        api_key=raw_key,
        key_prefix=raw_key[:10],
    )
