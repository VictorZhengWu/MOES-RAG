#!/usr/bin/env python3
"""
M8 API Gateway startup script with path fixes.
WHAT: Sets up proper Python path and starts uvicorn server.
WHY: The contracts module needs to be in the path for imports to work.
"""

import sys
import os

# Add contracts and other modules to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'contracts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'm3-retrieval'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'm5-qa-engine'))

# Now start uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "m8_gateway.core.app:create_app",
        host="0.0.0.0",
        port=8001,  # Use 8001 to avoid conflict with system process on 8000
        factory=True,
        reload=True
    )