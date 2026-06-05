"""
M8 API Gateway — Document Upload Route.

WHAT: Proxies file upload from M6 frontend to M1's document parsing engine.
      Accepts multipart/form-data, forwards to M1 /parse, returns parsed result
      with m2_status confirming chunks were stored for M3 retrieval.

WHY: M6 frontend has drag-and-drop file upload UI but needs a backend endpoint.
     M1's web_server runs on port 8007 internally; M8 proxies the request so
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

# M1 web_server address (internal, not exposed to clients)
M1_PARSE_URL = os.environ.get("M1_PARSE_URL", "http://127.0.0.1:8007/parse")


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    output_dir: str = Form(default="./output"),
    api_key: APIKey = Depends(get_api_key),
):
    """
    POST /api/v1/documents/upload — Upload and parse a document.

    WHAT:
      1. Saves the uploaded file to a temp directory.
      2. Forwards it to M1's /parse endpoint (HTTP multipart POST).
      3. M1 parses the document, OCRs images, extracts tables, chunks text,
         and automatically stores chunks in M2 ChromaDB.
      4. Returns the complete parse result including m2_status.

    WHY: M6 frontend drag-and-drop → M8 proxy → M1 parse → chunks in M2 →
         M3 immediately searchable. The full pipeline is triggered by this
         single endpoint.

    Returns:
        JSON with parse result: success, doc_id, markdown, page_count,
        metadata, m2_status (confirms M2 storage), etc.
    """
    # Step 1: Validate file type (basic check, M1 does deeper validation)
    filename = file.filename or "upload"
    if not filename:
        raise HTTPException(400, "Filename is required")

    # Step 2: Save to temp file (must exist on disk for M1's multipart upload)
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Step 3: Forward to M1 /parse via HTTP multipart
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(tmp_path, "rb") as f:
                m1_resp = await client.post(
                    M1_PARSE_URL,
                    files={"file": (filename, f, file.content_type or "application/octet-stream")},
                    data={"output_dir": output_dir},
                )

            if m1_resp.status_code != 200:
                raise HTTPException(
                    502,
                    f"M1 parse failed: {m1_resp.status_code} — {m1_resp.text[:200]}",
                )

            result = m1_resp.json()

        # Step 4: Return the parsed result
        return {
            "filename": filename,
            "parse_result": result,
        }

    except httpx.ConnectError:
        raise HTTPException(
            503,
            "M1 document parsing engine is not running. "
            "Start it with: python -c \"from m1_parser.standalone.web_server import main; main(port=8007)\"",
        )
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
