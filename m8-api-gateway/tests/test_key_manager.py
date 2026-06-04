"""Tests for M8 API Key Manager.

WHAT: Test suite covering the full API key lifecycle: generate, validate,
      revoke, and list. Uses a temporary SQLite database for each test
      to ensure isolation.
WHY: Each test must be independent and not depend on shared database state.
     tempfile.mkdtemp ensures cleanup even on test failure.
"""

import asyncio
import tempfile
import os

import pytest

from m8_gateway.auth.key_manager import KeyManager, APIKey


# ---------------------------------------------------------------------------
# Helper: create a KeyManager with a temporary database
# ---------------------------------------------------------------------------

def _make_manager() -> KeyManager:
    """Create a KeyManager backed by a temporary SQLite database.

    WHAT: Returns a KeyManager instance pointing to a unique temp db file.
    WHY: Isolates each test so they don't interfere with each other.
    """
    tmpdir = tempfile.mkdtemp(prefix="m8_test_")
    db_path = os.path.join(tmpdir, "test_keys.db")
    return KeyManager(db_path)


# ---------------------------------------------------------------------------
# Test 1: generate + validate — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_and_validate():
    """Generate an API key, then validate it and check returned metadata.

    WHAT: Calls generate_key() then validate_key() with the returned raw key.
          Verifies the returned APIKey object has the correct user_id and tier.
    WHY: This is the core lifecycle: a generated key must be immediately
         usable and return correct metadata on validation.
    """
    manager = _make_manager()

    # Generate a key for a test user with "pro" tier
    raw_key = await manager.generate_key(user_id="user-001", tier="pro")

    # Verify raw key format: "sk-m8-{16 hex chars}"
    assert raw_key.startswith("sk-m8-"), f"Unexpected key prefix: {raw_key[:10]}"
    # sk-m8- + 16 hex chars = sk-m8-xxxxxxxxxxxxxxxx
    hex_part = raw_key[6:]  # strip "sk-m8-"
    assert len(hex_part) == 16, f"Expected 16 hex chars, got {len(hex_part)}: {hex_part}"
    assert all(c in "0123456789abcdef" for c in hex_part), \
        f"Non-hex characters in key: {hex_part}"

    # Validate the raw key
    api_key = await manager.validate_key(raw_key)

    # Verify the returned APIKey object
    assert api_key is not None, "Valid key returned None from validate_key"
    assert isinstance(api_key, APIKey), f"Expected APIKey, got {type(api_key)}"
    assert api_key.user_id == "user-001", \
        f"Expected user_id 'user-001', got '{api_key.user_id}'"
    assert api_key.tier == "pro", \
        f"Expected tier 'pro', got '{api_key.tier}'"
    assert api_key.is_active is True, "Newly generated key should be active"
    assert api_key.key_prefix == raw_key[:10], \
        f"key_prefix mismatch: {api_key.key_prefix} vs {raw_key[:10]}"


# ---------------------------------------------------------------------------
# Test 2: validate an invalid / random key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_invalid_key():
    """Pass a random string (not a real key) to validate_key and expect None.

    WHAT: Calls validate_key() with a string that was never generated.
          Expects None as the return value.
    WHY: The system must silently reject invalid keys without leaking
         information about which keys exist.
    """
    manager = _make_manager()

    # Try to validate a random string that looks like a key but isn't in the DB
    result = await manager.validate_key("sk-m8-deadbeefcafebabe")

    assert result is None, (
        "Random key should return None from validate_key, "
        f"got {result}"
    )

    # Also test with completely malformed input
    result2 = await manager.validate_key("not-a-key-at-all")
    assert result2 is None, "Malformed input should return None"


