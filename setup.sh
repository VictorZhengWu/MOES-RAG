#!/usr/bin/env bash
# ============================================================================
# Marine & Offshore Expert System — Development Setup
# ============================================================================
# Installs all Python packages in editable mode.
# Usage: bash setup.sh
# ============================================================================

set -e

echo "Installing Marine & Offshore Expert System packages..."

# Install in dependency order
pip install -e contracts/
pip install -e m2-storage/
pip install -e m1-doc-parsing/
pip install -e m3-retrieval/
pip install -e m4-knowledge-graph/
pip install -e m5-qa-engine/
pip install -e m8-api-gateway/

echo ""
echo "All packages installed."
echo "Run tests: python -m pytest m2-storage/tests/ m3-retrieval/tests/ m4-knowledge-graph/tests/ m5-qa-engine/tests/"
echo ""
echo "Start M8:   python -c \"from m8_gateway.core.app import create_app; import uvicorn; uvicorn.run(create_app(), host='0.0.0.0', port=8000)\""
echo "Start M1:   python -c \"from m1_parser.standalone.web_server import main; main(host='127.0.0.1', port=8007)\""
echo ""
echo "Docker:     docker compose -f deploy/docker-compose.yml up -d"
