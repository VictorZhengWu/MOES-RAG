#!/usr/bin/env bash
# ============================================================================
# Marine & Offshore Expert System — Linux/Mac Startup Script
# ============================================================================
# Usage: ./deploy/start.sh [--profile search] [--profile llm]
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN} Marine & Offshore Expert System${NC}"
echo -e "${CYAN}========================================${NC}"

# Copy .env if not exists
if [ ! -f deploy/.env ]; then
    cp deploy/.env.example deploy/.env
    echo -e "${GREEN}[OK]${NC} Created deploy/.env from template"
    echo -e "${YELLOW}[!!]${NC} Edit deploy/.env to configure LLM and API keys"
fi

# Build and start
echo ""
echo -e "${YELLOW}Building containers (first time may take 10-20 min)...${NC}"

docker compose -f deploy/docker-compose.yml up -d --build "$@"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} System is starting...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  M8 Gateway:     http://localhost:8000"
echo "  M1 Parser:      http://localhost:8007"
echo "  Meilisearch:    http://localhost:7700"
echo "  API Docs:       http://localhost:8000/docs"
echo ""
echo " Health check:    curl http://localhost:8000/health"
echo " Create API key:  curl -X POST http://localhost:8000/admin/keys \\"
echo "                    -H 'Content-Type: application/json' \\"
echo "                    -d '{\"user_id\":\"admin\",\"tier\":\"pro\"}'"
echo ""
echo -e "${YELLOW} Got an LLM?${NC}"
echo "   Local:  docker compose --profile llm up -d"
echo "           docker exec -it marine-ollama ollama pull deepseek-r1:7b"
echo "   Cloud:  set LLM_API_KEY and LLM_BASE_URL in deploy/.env"
