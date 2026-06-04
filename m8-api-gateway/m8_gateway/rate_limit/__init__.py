# WHAT: Rate limit subpackage for M8 API Gateway.
# WHY: Separate namespace keeps the limiter isolated from auth and routing
#      concerns. Can be replaced with Redis-based implementation later
#      without touching any other module code.
