"""
REST API schemas (Pydantic models) shared across modules.

Used by M5 (QA Engine), M6 (User Portal), M7 (Admin Portal), M8 (API Gateway).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── i18n: Supported Languages ──────────────────────────────────────

class SupportedLanguage(str, Enum):
    """
    Languages supported by the system UI.

    WHY: The frontend needs a canonical list of supported locales for the
    language switcher component, API Accept-Language header validation,
    and user profile persistence. Using an enum prevents typos and
    provides a single source of truth across M6, M7, and M8.
    """
    EN = "en"   # English (default)
    ZH = "zh"   # Chinese
    KO = "ko"   # Korean
    JA = "ja"   # Japanese
    NO = "no"   # Norwegian


# ── Admin: Document Upload ──────────────────────────────────────────

class DocumentUploadRequest(BaseModel):
    """Request to upload and parse a document."""
    file_name: str
    classification_society: str | None = None
    regulation_name: str | None = None
    version_year: int | None = None
    domain: str = "general"
    vessel_types: list[str] = Field(default_factory=list)
    system_type: str | None = None
    manufacturer: str | None = None
    language: str = "en"  # Document language (may differ from UI language)
    custom_tags: dict[str, str] = Field(default_factory=dict)

class DocumentUploadResponse(BaseModel):
    """Response after initiating document parsing."""
    task_id: str
    doc_id: str
    status: str  # "queued" | "processing" | "completed" | "failed"
    created_at: datetime


class ParseTaskStatus(BaseModel):
    """Status of a document parsing task."""
    task_id: str
    doc_id: str
    status: str
    progress_pct: float = 0.0
    chunks_count: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# ── Admin: Knowledge Base ───────────────────────────────────────────

class DocumentInfo(BaseModel):
    """Summary of an ingested document in the knowledge base."""
    doc_id: str
    source_filename: str
    classification_society: str | None
    regulation_name: str | None
    version_year: int | None
    domain: str
    chunks_count: int
    ingested_at: datetime
    status: str  # "active" | "deprecated" | "error"


# ── Admin: LLM Configuration ────────────────────────────────────────

class LLMBackendType(str, Enum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    OLLAMA = "ollama"
    VLLM = "vllm"
    LMSTUDIO = "lmstudio"
    CUSTOM = "custom"


class LLMBackendConfig(BaseModel):
    """Configuration for a single LLM backend."""
    backend_id: str
    backend_type: LLMBackendType
    model_name: str
    base_url: str | None = None
    api_key: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    is_default: bool = False
    assigned_agents: list[str] = Field(default_factory=list)  # e.g. ["structure", "electrical"]


# ── Common ───────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: str | None = None
    code: str | None = None


class PaginatedResponse(BaseModel):
    """Wrapper for paginated list responses."""
    total: int
    limit: int
    offset: int
    items: list[Any]


# ── Chat & Conversations ────────────────────────────────────────────

class ConversationRenameRequest(BaseModel):
    """
    Request to rename a conversation.

    WHY: M6 provides an inline-edit feature on the conversation list.
    The API needs a dedicated lightweight endpoint (PATCH) rather than
    a full PUT because only the title field is mutable by users.
    """
    title: str


# ── User Settings ───────────────────────────────────────────────────

class UserSettings(BaseModel):
    """
    User preferences persisted server-side.

    WHY: Language preference and notification settings must survive
    across browser sessions and devices. Storing server-side (with
    localStorage as a fast cache) enables cross-device sync.
    """
    language: str = "en"
    theme: str = "light"


class UserSettingsUpdateRequest(BaseModel):
    """Partial update for user settings."""
    language: str | None = None
    theme: str | None = None


# ── Admin: Knowledge Graph Browser ──────────────────────────────────

class KGEntityResponse(BaseModel):
    """A knowledge graph entity returned to the admin UI."""
    entity_id: str
    name: str
    entity_type: str
    properties: dict[str, object] = Field(default_factory=dict)
    source_doc_id: str | None = None


class KGRelationResponse(BaseModel):
    """A knowledge graph relation returned to the admin UI."""
    relation_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    source_entity_name: str = ""
    target_entity_name: str = ""
    confidence: float = 1.0


# ── Admin: System Stats ─────────────────────────────────────────────

class SystemStats(BaseModel):
    """
    Dashboard statistics for the admin monitoring page.

    WHY: M7's monitoring dashboard needs aggregated numbers.
    These come from a /stats endpoint rather than querying each
    subsystem separately, avoiding N+1 calls on dashboard load.
    """
    total_documents: int = 0
    total_chunks: int = 0
    total_entities: int = 0
    total_relations: int = 0
    total_conversations: int = 0
    total_users: int = 0
    storage_size_bytes: int = 0
    avg_retrieval_latency_ms: float = 0.0


# ── Admin: User Management ──────────────────────────────────────────

class AdminUserInfo(BaseModel):
    """User record visible to admins."""
    user_id: str
    username: str
    email: str
    role: str  # "admin" | "editor" | "viewer"
    is_active: bool = True
    api_key_count: int = 0
    total_queries: int = 0
    created_at: str = ""


class AdminUserCreateRequest(BaseModel):
    """Request to create a new user via admin panel."""
    username: str
    email: str
    password: str
    role: str = "viewer"


# ── Health ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """
    System health check response.

    WHY: Docker health checks, load balancer probes, and the admin
    dashboard all need a standardized health endpoint. Each module
    can report its own status independently.
    """
    status: str  # "ok" | "degraded" | "down"
    version: str
    modules: dict[str, str] = Field(default_factory=dict)
    uptime_seconds: float = 0.0
