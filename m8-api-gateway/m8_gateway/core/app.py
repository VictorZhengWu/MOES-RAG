"""FastAPI application factory for M8 API Gateway.

WHAT: Factory function that builds the FastAPI app with proper
      routes, middleware, and lifecycle handlers. Wires up all
      application state (KeyManager, RateLimiter, QA Engine)
      into app.state for dependency injection.

WHY: Factory pattern allows test configuration injection and
     multiple instances for different deployment scenarios.
     Event handlers manage startup/shutdown correctly.
     Using app.state rather than module-level globals ensures
     test isolation — each TestClient can have its own instances.
"""

from fastapi import FastAPI

from m8_gateway.auth.key_manager import KeyManager
from m8_gateway.core.config import GatewayConfig
from m8_gateway.rate_limit.limiter import RateLimiter
from m8_gateway.routes import chat, keys, models


def create_app(config: GatewayConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    WHAT: Factory function that builds the FastAPI app with proper
          routes, middleware, and lifecycle handlers. Injects all
          runtime components into app.state for dependency injection.

    WHY: Factory pattern allows test configuration injection and
         multiple instances for different deployment scenarios.
         Each component (KeyManager, RateLimiter, QA Engine) is
         stored in app.state so that:
         - Route handlers can access them via request.app.state
         - Tests can override them per-test-case
         - No global singletons are needed

    State keys set on the app:
        app.state.config      — GatewayConfig instance
        app.state.key_manager — KeyManager(db_path)
        app.state.limiter     — RateLimiter(rate_limits)
        app.state.qa_engine   — QA Engine instance or None (lazy init)

    Args:
        config: Optional GatewayConfig instance. If None, uses defaults.

    Returns:
        Configured FastAPI application instance with all routers registered.
    """
    cfg: GatewayConfig = config or GatewayConfig()

    app = FastAPI(
        title="Marine & Offshore Expert System API",
        version="0.1.0",
        description="OpenAI-compatible API for ship and offshore engineering Q&A",
    )

    # ------------------------------------------------------------------
    # Lifecycle: startup
    # ------------------------------------------------------------------

    @app.on_event("startup")
    async def startup():
        """Initialize app state and resources on server startup.

        WHAT: Wires all runtime components into app.state so that
              route handlers and middleware dependencies can access
              them via request.app.state.

        WHY: FastAPI's lifespan events run before any requests;
             this is the correct place to wire configuration into
             app.state. KeyManager creates tables lazily on first
             use (no explicit DB init needed here). The QA Engine
             is set to None for lazy initialization — it requires
             a configured LLM backend which may not be available
             at gateway startup.
        """
        # Store config for reference by health endpoint
        app.state.config = cfg

        # Initialize the API key manager with the configured database path.
        # Tables are created lazily on first generate_key/validate_key call
        # via KeyManager._ensure_table().
        app.state.key_manager = KeyManager(cfg.db_path)

        # Initialize the rate limiter with per-tier limits from config.
        # In-memory implementation; will be replaced with Redis in SaaS phase.
        app.state.limiter = RateLimiter(cfg.rate_limits)

        # QA Engine is lazy-initialized. It requires an LLM backend config
        # which is set up separately via the admin portal (M7).
        # Set to None here; routes check for None and return 500 if not ready.
        #
        # INITIALIZATION: The QA Engine must be initialized at runtime via one
        # of these methods:
        # 1. Direct injection: app.state.qa_engine = QAEngine(config)
        # 2. Admin endpoint: POST /admin/initialize-engine (if implemented)
        # 3. Configuration-based: Load from deploy.yaml at startup
        #
        # For production deployments, the initialization should happen during
        # the startup phase after the LLM backend configuration is loaded.
        app.state.qa_engine = None

    # ------------------------------------------------------------------
    # Lifecycle: shutdown
    # ------------------------------------------------------------------

    @app.on_event("shutdown")
    async def shutdown():
        """Clean up resources on server shutdown.

        WHY: Ensures connections are released gracefully.
             Individual modules (KeyManager, RateLimiter) handle
             their own close methods. The KeyManager uses short-lived
             aiosqlite connections per operation, so no persistent
             connection needs closing.
        """
        pass  # Cleanup handled by module close methods

    # ------------------------------------------------------------------
    # Register routers
    # ------------------------------------------------------------------

    # OpenAI-compatible chat completions endpoint
    app.include_router(chat.router)

    # OpenAI-compatible models listing endpoint
    app.include_router(models.router)

    # Admin API key management endpoints
    app.include_router(keys.router)

    # Conversation management endpoints (M5-backed, replaces Mock Server)
    from m8_gateway.routes import conversations
    app.include_router(conversations.router)

    # Document upload endpoint (proxies to M1 /parse)
    from m8_gateway.routes import documents
    app.include_router(documents.router)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    @app.get("/health")
    async def health():
        """Health check endpoint.

        WHAT: Reports service status, deployment mode, and QA Engine
              availability. Ultra-lightweight — no DB queries.

        WHY: Load balancers and monitoring tools need a lightweight
             endpoint to verify the gateway is running. Returns 200
             even if the QA Engine is not yet initialized (the gateway
             itself is healthy — the engine is a downstream dependency).
        """
        qa_ready: bool = app.state.qa_engine is not None
        return {
            "status": "ok",
            "deployment_mode": cfg.deployment_mode,
            "qa_engine_ready": qa_ready,
        }

    return app
