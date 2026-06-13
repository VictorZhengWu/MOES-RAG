@echo off
REM Marine & Offshore Expert System — One-Click Start (Windows)
REM ============================================================================
REM Double-click this file to start. First run downloads images (5-10 min).
REM Subsequent starts take ~30 seconds.

title Marine Expert System

echo.
echo ============================================
echo   Marine ^& Offshore Expert System
echo   Personal Edition
echo ============================================
echo.

REM Check Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not installed or not running.
    echo.
    echo Please install Docker Desktop first:
    echo   https://www.docker.com/products/docker-desktop/
    echo.
    echo After installation, restart your computer and run this file again.
    pause
    exit /b 1
)

echo [1/3] Checking Docker status...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is installed but not running.
    echo Please start Docker Desktop and wait for it to finish initializing.
    pause
    exit /b 1
)

echo [2/3] Starting services...
cd /d "%~dp0"
docker compose up -d

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start services. Check the output above.
    pause
    exit /b 1
)

echo [3/3] Waiting for services to be ready...
echo   This may take 30-60 seconds on first run...
:wait_loop
curl -s http://localhost:18000/health >nul 2>&1
if %errorlevel% equ 0 goto ready
timeout /t 5 >nul
goto wait_loop

:ready
echo.
echo ============================================
echo   System is ready!
echo.
echo   User Portal:  http://localhost:3000
echo   Help:         http://localhost:3000/help
echo   API Docs:     http://localhost:18000/docs
echo.
echo   To stop:      Close this window, then run stop.bat
echo ============================================
echo.
echo Starting browser...
start http://localhost:3000

pause
