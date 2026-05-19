"""
SQLite implementation of BaseRelationalDB (STUB -- real impl in Task 6).

WHY: This stub allows factory.py to import SQLiteDB without needing
SQLAlchemy installed. Task 6 replaces this with the full async SQLAlchemy
implementation including connection pooling, WAL mode, and foreign key
enforcement.

The stub raises NotImplementedError for get_session() because it is
the primary access point for upper modules -- they must not silently
get a non-functional session.
"""

from __future__ import annotations

from .base import BaseRelationalDB


class SQLiteDB(BaseRelationalDB):
    """
    Relational database backed by SQLite + SQLAlchemy async.

    SQLite was chosen as the Personal-mode default because it requires
    zero configuration (single file), no separate server process, and
    supports the full SQL feature set needed for metadata storage.

    Full implementation in Task 6 will add:
    - sqlalchemy.ext.asyncio.create_async_engine with aiosqlite
    - WAL journal mode for concurrent read/write
    - Foreign key enforcement via PRAGMA
    - Connection pooling with QueuePool
    - Async session factory via async_sessionmaker
    """

    def __init__(self, config):
        self._config = config
        self._engine = None

    async def initialize(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def close(self) -> None:
        pass

    async def get_session(self):
        """
        Return an async database session (STUB -- Task 6 implements).

        Raises NotImplementedError intentionally: upper modules that
        call this must not silently receive a non-functional session.
        """
        raise NotImplementedError("SQLiteDB.get_session -- real impl in Task 6")
