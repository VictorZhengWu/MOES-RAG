"""FastAPI application factory for M8 API Gateway.

WHAT: Factory function that builds the FastAPI app with proper
      routes, middleware, and lifecycle handlers.
WHY: Factory pattern allows test configuration injection and
     multiple instances for different deployment scenarios.
     Event handlers manage startup/shutdown correctly.
"""

from fastapi import FastAPI
from m8_gateway.core.config import GatewayConfig


def create_app(config: GatewayConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    WHAT: Factory function that builds the FastAPI app with proper
          routes, middleware, and lifecycle handlers.

    WHY: Factory pattern allows test configuration injection and
         multiple instances for different deployment scenarios.

    Args:
        config: Optional GatewayConfig instance. If None, uses defaults.

    Returns:
        Configured FastAPI application instance.
    """
    cfg = config or GatewayConfig()

    app = FastAPI(
        title="Marine & Offshore Expert System API",
        version="0.1.0",
        description="OpenAI-compatible API for ship and offshore engineering Q&A",
    )

    @app.on_event("startup")
    async def startup():
        """Initialize app state and resources on server startup.

        WHY: FastAPI's lifespan events run before any requests;
             this is the correct place to wire configuration into
             app.state so route handlers can access it.
        """
        app.state.config = cfg
        # DB tables will be created by KeyManager on first use

    @app.on_event("shutdown")
    async def shutdown():
        """Clean up resources on server shutdown.

        WHY: Ensures connections are released gracefully.
             Individual modules (KeyManager, RateLimiter) handle
             their own close methods.
        """
        pass  # Cleanup handled by module close methods

    @app.get("/health")
    async def health():
        """Health check endpoint.

        WHAT: Reports service status and deployment mode.
        WHY: Load balancers and monitoring tools need a lightweight
             endpoint to verify the gateway is running.
        """
        return {"status": "ok", "deployment_mode": cfg.deployment_mode}

    return app
