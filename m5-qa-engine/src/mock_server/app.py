"""
Mock Server FastAPI application factory.

WHY: The app must be created via a factory function rather than a
module-level global so that tests can inject custom config and
the production entrypoint can use defaults. Factory pattern allows
tests to create fresh app instances with test-specific config
(e.g., different CORS origins) without mutating global state.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import MockServerConfig
from .routes_chat import router as chat_router
from .routes_conversations import router as conversations_router
from .routes_models import router as models_router
from .routes_admin import router as admin_router


def create_app(config: MockServerConfig | None = None) -> FastAPI:
    """
    Create and configure the Mock Server FastAPI application.

    Args:
        config: Server configuration. Uses MockServerConfig() defaults if None.

    Returns:
        A fully configured FastAPI application ready to serve.
    """
    if config is None:
        config = MockServerConfig()

    app = FastAPI(
        title="Marine & Offshore Expert System — Mock Server",
        description=(
            "Mock API server for Phase 1 frontend development. "
            "All responses are fake data matching contracts/ schemas. "
            "WILL BE REPLACED by M5 real implementation in Phase 2."
        ),
        version="0.1.0-mock",
    )

    # CORS: allow frontend dev servers to call the mock API
    # Without this, browser Same-Origin Policy blocks all requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register all route modules
    app.include_router(chat_router)
    app.include_router(conversations_router)
    app.include_router(models_router)
    app.include_router(admin_router)

    return app


# Module-level app instance for uvicorn
# Usage: pip install -e m5-qa-engine/ && python -c
#   "from mock_server.app import app; import uvicorn; uvicorn.run(app)"
app = create_app()
