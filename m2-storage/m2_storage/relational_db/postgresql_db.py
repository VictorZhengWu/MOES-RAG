"""
PostgreSQL implementation of BaseRelationalDB.

WHAT: Implements BaseRelationalDB using PostgreSQL via the asyncpg driver.
      Provides the same async SQLAlchemy engine + session factory interface
      as SQLiteDB, but backed by a full PostgreSQL server.

WHY: SQLite is adequate for Personal single-user deployments, but
     Enterprise and SaaS deployments need PostgreSQL for:
     - Concurrent write performance (MVCC, row-level locking)
     - Connection pooling across multiple application instances
     - Horizontal scalability (read replicas)
     - Point-in-time recovery and backup tooling

M2 only provides the engine and session factory. ORM model classes
(User, Conversation, etc.) are defined by upper modules (M5). Switching
from SQLite to PostgreSQL requires ZERO changes to upper modules --
only deploy.yaml needs updating.

CONNECTION STRING: postgresql+asyncpg://user:pass@host:port/database
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .base import BaseRelationalDB

logger = logging.getLogger(__name__)


class PostgreSQLDB(BaseRelationalDB):
    """Relational database backed by PostgreSQL + SQLAlchemy 2.0 async.

    WHAT: Wraps a PostgreSQL database with async SQLAlchemy engine and
          session factory. Uses asyncpg driver (fastest Python PostgreSQL
          driver, pure async, supports prepared statements).

    WHY asyncpg: 2-3x faster than psycopg3 for typical workloads, pure
          Python with no C extensions to compile, and has the most mature
          async support of any PostgreSQL driver.

    CONNECTION MANAGEMENT:
        - pool_pre_ping=True: Tests connections before use. Detects
          connections dropped by load balancers or firewalls.
        - pool_recycle=3600: Recycles connections every hour to prevent
          memory leaks from long-lived connections.
        - pool_size + max_overflow: Configurable via PostgreSQLConfig.
          Defaults: 10 base connections + 20 overflow = 30 max.
    """

    def __init__(self, config):
        """Store config; engine is created lazily in initialize().

        WHY lazy: creating the engine in __init__ would attempt a network
        connection immediately, making it impossible to test the object
        construction without a running PostgreSQL server. Deferring to
        initialize() allows the caller to construct and configure first.
        """
        self._config = config
        self._engine: Optional[object] = None
        self._session_factory: Optional[object] = None

    # ------------------------------------------------------------------
    # Connection URL construction
    # ------------------------------------------------------------------

    def _build_connection_url(self) -> str:
        """Build the SQLAlchemy asyncpg connection URL from config.

        WHAT: Constructs a URL-safe connection string with URL-encoded
              user and password to handle special characters.

        WHY: PostgreSQL connection strings use standard URL encoding.
              Passwords with @, :, /, or other special chars must be
              percent-encoded to avoid breaking the URL parser.

        ENV VAR OVERRIDE: The password field supports ${VAR} syntax.
              If the config value starts with ${ and ends with }, the
              actual value is read from the environment variable.
        """
        host: str = self._config.host
        port: int = self._config.port
        database: str = self._config.database
        user: str = self._config.user
        password: str = self._config.password

        # Resolve environment variable references in password
        # Format: ${PG_PASSWORD} → os.environ["PG_PASSWORD"]
        if password.startswith("${") and password.endswith("}"):
            env_var = password[2:-1]
            password = os.environ.get(env_var, "")

        # URL-encode user and password to handle special characters
        encoded_user: str = urllib.parse.quote_plus(user)
        encoded_password: str = urllib.parse.quote_plus(password)

        return (
            f"postgresql+asyncpg://"
            f"{encoded_user}:{encoded_password}@"
            f"{host}:{port}/{database}"
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Create async engine with connection pooling, verify connectivity.

        WHAT:
        - Builds the asyncpg connection URL
        - Creates an async SQLAlchemy engine with pool configuration
        - Applies SSL connect_args if ssl_mode requires it
        - Validates connectivity with a test connection
        - Creates an async_sessionmaker for session creation

        WHY pool_pre_ping: PostgreSQL connections can be silently dropped
        by network middleware (load balancers, NAT gateways, firewalls).
        pool_pre_ping=True sends a lightweight ping before each connection
        use, detecting and replacing dead connections transparently.

        WHY pool_recycle: long-lived connections accumulate memory on both
        client and server side. Recycling every 3600s prevents gradual
        memory growth while being infrequent enough not to impact latency.
        """
        url: str = self._build_connection_url()

        # Build SSL connect_args from ssl_mode config
        connect_args: dict = {}
        ssl_mode: str = getattr(self._config, 'ssl_mode', 'prefer')
        if ssl_mode in ("require", "prefer"):
            connect_args["ssl"] = ssl_mode

        self._engine = create_async_engine(
            url,
            pool_size=self._config.pool_size,
            max_overflow=self._config.max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args=connect_args if connect_args else {},
            echo=False,
        )

        # Verify connectivity with a simple test query
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        # Create session factory
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info(
            "PostgreSQL initialized: %s:%d/%s (pool_size=%d, max_overflow=%d)",
            self._config.host, self._config.port,
            self._config.database,
            self._config.pool_size, self._config.max_overflow,
        )

    async def health_check(self) -> bool:
        """Verify database is accessible with SELECT 1.

        WHAT: Executes a lightweight query against the engine. Returns
              True on success, False on any error.

        WHY: Same as SQLiteDB.health_check() — consistent interface
              across all relational DB backends. Load balancers and
              monitoring systems can call this without adding load.
        """
        try:
            if self._engine is None:
                return False
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.warning("PostgreSQL health check failed", exc_info=True)
            return False

    async def close(self) -> None:
        """Dispose engine and release all connections in the pool.

        WHAT: Calls engine.dispose() which closes all connections and
              releases TCP sockets immediately.

        WHY: Without explicit dispose(), pooled connections may linger
              until garbage collection, causing "too many connections"
              errors on the PostgreSQL server during development restarts.
        """
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("PostgreSQL engine disposed")

    async def get_session(self) -> AsyncSession:
        """Return an AsyncSession for use as an async context manager.

        WHAT: Returns a new AsyncSession from the session factory.
              The caller MUST use it as 'async with await db.get_session()
              as session:' to ensure proper cleanup.

        Raises:
            RuntimeError: if initialize() has not been called.
        """
        if self._session_factory is None:
            raise RuntimeError(
                "PostgreSQLDB not initialized. Call await db.initialize() first."
            )
        return self._session_factory()
