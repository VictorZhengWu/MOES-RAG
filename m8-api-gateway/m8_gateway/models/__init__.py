# WHAT: Pydantic schemas for M8 API Gateway request/response validation.
# WHY: FastAPI requires Pydantic models for automatic JSON serialization,
#      validation, and OpenAPI documentation generation. Separating schemas
#      from contracts allows M8 to evolve its API surface independently.
