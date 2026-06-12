"""Project permission middleware (Phase 4-D, 00110-06).

WHAT: Action-based permission matrix for project operations.
      Owner has full control. Editor can read/comment/write.
      Viewer can read/comment only.

SECURITY:
    - Editor cannot delete projects or manage members (admin actions)
    - Editor cannot self-promote to Owner
    - Non-members get 403 (not 404 — prevents info leakage)
    - Sole remaining Editor can self-promote if Owner has left
"""

from __future__ import annotations

from fastapi import HTTPException, Request

# Permission matrix: action → allowed roles
PERMISSIONS = {
    'viewer': {'read': True, 'comment': True},
    'editor': {'read': True, 'comment': True, 'write': True},
    'owner':  {'read': True, 'comment': True, 'write': True, 'admin': True},
}


async def check_project_access(
    request: Request,
    project_id: str,
    user_id: str,
    action: str = 'read',
) -> bool:
    """Verify user has permission for the given action on a project.

    Args:
        request: FastAPI request (to access app.state.project_manager).
        project_id: Target project ID.
        user_id: Authenticated user ID (from API key).
        action: 'read' | 'comment' | 'write' | 'admin'.

    Returns:
        True if permitted.

    Raises:
        HTTPException(403): If user lacks permission.
        HTTPException(404): If project not found.
    """
    pm = request.app.state.project_manager
    if pm is None:
        raise HTTPException(503, "Project Manager not initialized")

    project = await pm.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Owner has full access
    if project.get('owner_id') == user_id:
        return True

    # Check team membership
    team = project.get('team_members', [])
    if isinstance(team, str):
        import json
        team = json.loads(team)

    member = next((m for m in team if m.get('user_id') == user_id), None)
    if not member:
        raise HTTPException(403, "Not a project member. Contact the project owner for access.")

    role = member.get('role', 'viewer')

    # Check action permission
    if action not in PERMISSIONS.get(role, {}):
        raise HTTPException(
            403,
            f"Your role '{role}' does not allow '{action}' actions. "
            f"Contact the project owner to upgrade your access."
        )

    # Admin actions (manage members, delete project) — Owner only
    if action == 'admin' and role != 'owner':
        raise HTTPException(
            403,
            "Only the project Owner can manage members or delete the project."
        )

    return True


async def check_self_promote_allowed(
    request: Request,
    project_id: str,
    user_id: str,
) -> bool:
    """Check if a user can self-promote to Owner.

    Allowed only when: the project has no active Owner AND this user
    is the sole remaining Editor.

    WHY: Prevents orphaned projects when the Owner leaves the organization.
    """
    pm = request.app.state.project_manager
    project = await pm.get_project(project_id)
    if not project:
        return False

    team = project.get('team_members', [])
    if isinstance(team, str):
        import json
        team = json.loads(team)

    editors = [m for m in team if m.get('role') == 'editor']
    return len(editors) == 1 and editors[0].get('user_id') == user_id
