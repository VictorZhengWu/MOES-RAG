# ============================================================================
# Marine & Offshore Expert System — Development Setup (Windows PowerShell)
# ============================================================================

Write-Host "Installing Marine & Offshore Expert System packages..." -ForegroundColor Cyan

pip install -e contracts/
pip install -e m2-storage/
pip install -e m1-doc-parsing/
pip install -e m3-retrieval/
pip install -e m4-knowledge-graph/
pip install -e m5-qa-engine/
pip install -e m8-api-gateway/

Write-Host ""
Write-Host "All packages installed." -ForegroundColor Green
Write-Host "Run tests: python -m pytest m2-storage/tests/ m3-retrieval/tests/ m4-knowledge-graph/tests/ m5-qa-engine/tests/" -ForegroundColor Gray
Write-Host ""
Write-Host "Start M8:   python -c `"from m8_gateway.core.app import create_app; import uvicorn; uvicorn.run(create_app(), host='0.0.0.0', port=8000)`"" -ForegroundColor Gray
Write-Host "Start M1:   python -c `"from m1_parser.standalone.web_server import main; main(host='127.0.0.1', port=8007)`"" -ForegroundColor Gray
