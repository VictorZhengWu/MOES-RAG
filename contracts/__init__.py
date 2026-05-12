"""
Contracts Package - Interface definitions for all modules.

This package defines the protocols, data models, and API schemas
that form the contract between modules. Every module depends ONLY
on this package, never on another module directly.

DO NOT add implementation code here. This is pure interface definition.
"""

__version__ = "0.1.0"

# Document data models (used by M1 → M2 → M3/M4/M5)
from contracts.document import (
    Chunk,
    ClassificationSociety,
    DocumentMetadata,
    Domain,
    ParsedDocument,
    VesselType,
)

# Storage protocols (M2 interface)
from contracts.storage import (
    DocumentIndexProtocol,
    FileStoreProtocol,
    RelationalDBProtocol,
    VectorStoreProtocol,
)

# Retrieval protocols (M3 interface)
from contracts.retrieval import (
    RetrievedContext,
    RetrievalEngineProtocol,
    RetrievalRequest,
    ScoredChunk,
)

# Knowledge Graph protocols (M4 interface)
from contracts.knowledge_graph import (
    CrossReferenceResult,
    Entity,
    KGEngineProtocol,
    Relation,
    Subgraph,
)

# QA Engine protocols (M5 interface)
from contracts.qa_engine import (
    ChatRequest,
    ChatResponse,
    Choice,
    Citation,
    ConversationSummary,
    Message,
    QAEngineProtocol,
    Usage,
)

# REST API schemas (used by M5/M6/M7/M8)
from contracts.api_schemas import (
    AdminUserCreateRequest,
    AdminUserInfo,
    ConversationRenameRequest,
    DocumentInfo,
    DocumentUploadRequest,
    DocumentUploadResponse,
    ErrorResponse,
    HealthResponse,
    KGEntityResponse,
    KGRelationResponse,
    LLMBackendConfig,
    LLMBackendType,
    PaginatedResponse,
    ParseTaskStatus,
    SupportedLanguage,
    SystemStats,
    UserSettings,
    UserSettingsUpdateRequest,
)

__all__ = [
    # Document
    "Chunk", "ClassificationSociety", "DocumentMetadata", "Domain",
    "ParsedDocument", "VesselType",
    # Storage
    "DocumentIndexProtocol", "FileStoreProtocol", "RelationalDBProtocol",
    "VectorStoreProtocol",
    # Retrieval
    "RetrievedContext", "RetrievalEngineProtocol", "RetrievalRequest", "ScoredChunk",
    # Knowledge Graph
    "CrossReferenceResult", "Entity", "KGEngineProtocol", "Relation", "Subgraph",
    # QA Engine
    "ChatRequest", "ChatResponse", "Choice", "Citation", "ConversationSummary",
    "Message", "QAEngineProtocol", "Usage",
    # API Schemas
    "AdminUserCreateRequest", "AdminUserInfo", "ConversationRenameRequest",
    "DocumentInfo", "DocumentUploadRequest", "DocumentUploadResponse",
    "ErrorResponse", "HealthResponse", "KGEntityResponse", "KGRelationResponse",
    "LLMBackendConfig", "LLMBackendType", "PaginatedResponse", "ParseTaskStatus",
    "SupportedLanguage", "SystemStats", "UserSettings", "UserSettingsUpdateRequest",
]
