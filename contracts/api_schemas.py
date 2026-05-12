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
