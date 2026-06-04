# WHAT: Route handlers for M8 API Gateway.
# WHY: Separate subpackage keeps route modules isolated from core application
#      logic and auth middleware. Each route file corresponds to one API
#      surface (chat, models, keys).
