"""M8 API Key lifecycle management.

WHAT: Full lifecycle for API keys used to authenticate external requests
      to the M8 API Gateway. Supports generate, validate, revoke, list,
      and touch (update last_used_at).

      Key format: sk-m8-{16 hex chars} (e.g. sk-m8-a1b2c3d4e5f6g7h8).
      Only the SHA-256 hash is stored in SQLite. The raw key is returned
      once at generation time and never stored or shown again.

WHY: Separating key generation from M5 user management ensures M8 controls
     external API access independently. Hash-only storage prevents key
     leaks from database dumps or backups. The prefix-based lookup for
     revoke/list avoids exposing the full key material.

Design decisions:
- SHA-256 (not bcrypt/argon2) for hashing because API keys are 128-bit
  random (secrets.token_hex(8)) which is already un-brute-forceable.
  bcrypt would add latency to every validate_key() call with no real
  security benefit.
- aiosqlite (not SQLAlchemy async) for simplicity — this is a single
  table with straightforward CRUD, no ORM complexity needed.
- key_prefix (first 10 chars) stored alongside hash for human-readable
  identification without exposing the full secret.
"""

import hashlib
import secrets
import time
from dataclasses import dataclass

import aiosqlite


@dataclass
class APIKey:
    """Represents a validated API key with its metadata.

    WHAT: Immutable record of an API key's properties after successful
          validation. The raw key material is NOT stored here — only
          the hash and the visible prefix.

    Attributes:
        key_hash: SHA-256 hex digest of the raw key (stored in DB).
        key_prefix: First 10 characters of the raw key (e.g. "sk-m8-a1b2").
                    Used for human-readable identification in admin UIs.
        user_id: The M5 user ID this key belongs to.
        tier: Service tier — "basic", "pro", or "enterprise".
        created_at: Unix timestamp when the key was generated.
        is_active: Whether the key is currently valid for authentication.
        last_used_at: Unix timestamp of last successful authentication,
                      or None if never used.
    """
    key_hash: str
    key_prefix: str
    user_id: str
    tier: str
    created_at: float
    is_active: bool
    last_used_at: float | None = None


