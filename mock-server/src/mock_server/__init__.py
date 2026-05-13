"""
Mock Server for Phase 1 frontend development.

This package provides a standalone HTTP server that implements
all M5/M8 API endpoints with fake data conforming to contracts/ schemas.

WHY: M6 and M7 need a running backend to develop against in Phase 1,
before M1-M5 are implemented. The Mock Server lets frontend development
proceed in parallel with backend development.

IMPORTANT: This mock server will be REMOVED when M5 is fully implemented.
Do NOT build business logic here. Return fake data only.
"""
