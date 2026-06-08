"""
M8 API Gateway — Document Upload Route.

WHAT: Proxies file upload from M6 frontend to M1's document parsing engine.
      Accepts multipart/form-data, forwards to M1 /parse, returns parsed result
      with m2_status confirming chunks were stored for M3 retrieval.

WHY: M6 frontend has drag-and-drop file upload UI but needs a backend endpoint.
     M1's web_server runs on an internal port; M8 proxies the request so
     M6 only needs to know M8's port (8000). Module independence: M8 does not
     import M1 directly — uses HTTP to avoid docling/OCR dependency.
"""

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
import httpx

from m8_gateway.auth.key_manager import APIKey
from m8_gateway.auth.middleware import get_api_key

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# ---------------------------------------------------------------------------
# Security: file upload constraints
# ---------------------------------------------------------------------------

# Maximum allowed file size (200MB) — prevents memory-exhaustion DoS attacks.
# Marine engineering documents (specs, drawings) rarely exceed 100MB; 200MB
# provides generous headroom while capping worst-case resource consumption.
MAX_FILE_SIZE: int = 200 * 1024 * 1024  # 200 MB

# Allowed file extensions — defence-in-depth before M1's own format validation.
# Only document formats that M1 can actually parse are permitted. This blocks
# executables (.exe, .bat), archives (.zip, .7z), and other non-document files
# at the gateway layer before they reach downstream services.
ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".html", ".htm"}

# M1 web_server address — configured via environment variable with a sensible
# default. The port comes from the GatewayConfig in deploy.yaml when running
# in production; the env var override exists for development and testing.
M1_PARSE_URL: str = os.environ.get(
    "M1_PARSE_URL",
    "http://127.0.0.1:8007/parse",
)

# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    output_dir: str = Form(default="./output"),
    parse_backend: str = Form(default="docling"),
    api_key: APIKey = Depends(get_api_key),
):
    """
    POST /api/v1/documents/upload — Upload and parse a document.

    WHAT:
      1. Validates file type (extension whitelist) and size (200MB max).
      2. Saves the uploaded file to a temp directory.
      3. Forwards it to M1's /parse endpoint (HTTP multipart POST).
      4. M1 parses the document, OCRs images, extracts tables, chunks text,
         and automatically stores chunks in M2 ChromaDB.
      5. Returns the complete parse result including m2_status.

    WHY: M6 frontend drag-and-drop → M8 proxy → M1 parse → chunks in M2 →
         M3 immediately searchable. The full pipeline is triggered by this
         single endpoint.

    Returns:
        JSON with parse result: success, doc_id, markdown, page_count,
        metadata, m2_status (confirms M2 storage), etc.
    """
    # ---- Step 1: Validate filename ----
    filename: str = file.filename or "upload"
    if not filename:
        raise HTTPException(400, "Filename is required")

    # ---- Step 2: Validate file extension (security whitelist) ----
    suffix: str = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"File type '{suffix}' is not supported. "
            f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # ---- Step 3: Read file content with size limit ----
    content: bytes = await file.read()
    if len(content) > MAX_FILE_SIZE:
        max_mb: int = MAX_FILE_SIZE // (1024 * 1024)
        raise HTTPException(
            413,
            f"File too large. Maximum size: {max_mb} MB. "
            f"This file: {len(content) // (1024 * 1024)} MB",
        )

    # ---- Step 4: Save to temp file ----
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path: str = tmp.name

    try:
        # ---- Step 5: Forward to M1 /parse via HTTP multipart ----
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(tmp_path, "rb") as f:
                m1_resp = await client.post(
                    M1_PARSE_URL,
                    files={
                        "file": (
                            filename,
                            f,
                            file.content_type or "application/octet-stream",
                        )
                    },
                    data={"output_dir": output_dir, "backend": parse_backend},
                )

            if m1_resp.status_code != 200:
                raise HTTPException(
                    502,
                    "Document parsing service returned an error. "
                    "Please try again later.",
                )

            result = m1_resp.json()

        # ---- Step 6: Return the parsed result ----
        return {
            "filename": filename,
            "parse_result": result,
        }

    except httpx.ConnectError:
        raise HTTPException(
            503,
            "Document parsing service is temporarily unavailable. "
            "Please try again later.",
        )
    finally:
        # Clean up temp file — always, even on error
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
