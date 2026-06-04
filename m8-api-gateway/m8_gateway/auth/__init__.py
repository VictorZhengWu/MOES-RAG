"""M8 API Gateway — Authentication module.

WHAT: API key lifecycle management (generate, validate, revoke, list)
      and FastAPI middleware for Bearer token extraction.
WHY: M8 controls external API access independently from M5 user management.
     Key hash-only storage prevents key leaks from DB dumps.
"""
