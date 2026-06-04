# M8 API Gateway — Marine & Offshore Expert System
#
# WHAT: Layer 5 (Gateway) — external API entry point.
#       Authentication -> Rate Limiting -> Routing -> M5 QA Engine.
# WHY: Independent FastAPI process (port 8000) that exposes an
#      OpenAI-compatible API with self-managed API keys (sk-m8-xxx).
