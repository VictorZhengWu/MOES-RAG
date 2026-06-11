"""Tests for ProjectManager (Phase 4-B)."""

import json
import os
import tempfile

import pytest
import pytest_asyncio

from m5_qa.project.manager import ProjectManager


@pytest_asyncio.fixture
async def pm():
    """Create a ProjectManager with a temp database."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="m5_test_project_")
    os.close(fd)
    mgr = ProjectManager(path)
    await mgr.initialize()
    yield mgr
    try:
        os.unlink(path)
    except (PermissionError, OSError):
        pass


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_project(pm):
    """Create a project and verify it's retrievable."""
    p = await pm.create_project({
        "name": "Test Bulk Carrier",
        "type": "new_build",
        "vessel_type": "bulk_carrier",
        "primary_class": "DNV",
        "phase": "design",
        "disciplines": ["结构", "轮机"],
    }, "user-1")
    assert p is not None
    assert p["name"] == "Test Bulk Carrier"
    assert p["primary_class"] == "DNV"
    assert p["phase"] == "design"


@pytest.mark.asyncio
async def test_list_projects(pm):
    """Create 2 projects, list should return both."""
    await pm.create_project({"name": "A"}, "user-1")
    await pm.create_project({"name": "B"}, "user-2")
    projects = await pm.list_projects()
    assert len(projects) >= 2


@pytest.mark.asyncio
async def test_list_projects_filtered(pm):
    """List filtered by owner."""
    await pm.create_project({"name": "User1 Project"}, "user-1")
    await pm.create_project({"name": "User2 Project"}, "user-2")
    projects = await pm.list_projects("user-1")
    assert len(projects) >= 1
    assert all(p.get("owner_id") == "user-1" for p in projects)


@pytest.mark.asyncio
async def test_update_project(pm):
    """Update project phase."""
    p = await pm.create_project({"name": "Test", "phase": "design"}, "user-1")
    updated = await pm.update_project(p["project_id"], {"phase": "construction"})
    assert updated["phase"] == "construction"


@pytest.mark.asyncio
async def test_delete_project(pm):
    """Delete project and verify it's gone."""
    p = await pm.create_project({"name": "To Delete"}, "user-1")
    await pm.delete_project(p["project_id"])
    result = await pm.get_project(p["project_id"])
    assert result is None


@pytest.mark.asyncio
async def test_archive_project(pm):
    """Archive sets is_archived=1."""
    p = await pm.create_project({"name": "Archive Me"}, "user-1")
    archived = await pm.archive_project(p["project_id"])
    assert archived["is_archived"] == 1


@pytest.mark.asyncio
async def test_dashboard(pm):
    """Dashboard returns stats for new project."""
    p = await pm.create_project({
        "name": "Dashboard Test", "vessel_type": "bulk_carrier", "primary_class": "DNV",
    }, "user-1")
    dash = await pm.get_dashboard(p["project_id"])
    assert dash["conversation_count"] == 0
    assert dash["document_count"] == 0
    assert dash["compliance_total"] >= 0


# ---------------------------------------------------------------------------
# Conversation linking tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_link_conversation(pm):
    """Link and list conversations."""
    p = await pm.create_project({"name": "Conv Test"}, "user-1")
    await pm.link_conversation(p["project_id"], "conv-1", "design/结构", ["规范咨询"])
    await pm.link_conversation(p["project_id"], "conv-2", "design/轮机", [])
    convs = await pm.list_conversations(p["project_id"])
    assert len(convs) == 2


@pytest.mark.asyncio
async def test_unlink_conversation(pm):
    """Unlink removes conversation from project."""
    p = await pm.create_project({"name": "Unlink Test"}, "user-1")
    await pm.link_conversation(p["project_id"], "conv-x", "")
    await pm.unlink_conversation(p["project_id"], "conv-x")
    convs = await pm.list_conversations(p["project_id"])
    assert len(convs) == 0


# ---------------------------------------------------------------------------
# Auto-classification tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_welding_content(pm):
    """Welding content should classify to welding discipline."""
    p = {"phase": "design"}
    folder = await pm.classify_conversation("EH36 钢板焊接预热温度要求 WPS", p)
    assert "焊接" in folder


@pytest.mark.asyncio
async def test_classify_structural_content(pm):
    """Structural content should classify to structural."""
    p = {"phase": "design"}
    folder = await pm.classify_conversation("舱口盖强度计算 finite element", p)
    assert "结构" in folder


@pytest.mark.asyncio
async def test_classify_generic_content(pm):
    """Generic content should go to 通用."""
    p = {"phase": "design"}
    folder = await pm.classify_conversation("Hello world", p)
    assert "通用" in folder


# ---------------------------------------------------------------------------
# Regulation templates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_carrier_template(pm):
    """Bulk carrier + DNV should auto-fill regulation list."""
    p = await pm.create_project({
        "name": "Template Test",
        "vessel_type": "bulk_carrier",
        "primary_class": "DNV",
    }, "user-1")
    regs = p.get("regulation_list", [])
    assert len(regs) >= 2  # At least DNV + IACS + MARPOL
