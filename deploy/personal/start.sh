#!/bin/bash
# Marine & Offshore Expert System — One-Click Start (Mac/Linux)
# ============================================================================
# Usage: chmod +x start.sh && ./start.sh
# First run downloads images (5-10 min). Subsequent starts take ~30 seconds.

set -e

echo ""
echo "============================================"
echo "  Marine & Offshore Expert System"
echo "  Personal Edition"
echo "============================================"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed."
    echo ""
    echo "Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    echo "Or on Linux: curl -fsSL https://get.docker.com | sh"
    echo ""
    exit 1
fi

echo "[1/3] Checking Docker status..."
if ! docker info &> /dev/null; then
    echo "[ERROR] Docker is installed but not running."
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo "[2/3] Starting services..."
cd "$(dirname "$0")"
docker compose up -d

echo "[3/3] Waiting for services to be ready..."
echo "  This may take 30-60 seconds on first run..."

for i in {1..60}; do
    if curl -s http://localhost:8000/health &> /dev/null; then
        break
    fi
    sleep 2
done

echo ""
echo "============================================"
echo "  System is ready!"
echo ""
echo "  User Portal:  http://localhost:3000"
echo "  Help:         http://localhost:3000/help"
echo "  API Docs:     http://localhost:8000/docs"
echo ""
echo "  To stop:      ./stop.sh"
echo "============================================"
echo ""

# Open browser
if command -v open &> /dev/null; then
    open http://localhost:3000
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:3000
fi