# ---------------------------------------------------------------------------
# Test 3: revoke a key, then validate it
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoke_key():
    """Generate a key, revoke it by prefix, then verify validate returns None.

    WHAT: Generates a key, calls revoke_key() with the key prefix,
          then attempts to validate the original raw key. Expects None.
    WHY: Revocation must immediately invalidate the key so that revoked
         credentials cannot be used for further API access.
    """
    manager = _make_manager()

    # Generate a key
    raw_key = await manager.generate_key(user_id="user-002", tier="basic")
    key_prefix = raw_key[:10]  # "sk-m8-xxxx"

    # Verify it works before revocation
    before = await manager.validate_key(raw_key)
    assert before is not None, "Key should be valid before revocation"

    # Revoke the key by its prefix
    revoked = await manager.revoke_key(key_prefix)
    assert revoked is True, "revoke_key should return True when key found"

    # Verify it no longer validates
    after = await manager.validate_key(raw_key)
    assert after is None, (
        "Revoked key should return None from validate_key, "
        f"got {after}"
    )

    # Revoking an already-revoked key should return False
    double_revoke = await manager.revoke_key(key_prefix)
    assert double_revoke is False, (
        "Revoking an already-revoked key should return False"
    )


# ---------------------------------------------------------------------------
# Test 4: list keys for a user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_keys():
    """Generate 2 keys for the same user, then verify list_keys returns 2 entries.

    WHAT: Generates two keys for "user-003", then calls list_keys(user_id="user-003").
          Checks that the returned list has 2 entries, key_prefixes are shown,
          and full keys are never exposed.
    WHY: Administrators need to see which keys exist for a user without ever
         seeing the full secret key material.
    """
    manager = _make_manager()

    # Generate 2 keys for the same user
    raw_key_1 = await manager.generate_key(user_id="user-003", tier="basic")
    raw_key_2 = await manager.generate_key(user_id="user-003", tier="pro")

    # List keys for this user
    keys = await manager.list_keys(user_id="user-003")

    assert len(keys) == 2, f"Expected 2 keys, got {len(keys)}"

    # Verify each entry has the expected fields
    for entry in keys:
        assert "key_prefix" in entry, f"Missing key_prefix in {entry}"
        assert "user_id" in entry, f"Missing user_id in {entry}"
        assert "tier" in entry, f"Missing tier in {entry}"
        assert "created_at" in entry, f"Missing created_at in {entry}"
        assert "is_active" in entry, f"Missing is_active in {entry}"
        # Full key must never appear in list output
        assert "key_hash" not in entry, (
            "key_hash must NOT appear in list_keys output"
        )
        assert entry["user_id"] == "user-003"

    # Verify key prefixes match the generated keys
    prefixes = {entry["key_prefix"] for entry in keys}
    assert raw_key_1[:10] in prefixes, "key_prefix for first key not found"
    assert raw_key_2[:10] in prefixes, "key_prefix for second key not found"

    # List all keys (no user_id filter) should also include these
    all_keys = await manager.list_keys()
    assert len(all_keys) >= 2, (
        f"list_keys() without user_id should return at least 2 keys, "
        f"got {len(all_keys)}"
    )

    # Verify full keys are never in list output
    for entry in all_keys:
        assert "key_hash" not in entry, \
            "key_hash must NOT appear in list_keys output"


# ---------------------------------------------------------------------------
# Test 5: touch_key updates last_used_at
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_touch_key():
    """Generate a key, call touch_key(), then verify last_used_at is updated.

    WHAT: Generates a key, checks last_used_at is None initially, then calls
          touch_key() and verifies the timestamp is set.
    WHY: Tracking last usage is important for key rotation policies and
         identifying stale keys that should be revoked.
    """
    manager = _make_manager()

    raw_key = await manager.generate_key(user_id="user-004", tier="basic")
    key_prefix = raw_key[:10]

    # Before touch, last_used_at should be None
    keys_before = await manager.list_keys(user_id="user-004")
    assert len(keys_before) == 1
    assert keys_before[0]["last_used_at"] is None, \
        "New key should have last_used_at=None before first use"

    # Touch the key
    await manager.touch_key(key_prefix)

    # After touch, last_used_at should be set
    keys_after = await manager.list_keys(user_id="user-004")
    assert len(keys_after) == 1
    assert keys_after[0]["last_used_at"] is not None, \
        "last_used_at should be set after touch_key()"
    assert isinstance(keys_after[0]["last_used_at"], float), \
        f"last_used_at should be float, got {type(keys_after[0]['last_used_at'])}"
