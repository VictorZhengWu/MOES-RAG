"""
SQLite implementation of BaseRelationalDB.

WHY: SQLite is the Personal-mode default relational database. It requires
zero configuration, no separate server process, and stores everything in
a single file. Combined with SQLAlchemy's async engine via aiosqlite,
it provides the same interface as PostgreSQL -- just a different
connection string.

M2 only provides the engine and session factory. ORM model classes
(User, Conversation, etc.) are defined by upper modules (M5).
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .base import BaseRelationalDB

logger = logging.getLogger(__name__)


class SQLiteDB(BaseRelationalDB):
    """Relational database backed by SQLite + SQLAlchemy 2.0 async."""

    def __init__(self, config):
        """Store config; engine is created lazily in initialize().

        WHY lazy: creating the engine in __init__ would make it impossible
        to test the unit without a filesystem. Deferring allows the caller
        to construct the object and call initialize() when ready.
        """
        self._config = config
        self._engine = None
        self._session_factory = None

    async def initialize(self) -> None:
        """Create async engine with WAL mode, auto-create parent directories.

        WHAT:
        - Creates the parent directory tree if it does not exist
        - Creates an async SQLAlchemy engine using aiosqlite
        - Enables WAL journal mode for concurrent read performance
        - Creates an async_sessionmaker for session creation

        WHY WAL mode: without WAL, SQLite locks the entire database during
        writes, blocking concurrent reads. WAL allows reads and writes to
        proceed concurrently, which is essential for a web application
        where multiple requests may hit the database simultaneously.

        WHY check_same_thread=False: aiosqlite runs operations on a
        background thread. SQLite's default check_same_thread=True would
        reject all operations from that thread as it differs from the
        thread that opened the connection.
        """
        # Resolve path early so error messages include the full path
        db_path = Path(self._config.path)

        # Auto-create parent directories so users can specify nested paths
        # like ./data/subdir/db.sqlite3 without pre-creating the directory tree
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create async engine targeting the SQLite file via aiosqlite driver
        self._engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False},
        )

        # Enable WAL journal mode -- persists across connections (DB-level)
        # Enable foreign key enforcement -- must be set per connection
        async with self._engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA foreign_keys=ON"))

        # Also set foreign_keys on every new connection via event listener.
        # The PRAGMA above only applies to the first connection. SQLAlchemy's
        # connection pool creates new connections that won't have this set
        # unless we use a connect-level event.
        from sqlalchemy import event
        def _set_fk_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        event.listen(self._engine.sync_engine, "connect", _set_fk_pragma)

        # Create session factory -- expire_on_commit=False prevents
        # SQLAlchemy from issuing SELECT queries to refresh attributes
        # after commit, which is important for async usage where lazy
        # loading would raise DetachedInstanceError
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info("SQLite initialized: %s (WAL mode)", self._config.path)

    async def health_check(self) -> bool:
        """Verify database is accessible with a lightweight query.

        WHAT: executes SELECT 1 against the engine and returns True if
        it succeeds. Returns False on any error (not just connectivity
        issues, but also schema corruption, permission errors, etc.).

        WHY lightweight: health checks are called frequently (by load
        balancers, monitoring systems). A heavyweight query would add
        unnecessary load. SELECT 1 is the standard database ping.
        """
        try:
            if self._engine is None:
                return False
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.warning("SQLite health check failed")
            return False

    async def close(self) -> None:
        """Dispose the engine and release all connections.

        WHAT: calls engine.dispose() which closes all connections in the
        pool and releases underlying resources (file handles, memory).

        WHY explicit close: SQLAlchemy's engine does not auto-close on
        garbage collection. Without explicit dispose(), file handles
        may leak, which is especially problematic on Windows where open
        file handles prevent deletion of the database file.
        """
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("SQLite engine disposed")

    async def get_session(self) -> AsyncSession:
        """Return an AsyncSession for use as an async context manager.

        WHAT: calls the session factory to create a new AsyncSession.
        The caller MUST use the session as an async context manager to
        ensure it is properly closed after use.

        WHY async factory method (not asynccontextmanager): the call
        convention is ``async with await db.get_session() as session``
        per the protocol definition. AsyncSession is itself a context
        manager whose __aexit__ closes the session, so a simple factory
        method achieves the same lifetime guarantee.

        Usage:
            async with await db.get_session() as session:
                result = await session.execute(text("SELECT 1"))

        Raises:
            RuntimeError: if initialize() has not been called yet.
        """
        if self._session_factory is None:
            raise RuntimeError(
                "SQLiteDB not initialized. Call await db.initialize() first."
            )
        return self._session_factory()
