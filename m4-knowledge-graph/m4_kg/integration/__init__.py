"""
M4 Knowledge Graph — Integration layer with M1 (Document Parsing) and M2 (Storage).

WHAT:
  Provides hooks for M1 and M2 integration:
  - ``m1_bridge.on_parse_complete()`` — async hook called by M1 after document
    parsing completes, triggering background KG extraction.
  - ``m2_bridge`` (future) — writes KG build status to M2 RelationalDB.

WHY:
  The integration layer keeps cross-module wiring isolated from the core engine.
  M1 and M2 are separate modules that M4 depends on at runtime, not at compile
  time. The bridge functions decouple M1/M2-specific call signatures from the
  engine's internal API.
"""
