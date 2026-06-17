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
from m8_gateway.rate_limit import create_rate_limiter
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
        max_request_size=10 * 1024 * 1024,  # 10MB limit (prevents DoS)
    )

    # ------------------------------------------------------------------
    # CORS — allow the M6/M7 browser frontends to call the API.
    # WHAT: Adds Access-Control-Allow-Origin for the configured frontend
    #       origins so browsers can fetch across ports (3000/3001 -> 18000).
    # WHY:  Without CORS, every cross-origin API call from the Next.js
    #       portals is blocked by the browser's same-origin policy.
    # ------------------------------------------------------------------
    import os as _cors_os
    from fastapi.middleware.cors import CORSMiddleware
    _default_cors = (
        "http://localhost:3000,http://localhost:3001,"
        "http://localhost:4000,http://localhost:4001,"
        "http://127.0.0.1:3000,http://127.0.0.1:3001,"
        "http://127.0.0.1:4000,http://127.0.0.1:4001"
    )
    _cors_origins = [
        o.strip() for o in
        _cors_os.environ.get("M8_CORS_ORIGINS", _default_cors).split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Security headers middleware
    # ------------------------------------------------------------------

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Allow Swagger UI to load CDN assets + inline scripts.
        # API responses (JSON) are unaffected since they carry no active content.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "connect-src 'self'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

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

        # ── First-run admin bootstrap ──────────────────────────────────
        # Creates a default admin user + key if the users table is empty.
        # Idempotent; failure is non-fatal (operator can create admin
        # manually). See m8_gateway.core.bootstrap for details.
        try:
            from m8_gateway.core.bootstrap import bootstrap_admin_if_needed
            await bootstrap_admin_if_needed(cfg.db_path)
        except Exception as _bs_err:
            logging.getLogger("m8_gateway").error(
                "bootstrap failed (non-fatal): %s", _bs_err, exc_info=True
            )

        # Initialize the rate limiter via factory.
        # Auto-selects InMemoryRateLimiter or RedisRateLimiter based on
        # config.rate_limit_backend (auto-detected from deployment_mode).
        app.state.limiter = create_rate_limiter(cfg)

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

        # Initialize Project Manager (Phase 4-B) — always available
        from m5_qa.project.manager import ProjectManager
        app.state.project_manager = ProjectManager(config.m5_db_path)
        await app.state.project_manager.initialize()

        # Set restrictive DB file permissions (owner-only, prevents data leaks)
        import os as _os
        db_path = cfg.db_path
        _os.makedirs(_os.path.dirname(db_path) or '.', exist_ok=True)
        if _os.path.exists(db_path):
            _os.chmod(db_path, 0o600)

    # ------------------------------------------------------------------
    # Lifecycle: shutdown
    # ------------------------------------------------------------------

    @app.on_event("shutdown")
    async def shutdown():
        """Clean up resources on server shutdown.

        WHAT: Calls close() on the rate limiter to release Redis
              connection pools (if any). InMemoryRateLimiter.close()
              is a no-op.

        WHY: Redis connection pool must be explicitly closed to release
             TCP connections gracefully. Without this, Redis server
             accumulates dead connections until timeout.
        """
        limiter = app.state.limiter
        if limiter is not None:
            limiter.close()

    # ------------------------------------------------------------------
    # Register routers
    # ------------------------------------------------------------------

    # Authentication endpoints (register/login — no auth required)
    from m8_gateway.routes import auth
    app.include_router(auth.router)

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

    # Admin config endpoints (runtime M5 config update)
    from m8_gateway.routes import admin
    app.include_router(admin.router)

    # Share, pin, account deletion, projects (Phase 3 extras)
    from m8_gateway.routes import extras
    app.include_router(extras.router)

    # Deep Research endpoint (Phase 4-A)
    from m8_gateway.routes import research
    app.include_router(research.router)

    # Projects endpoints (Phase 4-B)
    from m8_gateway.routes import projects
    app.include_router(projects.router)

    # ------------------------------------------------------------------
    # Global error handler — catches all unhandled exceptions
    # ------------------------------------------------------------------

    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Return JSON error instead of HTML traceback for unhandled errors."""
        import logging, re, traceback
        tb = traceback.format_exc()
        # Sanitize: redact API keys and tokens from error logs
        tb = re.sub(r'sk-m8-[a-f0-9]+', '[REDACTED_KEY]', tb)
        tb = re.sub(r'token=[a-zA-Z0-9_-]+', 'token=[REDACTED]', tb)
        logging.getLogger("m8_gateway").error(
            "unhandled_error path=%s error=%s\n%s",
            request.url.path, exc, tb,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if cfg.deployment_mode == "personal" else "Please contact support.",
            },
        )

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
