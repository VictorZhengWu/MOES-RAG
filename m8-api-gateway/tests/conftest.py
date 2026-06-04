"""Shared test fixtures for M8 API Gateway route tests.

WHAT: Provides a pytest fixture that creates a fully configured FastAPI
      test application with in-memory components (KeyManager, RateLimiter)
      and a pre-generated API key for authentication-dependent tests.

WHY: Each test needs an isolated FastAPI app with its own KeyManager
     database and RateLimiter state to prevent cross-test contamination.
     The fixture handles setup (temp dir, config, app creation, key
     generation) and cleanup (temp dir removal) automatically.
"""

import os
import shutil
import sys
import tempfile

import pytest

# Ensure the worktree root is on sys.path so that 'contracts' is importable
# from within the m8-api-gateway subdirectory.
# The editable install only maps subpackages, not the top-level contracts
# package, so we need to add the worktree root explicitly for tests.
_WORKTREE_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _WORKTREE_ROOT not in sys.path:
    sys.path.insert(0, _WORKTREE_ROOT)


@pytest.fixture
async def test_app():
    """Create a test FastAPI app with in-memory components.

    WHAT: Sets up an isolated FastAPI application with:
          - A temporary SQLite database for KeyManager
          - A GatewayConfig with personal mode rate limits
          - A pre-generated API key (tier: "pro") for authentication
          - RateLimiter initialized with config rate limits
          - QA Engine set to None (no LLM backend needed for auth tests)

    WHY: Tests that need authenticated requests can use the returned
         raw_key directly in their Authorization headers. The in-memory
         components ensure test isolation — no cross-test contamination,
         no leftover files.

    Yields:
        Tuple of (FastAPI app, raw API key string, GatewayConfig).
    """
    from m8_gateway.core.app import create_app
    from m8_gateway.core.config import GatewayConfig

    # Use mkdtemp for a unique temporary directory per test run.
    # This ensures the SQLite database is isolated and cleaned up
    # even if the test fails (shutil.rmtree in teardown handles this).
    tmpdir: str = tempfile.mkdtemp(prefix="m8_test_routes_")
    db_path: str = os.path.join(tmpdir, "test.db")

    # Create config with in-memory-friendly defaults
    config = GatewayConfig(
        db_path=db_path,
        deployment_mode="personal",
    )

    # Create the FastAPI app using the factory.
    # The startup event initializes KeyManager, RateLimiter, and QA Engine.
    app = create_app(config)

    # Trigger startup manually to populate app.state before tests run.
    # (FastAPI TestClient would trigger this, but we want the state ready
    # before the client starts making requests.)
    await app.router.startup()

    # Generate a test API key with "pro" tier (higher rate limit for tests)
    raw_key: str = await app.state.key_manager.generate_key(
        user_id="test-user",
        tier="pro",
    )

    yield app, raw_key, config

    # Trigger shutdown to clean up resources
    await app.router.shutdown()

    # Clean up the temporary directory and all its contents
    shutil.rmtree(tmpdir, ignore_errors=True)
