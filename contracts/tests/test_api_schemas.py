"""
Validate all Pydantic schemas in contracts/api_schemas.py.

WHY: Pydantic models are the source of truth for API request/response
formats. If a schema is broken, every consumer (Mock Server, M5, M6,
M7, M8) will produce or expect malformed data. These tests catch
schema regressions before they propagate.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

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


class TestDocumentUploadRequest:
    """Document upload request accepts valid data and rejects invalid."""

    def test_valid_minimal_request(self, sample_document_upload):
        """Verify a valid minimal document upload request is accepted."""
        req = DocumentUploadRequest(**sample_document_upload)
        assert req.file_name == "dnv-pt4-ch3-2024.pdf"
        assert req.classification_society == "DNV"
        assert req.domain == "structure"
        assert req.language == "en"  # default

    def test_rejects_missing_file_name(self):
        """Verify missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            DocumentUploadRequest()

    def test_defaults(self):
        """Verify all optional fields have correct defaults."""
        req = DocumentUploadRequest(file_name="test.pdf")
        assert req.domain == "general"
        assert req.vessel_types == []
        assert req.language == "en"
        assert req.custom_tags == {}


class TestLLMBackendConfig:
    """LLM backend config enum and model validation."""

    def test_valid_backend_types(self):
        """Verify all enum members produce valid configs."""
        for bt in LLMBackendType:
            config = LLMBackendConfig(
                backend_id=f"test-{bt.value}",
                backend_type=bt,
                model_name="test-model",
            )
            assert config.backend_type == bt

    def test_defaults(self):
        """Verify sensible defaults on LLM backend config."""
        config = LLMBackendConfig(
            backend_id="test", backend_type="ollama", model_name="llama3"
        )
        assert config.max_tokens == 4096
        assert config.temperature == 0.7
        assert config.is_default is False
        assert config.assigned_agents == []


class TestSupportedLanguage:
    """Language enum contains the five supported locales."""

    def test_all_five_languages_present(self):
        """Verify all 5 required languages are in the enum."""
        values = {lang.value for lang in SupportedLanguage}
        assert values == {"en", "zh", "ko", "ja", "no"}

    def test_default_is_english(self):
        """Verify English is the default language."""
        assert SupportedLanguage.EN.value == "en"


class TestErrorResponse:
    """Error response schema handles all error shapes."""

    def test_minimal_error(self):
        """Verify error with only message field is valid."""
        err = ErrorResponse(error="Something went wrong")
        assert err.error == "Something went wrong"
        assert err.detail is None
        assert err.code is None

    def test_full_error(self):
        """Verify error with all optional fields is valid."""
        err = ErrorResponse(error="Not found", detail="Doc #42", code="NOT_FOUND")
        assert err.code == "NOT_FOUND"


class TestPaginatedResponse:
    """Paginated wrapper accepts any item list."""

    def test_wraps_items(self):
        """Verify paginated response wraps items correctly."""
        page = PaginatedResponse(total=100, limit=10, offset=0, items=[{"a": 1}])
        assert page.total == 100
        assert len(page.items) == 1


class TestAdminSchemas:
    """Admin-specific schemas validate correctly."""

    def test_admin_user_create(self):
        """Verify default role is viewer for new users."""
        req = AdminUserCreateRequest(
            username="admin1", email="admin@shipyard.com", password="s3cret"
        )
        assert req.role == "viewer"  # default

    def test_system_stats_defaults_to_zero(self):
        """Verify system stats default to zero (empty system)."""
        stats = SystemStats()
        assert stats.total_documents == 0


class TestHealthResponse:
    """Health check response schema."""

    def test_valid_health(self):
        """Verify health response with module statuses."""
        health = HealthResponse(
            status="ok", version="0.1.0",
            modules={"m5": "ok"}, uptime_seconds=3600.0
        )
        assert health.status == "ok"
        assert health.modules["m5"] == "ok"
