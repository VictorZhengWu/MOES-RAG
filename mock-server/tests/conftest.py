"""
Shared fixtures for mock server tests.

WHY: Every endpoint test needs an HTTP client pointed at the mock
server. Using FastAPI's TestClient approach via httpx ASGITransport
avoids spinning up a real HTTP server, making tests fast and
deterministic — no port conflicts, no process management.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from mock_server.app import create_app
from mock_server.config import MockServerConfig


@pytest.fixture
def config():
    """Test configuration with permissive CORS."""
    return MockServerConfig(cors_origins=["*"])


@pytest.fixture
def app(config):
    """Create a fresh app instance for each test.

    WHY: Fresh instances prevent test order dependencies.
    """
    return create_app(config)


@pytest.fixture
async def client(app):
    """Async HTTP test client bound to the mock server ASGI app.

    WHY: httpx AsyncClient with ASGITransport tests the full
    request/response cycle (routing, middleware, serialization)
    without network overhead. Every test gets a clean transport.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
