"""M8 Project routes — CRUD for marine engineering project workspaces.

Phase 4-B: Project management API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from m8_gateway.auth.key_manager import APIKey
from m8_gateway.auth.middleware import get_api_key

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str
    type: str = "custom"
    vessel_type: Optional[str] = None
    dwt: Optional[int] = None
    primary_class: str = ""
    secondary_class: Optional[str] = None
    regulation_year: str = "2025"
    phase: str = "design"
    disciplines: list[str] = []
    description: str = ""
    team_members: list[dict] = []
    tags: list[str] = []


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    vessel_type: Optional[str] = None
    dwt: Optional[int] = None
    primary_class: Optional[str] = None
    secondary_class: Optional[str] = None
    regulation_year: Optional[str] = None
    phase: Optional[str] = None
    disciplines: Optional[list[str]] = None
    description: Optional[str] = None
    team_members: Optional[list[dict]] = None
    tags: Optional[list[str]] = None


class LinkConversationRequest(BaseModel):
    conversation_id: str
    folder_path: str = ""
    tags: Optional[list[str]] = None


def _get_project_manager(request: Request):
    """Get or create the ProjectManager from app state."""
    pm = getattr(request.app.state, 'project_manager', None)
    if pm is None:
        raise HTTPException(503, "Project Manager not initialized")
    return pm


@router.post("")
async def create_project(
    body: CreateProjectRequest,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """POST /api/v1/projects — Create a new project."""
    pm = _get_project_manager(request)
    owner_id = api_key.user_id if hasattr(api_key, 'user_id') else 'unknown'
    project = await pm.create_project(body.model_dump(), owner_id)
    return project


@router.get("")
async def list_projects(
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """GET /api/v1/projects — List user's projects."""
    pm = _get_project_manager(request)
    owner_id = api_key.user_id if hasattr(api_key, 'user_id') else None
    projects = await pm.list_projects(owner_id)
    return projects


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """GET /api/v1/projects/{id} — Get project details."""
    pm = _get_project_manager(request)
    project = await pm.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """PATCH /api/v1/projects/{id} — Update project fields."""
    pm = _get_project_manager(request)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    project = await pm.update_project(project_id, data)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """DELETE /api/v1/projects/{id} — Delete a project."""
    pm = _get_project_manager(request)
    await pm.delete_project(project_id)
    return {"status": "deleted"}


@router.post("/{project_id}/archive")
async def archive_project(
    project_id: str,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """POST /api/v1/projects/{id}/archive — Archive a project."""
    pm = _get_project_manager(request)
    project = await pm.archive_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("/{project_id}/dashboard")
async def project_dashboard(
    project_id: str,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """GET /api/v1/projects/{id}/dashboard — Project dashboard stats."""
    pm = _get_project_manager(request)
    return await pm.get_dashboard(project_id)


# -- Conversations in project --

@router.post("/{project_id}/conversations")
async def link_conversation(
    project_id: str,
    body: LinkConversationRequest,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
):
    """POST /api/v1/projects/{id}/conversations — Link conversation to project."""
    pm = _get_project_manager(request)
    await pm.link_conversation(project_id, body.conversation_id, body.folder_path, body.tags)
    return {"status": "linked"}


@router.delete("/{project_id}/conversations/{conv_id}")
async def unlink_conversation(
    project_id: str, conv_id: str,
    request: Request, api_key: APIKey = Depends(get_api_key),
):
    """DELETE /api/v1/projects/{id}/conversations/{cid} — Unlink conversation."""
    pm = _get_project_manager(request)
    await pm.unlink_conversation(project_id, conv_id)
    return {"status": "unlinked"}


@router.get("/{project_id}/conversations")
async def list_conversations(
    project_id: str,
    request: Request,
    folder: Optional[str] = None,
    api_key: APIKey = Depends(get_api_key),
):
    """GET /api/v1/projects/{id}/conversations — List linked conversations."""
    pm = _get_project_manager(request)
    return await pm.list_conversations(project_id, folder)
