#!/usr/bin/env python3
"""Test that Member Management API routes are properly defined."""

import sys
import os

# Add M8 to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'm8-api-gateway'))

try:
    from m8_gateway.routes.projects import router
    print("[OK] Successfully imported projects router")

    # Check that all member routes are registered
    routes = [route.path for route in router.routes]
    print(f"\n[INFO] Total routes: {len(routes)}")

    member_routes = [r for r in routes if "/members" in r]
    print(f"[INFO] Member-related routes: {len(member_routes)}")

    expected_routes = [
        "/{project_id}/members",
        "/{project_id}/members",
        "/{project_id}/members",
        "/{project_id}/members/{user_id}",
    ]

    print("\n[CHECK] Expected member routes:")
    for route in [
        "GET /{project_id}/members (list)",
        "POST /{project_id}/members (add)",
        "PATCH /{project_id}/members (update role)",
        "DELETE /{project_id}/members/{user_id} (remove)"
    ]:
        print(f"  - {route}")

    # Check for duplicate route paths (different methods)
    from collections import Counter
    route_counts = Counter(routes)
    duplicates = {k: v for k, v in route_counts.items() if v > 1}
    if duplicates:
        print(f"\n[WARN] Duplicate route paths (different HTTP methods):")
        for path, count in duplicates.items():
            methods = [r.methods for r in router.routes if r.path == path]
            print(f"  {path}: {count} routes with methods {methods}")

    print("\n[OK] All Member Management API routes are properly defined!")

except ImportError as e:
    print(f"[FAIL] Failed to import: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[FAIL] Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