class KeyManager:
    """M8 API Key lifecycle management.

    WHAT: Complete lifecycle for API keys: generate new keys, validate
          incoming keys against the database, revoke keys by prefix,
          list keys per user or globally, and update last-used timestamps.

          Keys are generated as "sk-m8-{16hex}" (128 bits of entropy).
          Only SHA-256 hashes are stored in the SQLite database. The raw
          key is returned exactly once from generate_key() and must be
          saved by the caller.

    WHY: M8 needs its own key system independent of M5 user authentication.
         The gateway acts as the single entry point for all external API
         access. Hash-only storage ensures that a database compromise does
         not expose usable API keys.

    Usage:
        manager = KeyManager(db_path="./data/m8_gateway.db")
        raw_key = await manager.generate_key("user-001", "pro")
        # raw_key shown once to the user
        api_key = await manager.validate_key(raw_key)  # returns APIKey or None
        await manager.revoke_key("sk-m8-a1b2")          # revoke by prefix
        keys = await manager.list_keys("user-001")       # list user's keys
    """

    def __init__(self, db_path: str):
        """Initialize KeyManager with a path to the SQLite database.

        WHAT: Stores the database path. The actual connection is opened
              per-operation via aiosqlite.connect() for thread safety.

        Args:
            db_path: Filesystem path to the SQLite database file.
        """
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_table(self, conn: aiosqlite.Connection) -> None:
        """Create the api_keys table and indexes if they don't exist.

        WHAT: Idempotent DDL — creates the table, then two indexes
              for user-based and prefix-based lookups. Safe to call
              before every operation.

        WHY: Each connection is short-lived (opened and closed per
             operation), so the table must be guaranteed to exist
             before any DML. CREATE IF NOT EXISTS makes this safe
             to call redundantly.

        Table schema:
            key_hash TEXT PRIMARY KEY   — SHA-256 hex digest
            key_prefix TEXT NOT NULL    — first 10 chars of raw key
            user_id TEXT NOT NULL       — M5 user ID
            tier TEXT DEFAULT 'basic'   — service tier
            created_at REAL NOT NULL    — Unix timestamp
            is_active INTEGER DEFAULT 1 — 1=active, 0=revoked
            last_used_at REAL           — Unix timestamp or NULL
        """
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_hash TEXT PRIMARY KEY,
                key_prefix TEXT NOT NULL,
                user_id TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'basic',
                created_at REAL NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_used_at REAL
            )
        """)
        # Index for listing keys by user (most common admin query)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_keys_user ON api_keys(user_id)"
        )
        # Index for prefix-based lookup (used by revoke and touch)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_keys_prefix ON api_keys(key_prefix)"
        )
        await conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_key(self, user_id: str, tier: str = "basic") -> str:
        """Generate a new API key and store its hash in the database.

        WHAT: Creates a cryptographically random key in the format
              "sk-m8-{16hex}", computes its SHA-256 hash, and stores
              the hash + metadata in the api_keys table. Returns the
              raw key string — this is the ONLY time the full key is
              visible.

        WHY: secrets.token_hex(8) provides 128 bits of entropy (8 bytes
             = 16 hex chars), which is effectively un-brute-forceable.
             SHA-256 hashing means even a full database dump cannot be
             used to reconstruct valid API keys.

        Args:
            user_id: The M5 user ID to associate this key with.
            tier: Service tier for rate limiting — "basic", "pro",
                  or "enterprise". Defaults to "basic".

        Returns:
            The raw API key string (e.g. "sk-m8-a1b2c3d4e5f6g7h8").
            Caller must present this to the user and never store it
            in plaintext.
        """
        # Generate 8 random bytes → 16 hex characters
        raw = f"sk-m8-{secrets.token_hex(8)}"
        # Store only the SHA-256 hash; raw key is NEVER persisted
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        # Prefix for human-readable identification (first 10 chars)
        key_prefix = raw[:10]  # e.g. "sk-m8-a1b2"

        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_table(conn)
            await conn.execute(
                "INSERT INTO api_keys "
                "(key_hash, key_prefix, user_id, tier, created_at, is_active) "
                "VALUES (?, ?, ?, ?, ?, 1)",
                (key_hash, key_prefix, user_id, tier, time.time()),
            )
            await conn.commit()

        return raw

    async def validate_key(self, raw_key: str) -> APIKey | None:
        """Validate a raw API key against the database.

        WHAT: Computes SHA-256(raw_key), looks up the hash in the
              api_keys table, and returns an APIKey object if the
              key exists and is active. Returns None for invalid,
              revoked, or non-existent keys.

        WHY: Constant-time comparison is unnecessary here because
             SHA-256 pre-image resistance means an attacker cannot
             derive the raw key from the hash. The lookup is a simple
             indexed SELECT — fast enough for per-request auth.

        Args:
            raw_key: The full API key string from the Authorization header.

        Returns:
            APIKey dataclass if the key is valid and active, None otherwise.
        """
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_table(conn)
            cursor = await conn.execute(
                "SELECT key_hash, key_prefix, user_id, tier, "
                "created_at, is_active, last_used_at "
                "FROM api_keys WHERE key_hash = ? AND is_active = 1",
                (key_hash,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return APIKey(
                key_hash=row[0],
                key_prefix=row[1],
                user_id=row[2],
                tier=row[3],
                created_at=row[4],
                is_active=bool(row[5]),
                last_used_at=row[6],
            )

    async def revoke_key(self, key_prefix: str) -> bool:
        """Revoke an API key by its visible prefix.

        WHAT: Sets is_active=0 for the key matching the given prefix.
              Only affects currently active keys. Returns True if a
              key was found and revoked, False otherwise.

        WHY: Revocation by prefix is the admin-facing operation — the
             prefix is what admins see in list_keys() output. The full
             key is never shown after generation, so prefix is the only
             identifier available for revocation.

        Args:
            key_prefix: First 10 characters of the key (e.g. "sk-m8-a1b2").

        Returns:
            True if a key was found and revoked, False if no active key
            matched the prefix.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_table(conn)
            cursor = await conn.execute(
                "UPDATE api_keys SET is_active = 0 "
                "WHERE key_prefix = ? AND is_active = 1",
                (key_prefix,),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def list_keys(self, user_id: str | None = None) -> list[dict]:
        """List API keys, optionally filtered by user_id.

        WHAT: Returns a list of key metadata dictionaries. Only the
              key_prefix is shown — the full key and its hash are
              NEVER included in the output.

        WHY: Admins need to see which keys exist and their status
             without ever seeing the secret material. Excluding
             key_hash from the output is a security measure — even
             if an admin account is compromised, existing API keys
             cannot be extracted.

        Args:
            user_id: If provided, filter keys to this user only.
                     If None, return all keys.

        Returns:
            List of dicts with keys: key_prefix, user_id, tier,
            created_at, is_active, last_used_at.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await self._ensure_table(conn)
            if user_id:
                cursor = await conn.execute(
                    "SELECT key_prefix, user_id, tier, created_at, "
                    "is_active, last_used_at "
                    "FROM api_keys WHERE user_id = ? "
                    "ORDER BY created_at DESC",
                    (user_id,),
                )
            else:
                cursor = await conn.execute(
                    "SELECT key_prefix, user_id, tier, created_at, "
                    "is_active, last_used_at "
                    "FROM api_keys ORDER BY created_at DESC"
                )
            return [
                {
                    "key_prefix": r[0],
                    "user_id": r[1],
                    "tier": r[2],
                    "created_at": r[3],
                    "is_active": bool(r[4]),
                    "last_used_at": r[5],
                }
                async for r in cursor
            ]

    async def touch_key(self, key_prefix: str) -> None:
        """Update the last_used_at timestamp for a key.

        WHAT: Sets last_used_at to the current Unix timestamp for the
              key identified by its prefix. Called after each successful
              API request to track key activity.

        WHY: Tracking last usage enables key rotation policies (e.g.
             auto-revoke keys unused for 90 days) and helps identify
             stale or compromised keys. The prefix-based lookup is
             efficient via the idx_keys_prefix index.

        Args:
            key_prefix: First 10 characters of the key.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE key_prefix = ?",
                (time.time(), key_prefix),
            )
            await conn.commit()
