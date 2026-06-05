"""
Tests for M8 document upload route.

WHAT: Verify the POST /api/v1/documents/upload endpoint:
  - Authentication required (401 without key)
  - File type whitelist enforcement (400 for blocked extensions)
  - File size limit enforcement (413 for oversized files)
  - M1 unavailable handling (503 when M1 is not running)
"""

import pytest
from fastapi.testclient import TestClient


def test_upload_requires_auth(test_app):
    """POST without auth header → 401."""
    app, _, _ = test_app
    client = TestClient(app)
    resp = client.post("/api/v1/documents/upload")
    assert resp.status_code == 401


def test_upload_blocked_extension(test_app):
    """POST .exe file → 400 (blocked by whitelist)."""
    app, api_key, _ = test_app
    client = TestClient(app)
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("malware.exe", b"fake exe", "application/octet-stream")},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert resp.status_code == 400
    assert "not supported" in resp.json()["detail"].lower()


def test_upload_allowed_extension(test_app):
    """POST .pdf file with valid auth → M1 unavailable (503), not 400."""
    app, api_key, _ = test_app
    client = TestClient(app)
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
        data={"output_dir": "./output"},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    # .pdf is allowed → should pass validation, fail at M1 proxy (503/502)
    assert resp.status_code in (502, 503)


def test_upload_oversized_file(test_app):
    """POST file exceeding 200MB → 413."""
    app, api_key, _ = test_app
    client = TestClient(app)
    # Override MAX_FILE_SIZE for the test by creating a small chunk
    # and then patching: actually, just send a request with headers
    # claiming a huge file. FastAPI streams, but TestClient reads all.
    # Instead, we test the error message format for the 413 case
    # by verifying a known-too-large file triggers the right status.
    # For test speed, we only verify the path is wired; actual size
    # enforcement is tested via the route's logic.
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("big.pdf", b"x" * 300_000_000, "application/pdf")},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert resp.status_code == 413


def test_upload_empty_filename(test_app):
    """POST without filename → 401 (auth check comes first)."""
    app, _, _ = test_app
    client = TestClient(app)
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("", b"", "application/octet-stream")},
    )
    assert resp.status_code == 401


def test_error_message_no_internal_commands(test_app):
    """Verify error messages do NOT expose internal commands or code paths."""
    app, api_key, _ = test_app
    client = TestClient(app)
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", b"x", "application/pdf")},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    # Should get 503 (M1 not running)
    assert resp.status_code in (502, 503)
    detail = resp.json().get("detail", "")
    # Should NOT contain internal commands or code
    assert "python -c" not in detail
    assert "from m1_parser" not in detail
    assert "main(port=" not in detail
