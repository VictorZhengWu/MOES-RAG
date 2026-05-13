"""
Mock Server configuration.

WHY: Configuration values (port, host, CORS origins) must be
injectable rather than hardcoded. Tests need to override the
port and CORS settings to avoid conflicts with other services
and to test without real cross-origin constraints.

Defaults are for local development — a developer runs
python -c "from mock_server.app import app; import uvicorn; uvicorn.run(app)"
and opens http://localhost:8000.
"""

from dataclasses import dataclass, field


@dataclass
class MockServerConfig:
    """
    Configuration for the Mock Server.

    All values have sensible defaults for local development.
    Override via constructor arguments in tests.
    """
    host: str = "127.0.0.1"
    port: int = 8000
    # CORS origins that the frontend dev servers use
    cors_origins: list[str] = field(default_factory=lambda: [
        "http://localhost:3000",   # M6 Next.js dev server
        "http://localhost:3001",   # M7 Next.js dev server
        "http://localhost:5173",   # Vite dev server (if using Vue)
    ])
    # Simulated latency range for realistic UX testing (milliseconds)
    min_latency_ms: int = 200
    max_latency_ms: int = 800
