"""
Base class for document index backends.

WHY: Adds lifecycle methods to DocumentIndexProtocol for consistent
startup/shutdown across all index backends. The Protocol only defines
business operations (index, search, delete); lifecycle belongs to
the implementation layer because each backend has its own connection
strategy, health check mechanism, and cleanup requirements.
"""

from abc import ABC, abstractmethod

from contracts.storage import DocumentIndexProtocol


class BaseDocumentIndex(DocumentIndexProtocol, ABC):
    """
    Abstract document index with lifecycle management.

    All document index backends (Meilisearch, Elasticsearch, etc.)
    inherit from this class. It adds three lifecycle hooks:
    - initialize(): connect, create/verify index, configure fields
    - health_check(): verify the index is reachable
    - close(): release connections
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Set up the index (connect, create/verify index, configure fields).

        Called once at application startup. Must be idempotent --
        subsequent calls should not reset the index or lose data.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify the index is reachable.

        Called by monitoring endpoints. Returns True if the backend
        can process index and search requests, False otherwise.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """
        Release connections.

        Called at application shutdown. Must be safe even if
        initialize() was never called.
        """
        ...
