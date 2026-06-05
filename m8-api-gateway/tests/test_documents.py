"""
Tests for M8 document upload route.

WHAT: Verify the POST /api/v1/documents/upload endpoint:
  - Requires authentication (401 without key)
  - Validates file is present
  - Returns 503 when M1 is not running
"""

import pytest
from fastapi.testclient import TestClient


def test_upload_requires_auth(test_app):
    """POST /api/v1/documents/upload without auth → 401."""
    app, _, _ = test_app
    client = TestClient(app)
    resp = client.post("/api/v1/documents/upload")
    assert resp.status_code == 401


def test_upload_without_file_requires_auth(test_app):
    """POST without file → 401 (auth check comes first)."""
    app, _, _ = test_app
    client = TestClient(app)
    resp = client.post("/api/v1/documents/upload", data={"output_dir": "./output"})
    assert resp.status_code == 401


def test_upload_m1_unavailable(test_app):
    """POST with valid auth but M1 not running → 503."""
    app, api_key, _ = test_app
    client = TestClient(app)
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
        data={"output_dir": "./output"},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    # 503 = M1 not running (ConnectionError) or 502 = M1 returned error
    assert resp.status_code in (502, 503)
