"""First-run admin bootstrap.

WHAT: On M8 startup, if the users table is empty (fresh database), create
      a default admin user + an admin-tier API key, and persist the raw
      key to <data_dir>/admin_key.txt + log it. Idempotent — skips if any
      user already exists.

WHY: The M7 admin portal logs in via POST /auth/admin-login, which
     requires a pre-existing user with is_admin=1 or tier in (admin,
     editor). A brand-new deployment has an empty users table, so there
     is no way to get the first admin key without this bootstrap.
     Writing the key to a file lets the operator retrieve it without
     scraping logs.

Security: Runs ONLY when the users table is completely empty. On any
          subsequent start it will NOT re-run. The admin_key.txt file is
          written with mode 0600. The admin password is a placeholder —
          admin authenticates via API key, not password.
"""

from __future__ import annotations

import logging
import os
import time

import aiosqlite

logger = logging.getLogger("m8_gateway.bootstrap")

# "admin" is in _BANNED_USERNAMES (auth.py), so use a non-reserved name.
DEFAULT_ADMIN_USERNAME = "moes-admin"
DEFAULT_ADMIN_EMAIL = "admin@local.system"
DEFAULT_ADMIN_PASSWORD = "marine-admin-change-me"  # placeholder; login via API key
ADMIN_USER_ID = "user-bootstrap-admin"  # stable id for idempotency check


async def bootstrap_admin_if_needed(db_path: str) -> str | None:
    """Create a default admin user + key if the users table is empty.

    Args:
        db_path: Path to the SQLite database (same as KeyManager uses).

    Returns:
        The raw API key if bootstrap ran, or None if it was skipped
        (users already exist).
    """
    # Ensure the data directory exists (mirrors app.py startup logic).
    db_dir = os.path.dirname(db_path) or "."
    os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(db_path) as conn:
        # Create users table if missing (mirror _ensure_users_table schema).
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

        # Idempotency: only bootstrap on a completely empty users table.
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        (count,) = await cursor.fetchone()
        if count > 0:
            logger.info("bootstrap: skipped (%d users already exist)", count)
            return None

        # Insert admin user. password_hash is a placeholder since admin
        # authenticates via API key, not password login.
        from m8_gateway.routes.auth import _hash_password
        pw_hash = _hash_password(DEFAULT_ADMIN_PASSWORD)
        await conn.execute(
            "INSERT INTO users (user_id, username, email, password_hash, "
            "password_salt, tier, is_admin, created_at) "
            "VALUES (?, ?, ?, ?, '', 'admin', 1, ?)",
            (ADMIN_USER_ID, DEFAULT_ADMIN_USERNAME,
             DEFAULT_ADMIN_EMAIL, pw_hash, time.time()),
        )
        await conn.commit()

    # Generate admin-tier API key via the same KeyManager used at runtime.
    from m8_gateway.auth.key_manager import KeyManager
    km = KeyManager(db_path)
    raw_key = await km.generate_key(ADMIN_USER_ID, "admin")

    # Persist raw key to file (mode 0600) inside the data directory.
    key_file = os.path.join(db_dir, "admin_key.txt")
    fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(raw_key + "\n")
    os.chmod(key_file, 0o600)

    logger.warning(
        "bootstrap: created default admin user '%s' (user_id=%s). "
        "Admin API key written to %s and printed below (FIRST RUN ONLY):\n    %s",
        DEFAULT_ADMIN_USERNAME, ADMIN_USER_ID, key_file, raw_key,
    )
    print("\n" + "=" * 60)
    print("  FIRST-RUN ADMIN API KEY (save this now):")
    print(f"    {raw_key}")
    print(f"  Also saved to: {key_file}")
    print("  Use it to log into the Admin Portal at http://localhost:3001")
    print("=" * 60 + "\n", flush=True)

    return raw_key
