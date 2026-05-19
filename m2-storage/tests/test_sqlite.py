"""
Tests for SQLiteDB -- the Personal-mode relational database backend.

WHY: SQLite is the primary relational store for Personal deployments.
It must provide a working async SQLAlchemy engine, return usable sessions,
and handle edge cases like non-existent parent directories.
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy import text

from contracts.storage import RelationalDBProtocol

from m2_storage.config import SQLiteConfig
from m2_storage.relational_db.sqlite_db import SQLiteDB


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_config(tmp_path):
    """Create a SQLiteConfig pointing at a temp file in a subdirectory.

    WHY subdirectory: test_auto_creates_parent_dir needs a multi-level
    path to verify mkdir(parents=True, exist_ok=True) works.
    """
    db_path = tmp_path / "subdir" / "test.db"
    return SQLiteConfig(path=str(db_path))


@pytest_asyncio.fixture
async def sqlite_db(sqlite_config):
    """Return an initialized SQLiteDB, cleaned up after test.

    WHY pytest_asyncio.fixture: supports async setup (initialize) and
    teardown (close) so each test starts with a fresh, ready database
    and no connection leaks between tests.
    """
    db = SQLiteDB(sqlite_config)
    await db.initialize()
    yield db
    await db.close()


# ---------------------------------------------------------------------------
# Test 1: Protocol compliance
# ---------------------------------------------------------------------------

def test_protocol_compliance(sqlite_db):
    """SQLiteDB must satisfy RelationalDBProtocol.

    WHY: upper modules depend on RelationalDBProtocol, not the concrete
    class. This test catches accidental signature drift.
    """
    assert isinstance(sqlite_db, RelationalDBProtocol)


# ---------------------------------------------------------------------------
# Test 2: initialize creates database file
# ---------------------------------------------------------------------------

def test_initialize_creates_file(sqlite_db, sqlite_config):
    """After initialize(), the .db file must exist on disk.

    WHY: SQLAlchemy's create_async_engine may defer file creation until
    the first connection. We verify that after initialize() (which
    executes PRAGMA journal_mode=WAL), the file is physically present.
    """
    assert os.path.exists(sqlite_config.path)


# ---------------------------------------------------------------------------
# Test 3: get_session returns working session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_session_works(sqlite_db):
    """A session from get_session() must be able to execute SQL.

    WHY: this is the primary access point for upper modules. If a session
    cannot execute a simple SELECT 1, every domain operation (user CRUD,
    conversation history, config storage) is broken.
    """
    async with await sqlite_db.get_session() as session:
        result = await session.execute(text("SELECT 1"))
        row = result.scalar()
        assert row == 1


# ---------------------------------------------------------------------------
# Test 4: health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check(sqlite_db):
    """Initialized database must report healthy.

    WHY: M2 exposes a /health endpoint that aggregates health checks
    from all 4 backends. Each backend's health_check() must return True
    when the backend is operational.
    """
    assert await sqlite_db.health_check() is True


# ---------------------------------------------------------------------------
# Test 5: auto-creates parent directory
# ---------------------------------------------------------------------------

def test_auto_creates_parent_dir(tmp_path):
    """If the parent directory does not exist, initialize must create it.

    WHY: users may specify a path like ./data/subdir/db.sqlite3 in
    deploy.yaml. M2 must create intermediate directories rather than
    failing with a cryptic "No such file or directory" error.
    """
    db_path = tmp_path / "new_subdir" / "deep" / "test.db"
    config = SQLiteConfig(path=str(db_path))
    db = SQLiteDB(config)

    assert not os.path.exists(str(db_path.parent))

    import asyncio

    async def _init():
        await db.initialize()
        await db.close()

    asyncio.run(_init())

    assert os.path.exists(str(db_path))
