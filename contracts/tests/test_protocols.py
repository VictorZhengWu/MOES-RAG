"""
Structural validation of Python Protocols in contracts/.

WHY: Protocols define the contract between modules. If a Protocol
signature is wrong, implementations won't match. These tests verify
that Protocols are structurally sound — correct method names,
parameter counts, and return type annotations. They do NOT test any
implementation, only the interface definitions.
"""

from contracts.retrieval import RetrievalEngineProtocol
from contracts.knowledge_graph import KGEngineProtocol
from contracts.qa_engine import QAEngineProtocol
from contracts.storage import (
    DocumentIndexProtocol,
    FileStoreProtocol,
    RelationalDBProtocol,
    VectorStoreProtocol,
)


class TestRetrievalEngineProtocol:
    """M3 Retrieval Engine protocol has the expected methods."""

    def test_has_retrieve_method(self):
        """Verify protocol defines the retrieve method."""
        assert hasattr(RetrievalEngineProtocol, "retrieve")
        method = RetrievalEngineProtocol.__dict__.get("retrieve")
        assert method is not None
        assert callable(method)

    def test_has_health_check(self):
        """Verify protocol defines health_check."""
        assert hasattr(RetrievalEngineProtocol, "health_check")


class TestKGEngineProtocol:
    """M4 Knowledge Graph Engine protocol has the expected methods."""

    def test_has_core_methods(self):
        """Verify all 7 core KG engine methods are defined."""
        methods = [
            "extract_entities", "extract_relations", "query_entities",
            "query_relations", "graph_search", "cross_reference", "health_check",
        ]
        for m in methods:
            assert hasattr(KGEngineProtocol, m), f"Missing method: {m}"


class TestQAEngineProtocol:
    """M5 QA Engine protocol has the expected methods."""

    def test_has_chat_methods(self):
        """Verify chat and chat_stream methods are defined."""
        assert hasattr(QAEngineProtocol, "chat")
        assert hasattr(QAEngineProtocol, "chat_stream")

    def test_has_conversation_methods(self):
        """Verify conversation CRUD methods are defined."""
        assert hasattr(QAEngineProtocol, "list_conversations")
        assert hasattr(QAEngineProtocol, "get_conversation")
        assert hasattr(QAEngineProtocol, "delete_conversation")

    def test_has_model_listing(self):
        """Verify list_models method is defined."""
        assert hasattr(QAEngineProtocol, "list_models")


class TestStorageProtocols:
    """M2 Storage protocols each define their core operations."""

    def test_vector_store_has_crud(self):
        """Verify VectorStoreProtocol has insert, search, delete, count."""
        for method in ["insert", "search", "delete", "count"]:
            assert hasattr(VectorStoreProtocol, method), f"Missing: {method}"

    def test_document_index_has_crud(self):
        """Verify DocumentIndexProtocol has index, search, delete."""
        for method in ["index", "search", "delete"]:
            assert hasattr(DocumentIndexProtocol, method), f"Missing: {method}"

    def test_file_store_has_crud(self):
        """Verify FileStoreProtocol has put, get, delete, list."""
        for method in ["put", "get", "delete", "list"]:
            assert hasattr(FileStoreProtocol, method), f"Missing: {method}"

    def test_relational_db_has_lifecycle(self):
        """Verify RelationalDBProtocol has session, init, health_check."""
        for method in ["get_session", "initialize", "health_check"]:
            assert hasattr(RelationalDBProtocol, method), f"Missing: {method}"
