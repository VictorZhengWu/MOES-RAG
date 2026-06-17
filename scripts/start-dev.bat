@echo off
REM ============================================
REM  MOES Dev Launcher
REM  Starts: Backend Docker + M6 User Portal + M7 Admin Portal
REM  Usage: Double-click (requires Docker Desktop running)
REM ============================================
title MOES Dev Launcher

REM Set API URL once; child windows launched by "start" inherit this env var
set NEXT_PUBLIC_API_URL=http://localhost:18000

echo ============================================
echo   MOES - Dev Environment Launcher
echo ============================================
echo.

echo [1/4] Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running.
    echo Please start Docker Desktop first, wait for the whale icon to be steady.
    pause
    exit /b 1
)
echo       Docker OK

echo [2/4] Starting backend (M8 API + Redis + Meilisearch)...
cd /d "E:\myCode\RAG\deploy\personal"
docker compose up -d
if %errorlevel% neq 0 (
    echo [ERROR] Backend failed to start.
    pause
    exit /b 1
)

echo [3/4] Starting M6 User Portal (port 3000)...
start "MOES-M6-3000" cmd /k "cd /d E:\myCode\RAG\m6-user-portal && npm run dev"

echo [4/4] Starting M7 Admin Portal (port 3001)...
start "MOES-M7-3001" cmd /k "cd /d E:\myCode\RAG\m7-admin-portal && npm run dev"

echo.
echo ============================================
echo   All start commands issued.
echo.
echo   URLs:
echo     User Portal : http://localhost:3000
echo     Admin Portal: http://localhost:3001
echo     API Docs    : http://localhost:18000/docs
echo.
echo   Get Admin Key (for M7 login):
echo     docker exec marine-m8 cat /data/admin_key.txt
echo.
echo   Wait notes:
echo     - Backend ready in ~30s
echo     - Frontend first build takes 30-60s
echo     - Keep the two frontend windows open
echo ============================================
echo.
echo Opening Admin Portal in 35s...
timeout /t 35 >nul
start http://localhost:3001
pause
