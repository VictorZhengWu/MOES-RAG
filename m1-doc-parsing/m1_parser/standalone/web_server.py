# -*- coding: utf-8 -*-
"""
Standalone FastAPI web server for M1 document parsing engine.

Provides a lightweight HTTP interface for document parsing without
requiring the full M6/M7 stack. Single-file HTML UI is served from
the same process.

Endpoints:
  - GET  /            -- API status and hardware info
  - POST /upload      -- upload a document file (placeholder)
  - POST /parse       -- parse a previously uploaded file (placeholder)
  - GET  /download/{id} -- download parsed output (placeholder)

WHY FastAPI: async-native, auto-generated OpenAPI docs (/docs), low
learning curve, and the same framework used by M8 API Gateway.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI import guard
# WHY try/except: FastAPI and uvicorn are optional dependencies. In a
# headless CI/testing environment, only the CLI may be installed. This
# guard allows the module to be imported without FastAPI present, and
# fails with a clear error message only when the server is actually started.
# ---------------------------------------------------------------------------
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]
    HTMLResponse = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]


# ===========================================================================
# Application factory
# ===========================================================================


def create_app() -> "FastAPI":  # type: ignore[valid-type]
    """
    Build and configure the FastAPI application instance.

    WHAT: creates the FastAPI app with title, version, and routes.

    WHY factory function: allows the test suite to create fresh app
    instances without global state contamination. Also enables
    configuration injection in the future (e.g., upload directory,
    max file size).

    Returns:
        A configured FastAPI application instance.

    Raises:
        ImportError: If FastAPI is not installed.
    """
    # WHY check inside the factory: importing the module is fine, but
    # creating the app should fail loudly if FastAPI is missing.
    if FastAPI is None:  # pragma: no cover
        raise ImportError(
            "FastAPI is not installed. Install it with: pip install fastapi uvicorn"
        )

    app = FastAPI(
        title="Marine & Offshore Expert System -- M1 Document Parsing Engine",
        version="0.1.0",
        description=(
            "Standalone document parsing service. Upload documents, "
            "trigger parsing, and download structured Markdown output."
        ),
    )

    # -- Register routes --
    _register_routes(app)

    return app


def _register_routes(app: "FastAPI") -> None:  # type: ignore[valid-type]
    """
    Register all API routes on the application.

    WHAT: attaches endpoint handlers to the FastAPI app instance.

    WHY separate from create_app: keeps route registration in one place,
    making it easy to add/remove endpoints as the module grows.
    """

    @app.get("/", response_model=dict)
    async def root_status() -> dict:
        """
        Root endpoint -- returns server status and hardware information.

        WHAT: a lightweight health/status check that summarizes what the
        server can do, what hardware it's running on, and when it started.

        WHY: frontend clients and monitoring tools need a fast, no-side-
        effect endpoint to check server availability before attempting
        heavier operations like file uploads.
        """
        # -- Detect hardware (cached import from core config) --
        # WHY lazy import: detect_hardware imports torch, which is heavy.
        # Importing only when the endpoint is hit keeps cold-start fast.
        try:
            from m1_parser.core.config import detect_hardware
            hw = detect_hardware()
            hardware_info = {
                "gpu": hw.gpu,
                "vram_gb": round(hw.vram_gb, 1),
                "recommended_backend": hw.recommended_backend,
                "recommended_ocr": hw.recommended_ocr,
                "can_use_vllm": hw.can_use_vllm,
            }
        except Exception:
            # hardware detection failed (no torch, no GPU) -- report gracefully
            hardware_info = {
                "gpu": False,
                "vram_gb": 0.0,
                "recommended_backend": "docling_standard",
                "recommended_ocr": "easyocr",
                "can_use_vllm": False,
            }

        return {
            "service": "m1-doc-parsing",
            "status": "running",
            "version": "0.1.0",
            "started_at": _start_time.isoformat() if _start_time else None,
            "hardware": hardware_info,
            "endpoints": {
                "GET /": "This status page",
                "POST /upload": "Upload a document file (placeholder)",
                "POST /parse": "Parse an uploaded document (placeholder)",
                "GET /download/{doc_id}": "Download parsed output (placeholder)",
                "GET /docs": "OpenAPI documentation (Swagger UI)",
            },
        }

    @app.post("/upload")
    async def upload_document() -> dict:
        """
        Placeholder -- upload a document file for later parsing.

        WHAT: accepts a file upload via multipart/form-data and returns
        a file_id that can be used with the /parse endpoint.

        WHY placeholder: implemented as part of the full M1+Web UI
        integration. This endpoint ensures the URL structure is stable
        for frontend development.
        """
        return {
            "status": "not_implemented",
            "message": "File upload endpoint is not yet implemented.",
            "available_in": "00060-11 phase 2",
        }

    @app.post("/parse")
    async def parse_document() -> dict:
        """
        Placeholder -- trigger parsing for an uploaded document.

        WHAT: accepts a file_id and parse options, then runs the full
        conversion pipeline.

        WHY placeholder: see /upload.
        """
        return {
            "status": "not_implemented",
            "message": "Parse endpoint is not yet implemented.",
            "available_in": "00060-11 phase 2",
        }

    @app.get("/download/{doc_id}")
    async def download_result(doc_id: str) -> dict:
        """
        Placeholder -- download parsed output for a document.

        WHAT: returns the Markdown/JSON/HTML output for a previously
        parsed document, identified by its doc_id.

        WHY placeholder: see /upload.
        """
        return {
            "status": "not_implemented",
            "message": "Download endpoint is not yet implemented.",
            "doc_id": doc_id,
            "available_in": "00060-11 phase 2",
        }


# ===========================================================================
# Module-level state
# ===========================================================================

_start_time: datetime | None = None


# ===========================================================================
# Entry point
# ===========================================================================


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    """
    Start the standalone web server.

    WHAT: creates the FastAPI app and runs it with uvicorn on the
    specified host/port.

    WHY function entry point: allows both direct execution
    (``python -m m1_parser.standalone.web_server``) and programmatic
    use in integration tests.

    Args:
        host: Bind address (default: 0.0.0.0 for all interfaces).
        port: TCP port (default: 8000).
    """
    global _start_time
    _start_time = datetime.now(timezone.utc)

    try:
        import uvicorn
    except ImportError:  # pragma: no cover
        print(
            "Error: uvicorn is not installed. "
            "Install it with: pip install uvicorn",
            file=sys.stderr,
        )
        sys.exit(1)

    app = create_app()

    print("=" * 60)
    print("  M1 Document Parsing Engine -- Standalone Web Server")
    print(f"  Listening on http://{host}:{port}")
    print(f"  API docs:    http://{host}:{port}/docs")
    print(f"  Status:      http://{host}:{port}/")
    print("=" * 60)

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
