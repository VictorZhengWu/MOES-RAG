"""
Base class for relational database backends.

WHY: Adds lifecycle methods to RelationalDBProtocol. M2 only provides
the engine and session -- ORM models are defined by upper modules (M5
Knowledge Base Manager). This separation means M2 owns the database
connection lifecycle but not the schema, keeping storage concerns
decoupled from domain model concerns.
"""

from abc import ABC, abstractmethod

from contracts.storage import RelationalDBProtocol


class BaseRelationalDB(RelationalDBProtocol, ABC):
    """
    Abstract relational DB with lifecycle management.

    All relational database backends (SQLite, PostgreSQL, etc.)
    inherit from this class. M2 provides the async engine and session
    factory; upper modules define ORM models and use get_session()
    to access the database.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Create engine and run schema setup.

        Called once at application startup. Creates the SQLAlchemy
        async engine, verifies connectivity, and runs any necessary
        schema migrations.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify database connectivity.

        Typically runs a lightweight query like "SELECT 1" to confirm
        the database is reachable and responsive.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """
        Dispose engine and connection pool.

        Called at application shutdown. Gracefully closes all pooled
        connections and disposes the engine.
        """
        ...
