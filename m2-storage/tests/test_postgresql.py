"""
Tests for PostgreSQLDB -- the Enterprise/SaaS relational database backend.

WHAT: Verifies PostgreSQLDB satisfies RelationalDBProtocol, provides working
      async sessions, reports health correctly, and handles connection
      failures gracefully.

WHY: PostgreSQL is the recommended backend for Enterprise and SaaS
     deployments. These tests mirror test_sqlite.py to ensure both
     backends implement the same contract identically.

REQUIREMENTS:
    - PostgreSQL server (local, Docker, or remote)
    - Defaults: localhost:5432, user=postgres, password=test, db=marine_rag_test
    - Override via: PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE

    # Docker (quickest):
    docker run -d --name pg-test -p 5432:5432 \
      -e POSTGRES_PASSWORD=test -e POSTGRES_DB=marine_rag_test postgres:15

    # No PG available: tests auto-skip
"""

import asyncio
import os

import pytest
import pytest_asyncio
from sqlalchemy import text

from contracts.storage import RelationalDBProtocol

from m2_storage.config import PostgreSQLConfig
from m2_storage.relational_db.postgresql_db import PostgreSQLDB


# ---------------------------------------------------------------------------
# Auto-detect PostgreSQL availability
# ---------------------------------------------------------------------------

def _pg_is_available() -> bool:
    """Check if a PostgreSQL server is reachable with a fast socket connection.

    WHY: Tests auto-skip if no PG is available — no need for developers
         to install PostgreSQL just to run M2 tests. CI environments
         can provide PG via Docker service container.
    """
    import socket
    host = os.environ.get("PG_HOST", "localhost")
    port = int(os.environ.get("PG_PORT", "5432"))
    try:
        sock = socket.create_connection((host, port), timeout=1.5)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


PG_AVAILABLE = _pg_is_available()

# pytest markers for conditional skip
requires_pg = pytest.mark.skipif(
    not PG_AVAILABLE,
    reason="PostgreSQL not available. Start with: "
           "docker run -d --name pg-test -p 5432:5432 "
           "-e POSTGRES_PASSWORD=test -e POSTGRES_DB=marine_rag_test postgres:15"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _pg_config() -> PostgreSQLConfig:
    """Build PostgreSQLConfig from environment or defaults.

    WHY: Environment variable overrides allow CI to inject connection
         parameters without editing code. Defaults match the Docker
         command in the test file header.
    """
    return PostgreSQLConfig(
        host=os.environ.get("PG_HOST", "localhost"),
        port=int(os.environ.get("PG_PORT", "5432")),
        database=os.environ.get("PG_DATABASE", "marine_rag_test"),
        user=os.environ.get("PG_USER", "postgres"),
        password=os.environ.get("PG_PASSWORD", "test"),
        pool_size=2,
        max_overflow=2,
    )


@pytest_asyncio.fixture
async def pg_db():
    """Return an initialized PostgreSQLDB, cleaned up after test.

    WHY: Each test gets a fresh initialized database. The fixture
         handles async setup (initialize) and teardown (close) so
         tests don't leak connections.
    """
    config = _pg_config()
    db = PostgreSQLDB(config)
    await db.initialize()
    yield db
    await db.close()


# ---------------------------------------------------------------------------
# Test 1: Protocol compliance
# ---------------------------------------------------------------------------

@requires_pg
def test_protocol_compliance(pg_db):
    """PostgreSQLDB must satisfy RelationalDBProtocol.

    WHY: Upper modules depend on RelationalDBProtocol, not the concrete
         class. This test catches accidental signature drift between
         SQLiteDB and PostgreSQLDB.
    """
    assert isinstance(pg_db, RelationalDBProtocol), (
        "PostgreSQLDB must satisfy RelationalDBProtocol"
    )


# ---------------------------------------------------------------------------
# Test 2: get_session returns working session
# ---------------------------------------------------------------------------

@requires_pg
@pytest.mark.asyncio
async def test_get_session_works(pg_db):
    """A session from get_session() must be able to execute SQL.

    WHY: This is the primary access point for upper modules (M5).
         If a session cannot execute SELECT 1, every domain operation
         (user CRUD, conversation history, config storage) is broken.
    """
    async with await pg_db.get_session() as session:
        result = await session.execute(text("SELECT 1"))
        row = result.scalar()
        assert row == 1, f"Expected 1 from SELECT 1, got {row}"


# ---------------------------------------------------------------------------
# Test 3: Table creation and CRUD via session
# ---------------------------------------------------------------------------

@requires_pg
@pytest.mark.asyncio
async def test_create_table_and_insert(pg_db):
    """Verify that DDL and DML work through a session.

    WHAT: Creates a test table, inserts a row, and reads it back.
          This validates the full round-trip: DDL → INSERT → SELECT.

    WHY: Upper modules define ORM models and create tables via M2
         sessions. This test confirms that PostgreSQL supports the
         same SQL operations as SQLite without requiring ORM changes.
    """
    async with await pg_db.get_session() as session:
        # DDL: create test table
        await session.execute(text(
            "CREATE TEMPORARY TABLE IF NOT EXISTS _m2_test ("
            "  id SERIAL PRIMARY KEY,"
            "  name TEXT NOT NULL"
            ")"
        ))
        await session.commit()

        # DML: insert
        await session.execute(
            text("INSERT INTO _m2_test (name) VALUES (:name)"),
            {"name": "test-row"},
        )
        await session.commit()

        # DML: select
        result = await session.execute(text("SELECT name FROM _m2_test"))
        rows = result.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "test-row"


# ---------------------------------------------------------------------------
# Test 4: Health check
# ---------------------------------------------------------------------------

@requires_pg
@pytest.mark.asyncio
async def test_health_check(pg_db):
    """Initialized PostgreSQL must report healthy.

    WHY: M2 exposes a /health endpoint that aggregates health checks
         from all 4 backends. Each backend's health_check() must return
         True when the backend is operational.
    """
    result = await pg_db.health_check()
    assert result is True, "PostgreSQL health check should return True"


# ---------------------------------------------------------------------------
# Test 5: Connection failure handling (no running PG needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connection_failure_graceful():
    """Connecting to an unreachable host must raise an error during
    initialize(), not silently succeed.

    WHAT: Creates a PostgreSQLDB pointing at a non-existent server.
          initialize() should raise an exception (OSError or similar),
          not hang indefinitely or return normally.

    WHY: Silent failures at startup lead to runtime errors much later
         when code tries to use the session. Fast-fail at initialize()
         gives operators clear feedback about misconfiguration.
    """
    config = PostgreSQLConfig(
        host="255.255.255.255",  # Unreachable broadcast address
        port=5432,
        database="test",
        user="test",
        password="test",
        pool_size=1,
        max_overflow=1,
    )
    db = PostgreSQLDB(config)

    with pytest.raises(Exception):
        async with asyncio.timeout(5):  # 5s timeout — don't hang
            await db.initialize()
