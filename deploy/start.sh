#!/usr/bin/env bash
# ============================================================================
# Marine & Offshore Expert System — Linux/Mac Startup Script
# ============================================================================
# Usage: ./deploy/start.sh [personal|enterprise|saas] [--profile search] [--profile llm]
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

MODE="personal"
PROFILES=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        personal|enterprise|saas) MODE="$1"; shift ;;
        --profile) PROFILES="$PROFILES --profile $2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [personal|enterprise|saas] [--profile search] [--profile llm]"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN} Marine & Offshore Expert System${NC}"
echo -e "${CYAN} Mode: ${MODE}${NC}"
echo -e "${CYAN}========================================${NC}"

# Copy .env if not exists
if [ ! -f deploy/.env ]; then
    cp deploy/.env.example deploy/.env
    echo -e "${GREEN}[OK]${NC} Created deploy/.env from template"
    echo -e "${YELLOW}[!!]${NC} Edit deploy/.env to configure LLM and API keys"
fi

# Set deployment mode in .env
if grep -q "^DEPLOYMENT_MODE=" deploy/.env 2>/dev/null; then
    sed -i.bak "s/^DEPLOYMENT_MODE=.*/DEPLOYMENT_MODE=${MODE}/" deploy/.env
else
    echo "DEPLOYMENT_MODE=${MODE}" >> deploy/.env
fi

echo -e "${YELLOW}Building and starting containers...${NC}"
docker compose -f deploy/docker-compose.yml up -d --build $PROFILES

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} Starting up (health checks in progress)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  Mode:           ${MODE}"
echo "  M8 Gateway:     http://localhost:8000"
echo "  M1 Parser:      http://localhost:8007"
echo "  Meilisearch:    http://localhost:7700"
echo "  API Docs:       http://localhost:8000/docs"
echo ""
echo " Health:    curl http://localhost:8000/health"
echo " API Key:   curl -X POST http://localhost:8000/admin/keys \\"
echo "              -H 'Content-Type: application/json' \\"
echo "              -d '{\"user_id\":\"admin\",\"tier\":\"pro\"}'"
echo ""
echo -e "${YELLOW} LLM not running?${NC}"
echo "   Local:  docker compose -f deploy/docker-compose.yml --profile llm up -d"
echo "           docker exec -it marine-ollama ollama pull deepseek-r1:7b"
echo "   Cloud:  set LLM_API_KEY + LLM_BASE_URL in deploy/.env"
echo ""
echo -e "${CYAN} Logs: docker compose -f deploy/docker-compose.yml logs -f${NC}"
