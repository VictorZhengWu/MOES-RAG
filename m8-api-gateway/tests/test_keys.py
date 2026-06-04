"""Tests for the M8 admin API key management routes.

WHAT: Verifies the admin endpoints for API key lifecycle: create (POST)
      and revoke (DELETE). Creating a key returns the raw key exactly
      once; revoking a key makes it immediately invalid for auth.
WHY: Key management is the security foundation of the API gateway.
     If key creation is broken, users can't authenticate. If revocation
     doesn't work, compromised keys remain usable indefinitely.
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_create_key(test_app):
    """POST /admin/keys creates a new key and returns raw key + prefix.

    WHAT: Sends a POST to /admin/keys with user_id and tier, verifies
          the response contains a valid-looking API key (sk-m8-... format)
          and matching prefix.

    WHY: The raw key is returned exactly once during creation. If the
         format is wrong or the prefix doesn't match, the caller cannot
         use the key to authenticate.
    """
    app, raw_key, config = test_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.post(
            "/admin/keys",
            json={"user_id": "test-user-2", "tier": "basic"},
        )

        # Expect 200 — key creation should succeed
        assert response.status_code == 200, (
            f"Expected 200 for key creation, got {response.status_code}: {response.text}"
        )

        body = response.json()

        # Verify the raw key is present and has the correct format
        assert "key" in body, (
            f"Response should include 'key' field, got keys: {list(body.keys())}"
        )
        assert body["key"].startswith("sk-m8-"), (
            f"API key should start with 'sk-m8-', got: {body['key'][:20]}"
        )
        # sk-m8- + 16 hex chars
        hex_part = body["key"][6:]
        assert len(hex_part) == 16, (
            f"Expected 16 hex chars after 'sk-m8-', got {len(hex_part)}: {hex_part}"
        )

        # Verify the prefix matches the first 10 chars of the key
        assert "prefix" in body, (
            f"Response should include 'prefix' field, got keys: {list(body.keys())}"
        )
        assert body["prefix"] == body["key"][:10], (
            f"Prefix '{body['prefix']}' should match first 10 chars of key"
        )

        # Verify tier is returned correctly
        assert body["tier"] == "basic", (
            f"Expected tier 'basic', got '{body['tier']}'"
        )


@pytest.mark.asyncio
async def test_revoke_key(test_app):
    """Create a key, revoke it, then verify it can't authenticate.

    WHAT: Generates a new key via POST /admin/keys, revokes it via
          DELETE /admin/keys/{prefix}, then attempts to use the revoked
          key to access GET /v1/models. Expects 401.

    WHY: Key revocation must take effect immediately. A delay between
         revocation and enforcement would allow compromised keys to
         continue being used, creating a security window. This test
         verifies instant revocation.
    """
    app, existing_key, config = test_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # Step 1: Create a new key
        create_resp = await client.post(
            "/admin/keys",
            json={"user_id": "test-revoke-user", "tier": "basic"},
        )
        assert create_resp.status_code == 200, (
            f"Key creation failed: {create_resp.status_code} {create_resp.text}"
        )
        new_key = create_resp.json()["key"]
        new_prefix = create_resp.json()["prefix"]

        # Step 2: Verify the key works for authentication
        models_resp = await client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {new_key}"},
        )
        assert models_resp.status_code == 200, (
            f"New key should authenticate successfully, got {models_resp.status_code}"
        )

        # Step 3: Revoke the key
        revoke_resp = await client.delete(f"/admin/keys/{new_prefix}")
        assert revoke_resp.status_code == 200, (
            f"Key revocation failed: {revoke_resp.status_code} {revoke_resp.text}"
        )
        revoke_body = revoke_resp.json()
        assert revoke_body["status"] == "revoked", (
            f"Expected status 'revoked', got '{revoke_body.get('status')}'"
        )
        assert revoke_body["key_prefix"] == new_prefix, (
            f"Expected key_prefix '{new_prefix}', got '{revoke_body.get('key_prefix')}'"
        )

        # Step 4: Verify the revoked key is rejected (returns 401)
        after_revoke_resp = await client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {new_key}"},
        )
        assert after_revoke_resp.status_code == 401, (
            f"Revoked key should be rejected (401), got {after_revoke_resp.status_code}"
        )

        # Step 5: Verify existing (non-revoked) key still works
        still_works_resp = await client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {existing_key}"},
        )
        assert still_works_resp.status_code == 200, (
            f"Existing key should still work after revoking a different key, "
            f"got {still_works_resp.status_code}"
        )
