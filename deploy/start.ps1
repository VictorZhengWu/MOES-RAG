# ============================================================================
# Marine & Offshore Expert System — Windows Startup Script
# ============================================================================
# Usage: .\deploy\start.ps1 personal [--profile search] [--profile llm]
# ============================================================================

param(
    [ValidateSet("personal", "enterprise", "saas")]
    [string]$Mode = "personal",
    [string[]]$Profiles = @()
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Marine & Offshore Expert System" -ForegroundColor Cyan
Write-Host " Mode: $Mode" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Copy .env if not exists
if (-not (Test-Path "deploy\.env")) {
    Copy-Item "deploy\.env.example" "deploy\.env"
    Write-Host "[OK] Created deploy/.env from template" -ForegroundColor Green
    Write-Host "[!!] Edit deploy/.env to configure LLM and API keys" -ForegroundColor Yellow
}

# Set DEPLOYMENT_MODE in .env
$envContent = Get-Content "deploy\.env" -Raw -ErrorAction SilentlyContinue
if ($envContent -match "DEPLOYMENT_MODE=") {
    $envContent = $envContent -replace "DEPLOYMENT_MODE=.*", "DEPLOYMENT_MODE=$Mode"
} else {
    $envContent += "`nDEPLOYMENT_MODE=$Mode"
}
Set-Content "deploy\.env" $envContent -NoNewline

# Build and start
Write-Host ""
Write-Host "Building and starting containers..." -ForegroundColor Yellow

$composeArgs = @("compose", "-f", "deploy/docker-compose.yml", "up", "-d", "--build")
foreach ($p in $Profiles) {
    $composeArgs += @("--profile", $p)
}

docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker Compose failed. Check Docker is running." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Starting up (health checks in progress)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Mode:           $Mode" -ForegroundColor White
Write-Host "  M8 Gateway:     http://localhost:8000" -ForegroundColor White
Write-Host "  M1 Parser:      http://localhost:8007" -ForegroundColor White
Write-Host "  Meilisearch:    http://localhost:7700" -ForegroundColor White
Write-Host "  API Docs:       http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host " Health:    curl http://localhost:8000/health" -ForegroundColor Gray
Write-Host " API Key:   curl -X POST http://localhost:8000/admin/keys -H 'Content-Type: application/json' -d '{\"user_id\":\"admin\",\"tier\":\"pro\"}'" -ForegroundColor Gray
Write-Host ""
Write-Host " LLM not running?" -ForegroundColor Yellow
Write-Host "   Local:  docker compose -f deploy/docker-compose.yml --profile llm up -d" -ForegroundColor Yellow
Write-Host "           docker exec -it marine-ollama ollama pull deepseek-r1:7b" -ForegroundColor Yellow
Write-Host "   Cloud:  set LLM_API_KEY + LLM_BASE_URL in deploy/.env" -ForegroundColor Yellow
