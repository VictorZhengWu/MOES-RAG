@echo off
title MOES Dev Stopper
echo ============================================
echo   Stop MOES Dev Environment
echo ============================================
echo.

echo [1/2] Stopping backend Docker services...
cd /d "E:\myCode\RAG\deploy\personal"
docker compose down
echo       Backend stopped (data kept in volume)

echo.
echo [2/2] Frontend M6/M7: please close manually:
echo   - Close window titled "MOES-M6-4000"
echo   - Close window titled "MOES-M7-4001"
echo   (or press Ctrl+C in each window)

echo.
echo ============================================
echo   All stopped.
echo ============================================
pause
