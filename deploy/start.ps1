# ============================================================================
# Marine & Offshore Expert System — Windows Startup Script
# ============================================================================
# Usage: .\deploy\start.ps1 [--profile search] [--profile llm]
# ============================================================================

param(
    [string]$Profile = ""
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Marine & Offshore Expert System" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Copy .env if not exists
if (-not (Test-Path "deploy\.env")) {
    Copy-Item "deploy\.env.example" "deploy\.env"
    Write-Host "[OK] Created deploy/.env from template" -ForegroundColor Green
    Write-Host "[!!] Edit deploy/.env to configure LLM and API keys" -ForegroundColor Yellow
}

# Build and start
Write-Host ""
Write-Host "Building containers (first time may take 10-20 min)..." -ForegroundColor Yellow

$composeArgs = @("compose", "-f", "deploy/docker-compose.yml", "up", "-d", "--build")
if ($Profile) {
    $composeArgs += @("--profile", $Profile)
}

docker @composeArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Compose failed. Check Docker is running." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " System is starting..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  M8 Gateway:     http://localhost:8000" -ForegroundColor White
Write-Host "  M1 Parser:      http://localhost:8007" -ForegroundColor White
Write-Host "  Meilisearch:    http://localhost:7700" -ForegroundColor White
Write-Host "  API Docs:       http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host " Health check:    curl http://localhost:8000/health" -ForegroundColor Gray
Write-Host " Create API key:  curl -X POST http://localhost:8000/admin/keys -H 'Content-Type: application/json' -d '{\"user_id\":\"admin\",\"tier\":\"pro\"}'" -ForegroundColor Gray
Write-Host ""
Write-Host " Got an LLM?" -ForegroundColor Yellow
Write-Host "   Local:  docker compose --profile llm up -d" -ForegroundColor Yellow
Write-Host "           docker exec -it marine-ollama ollama pull deepseek-r1:7b" -ForegroundColor Yellow
Write-Host "   Cloud:  set LLM_API_KEY and LLM_BASE_URL in deploy/.env" -ForegroundColor Yellow
