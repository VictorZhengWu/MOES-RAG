"""Pydantic schemas for M8 API Gateway request/response validation.

WHAT: Pydantic models that define the shape of API requests and responses.
      Used by FastAPI for automatic validation, serialization, and OpenAPI
      documentation generation.
WHY: FastAPI requires Pydantic models for request body parsing. Separating
     schemas from contracts dataclasses allows M8 to version its API surface
     independently from internal module contracts. The schemas also provide
     stricter validation (e.g., numeric ranges for temperature/top_p).
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Chat Completion Request / Response
# ---------------------------------------------------------------------------


class MessageSchema(BaseModel):
    """A single chat message in an OpenAI-compatible conversation.

    WHAT: Represents one turn in a conversation with role and content fields.
          Roles are "user", "assistant", or "system" per OpenAI spec.
    WHY: Used as a nested model inside ChatCompletionRequest. Separated from
         the contract Message dataclass to provide Pydantic validation.
    """
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request body.

    WHAT: Full request payload for POST /v1/chat/completions. Mirrors the
          OpenAI API format with RAG-specific extension fields for domain
          and vessel type filtering.
    WHY: FastAPI uses this model to auto-validate incoming JSON, coercing
         types and rejecting malformed requests with 422 responses. The
         RAG extension fields allow the QA engine to scope retrieval to
         specific domains or vessel types.
    """
    model: str
    messages: list[MessageSchema]
    stream: bool = False
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=32768)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    user: str | None = None
    conversation_id: str | None = None
    # RAG-specific extensions (not part of OpenAI spec)
    domain_filter: str | None = None
    vessel_type_filter: str | None = None


# ---------------------------------------------------------------------------
# API Key Management Schemas
# ---------------------------------------------------------------------------


class APIKeyCreate(BaseModel):
    """Request body for creating a new API key via POST /admin/keys.

    WHAT: Minimal payload — just the user_id and optional tier. The raw key
          is generated server-side and returned once in the response.
    WHY: The caller should never provide their own key material; the server
         generates cryptographically random keys to guarantee entropy and
         prevent weak-key attacks.
    """
    user_id: str
    tier: str = "basic"


class APIKeyInfo(BaseModel):
    """Response model for API key metadata (masked -- only prefix shown).

    WHAT: Safe-for-display key information. Only the key_prefix (first 10
          chars) is exposed. The full key material and its hash are never
          included in list responses.
    WHY: Administrators need to see which keys exist and their status
         without access to secret material. Even if an admin account is
         compromised, existing API keys cannot be extracted from the API.
    """
    key_prefix: str
    user_id: str
    tier: str
    created_at: float
    is_active: bool
    last_used_at: float | None = None


class CreateKeyResponse(BaseModel):
    """Response for POST /admin/keys -- raw key returned ONCE.

    WHAT: Contains the full raw API key (shown only at creation time),
          its visible prefix, and the assigned tier.
    WHY: The caller must save the raw key immediately because the server
         stores only the SHA-256 hash and cannot recover the original.
    """
    key: str
    prefix: str
    tier: str


class RevokeKeyResponse(BaseModel):
    """Response for DELETE /admin/keys/{key_prefix}."""
    status: str
    key_prefix: str


# ---------------------------------------------------------------------------
# Error Response
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Standard error response following OpenAI API error format.

    WHAT: Structured error payload with a top-level error message and
          optional detail field. Matches the OpenAI API error shape so
          that OpenAI SDK clients display errors correctly.
    WHY: OpenAI-compatible error format enables seamless integration with
         existing tooling (OpenAI Python/JS SDKs, LangChain, etc.) that
         parse error responses expecting this structure.
    """
    error: str
    detail: str | None = None
