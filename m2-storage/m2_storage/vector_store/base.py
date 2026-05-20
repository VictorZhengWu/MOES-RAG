"""
Base class for vector store backends.

WHY: Adds lifecycle methods (initialize, health_check, close) to the
contracts/storage.py VectorStoreProtocol. The Protocol only defines
business operations; lifecycle belongs to the implementation layer.

Separating lifecycle from business operations means the contracts/
package stays pure -- no assumptions about how backends start up
or shut down. Each backend module owns its own lifecycle.
"""

from abc import ABC, abstractmethod

from contracts.storage import VectorStoreProtocol


class BaseVectorStore(VectorStoreProtocol, ABC):
    """
    Abstract vector store with lifecycle management.

    All vector store backends (ChromaDB, Qdrant, Milvus, etc.)
    inherit from this class. It adds three lifecycle hooks:
    - initialize(): set up connections/collections
    - health_check(): verify the backend is operational
    - close(): release connections and resources
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Set up the backend (create collections, open connections).

        Called once at application startup before any search/insert
        operations. Must be idempotent -- calling it twice should
        not create duplicate collections.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify the backend is operational.

        Called by monitoring endpoints and load balancers.
        Returns True if the backend can serve requests, False otherwise.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """
        Release all resources held by this backend.

        Called at application shutdown. Must be safe to call even
        if initialize() was never called or failed.
        """
        ...
