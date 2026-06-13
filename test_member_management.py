#!/usr/bin/env python3
"""Quick integration test for Member Management API (US-011)."""

import sys
import os
import asyncio
import tempfile
import json

# Add M5 to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'm5-qa-engine'))

from m5_qa.project.manager import ProjectManager


async def test_member_management():
    """Test all member management operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        pm = ProjectManager(db_path)
        await pm.initialize()  # Initialize database schema

        # Create a test project
        project = await pm.create_project({
            "name": "Test Project",
            "type": "custom",
            "vessel_type": "Bulk Carrier",
            "primary_class": "DNV",
            "team_members": [
                {"user_id": "owner1", "role": "owner"}
            ]
        }, owner_id="owner1")
        project_id = project["project_id"]
        print(f"[OK] Created project: {project_id}")
        print(f"  Initial members: {project.get('team_members', [])}")

        # Test 1: List members
        members = await pm.list_members(project_id)
        assert len(members) == 1, f"Expected 1 member, got {len(members)}"
        assert members[0]["user_id"] == "owner1", f"Expected owner1, got {members[0]['user_id']}"
        print("[OK] Test 1 passed: list_members")

        # Test 2: Add a viewer
        updated = await pm.add_member(project_id, "viewer1", "viewer")
        members = await pm.list_members(project_id)
        assert len(members) == 2, f"Expected 2 members, got {len(members)}"
        assert any(m["user_id"] == "viewer1" and m["role"] == "viewer" for m in members), \
            "viewer1 not found or wrong role"
        print("[OK] Test 2 passed: add_member (viewer)")

        # Test 3: Add an editor
        await pm.add_member(project_id, "editor1", "editor")
        members = await pm.list_members(project_id)
        assert len(members) == 3, f"Expected 3 members, got {len(members)}"
        assert any(m["user_id"] == "editor1" and m["role"] == "editor" for m in members), \
            "editor1 not found or wrong role"
        print("[OK] Test 3 passed: add_member (editor)")

        # Test 4: Try to add duplicate (should fail)
        try:
            await pm.add_member(project_id, "viewer1", "viewer")
            print("[FAIL] Test 4 failed: Should not allow duplicate members")
            sys.exit(1)
        except ValueError as e:
            assert "already a member" in str(e), f"Wrong error message: {e}"
            print("[OK] Test 4 passed: duplicate member rejected")

        # Test 5: Update member role
        await pm.update_member_role(project_id, "viewer1", "editor")
        members = await pm.list_members(project_id)
        viewer1 = next(m for m in members if m["user_id"] == "viewer1")
        assert viewer1["role"] == "editor", f"Expected editor, got {viewer1['role']}"
        print("[OK] Test 5 passed: update_member_role")

        # Test 6: Try to update non-existent member (should fail)
        try:
            await pm.update_member_role(project_id, "nonexistent", "editor")
            print("[FAIL] Test 6 failed: Should not allow updating non-existent member")
            sys.exit(1)
        except ValueError as e:
            assert "not a member" in str(e), f"Wrong error message: {e}"
            print("[OK] Test 6 passed: non-existent member rejected")

        # Test 7: Remove a member
        await pm.remove_member(project_id, "viewer1")
        members = await pm.list_members(project_id)
        assert len(members) == 2, f"Expected 2 members, got {len(members)}"
        assert not any(m["user_id"] == "viewer1" for m in members), \
            "viewer1 should have been removed"
        print("[OK] Test 7 passed: remove_member")

        # Test 8: Invalid role validation
        try:
            await pm.add_member(project_id, "user2", "invalid_role")
            print("[FAIL] Test 8 failed: Should reject invalid role")
            sys.exit(1)
        except ValueError as e:
            assert "Invalid role" in str(e), f"Wrong error message: {e}"
            print("[OK] Test 8 passed: invalid role rejected")

        # Test 9: Non-existent project
        result = await pm.add_member("nonexistent_project", "user1", "viewer")
        assert result is None, "Should return None for non-existent project"
        print("[OK] Test 9 passed: non-existent project handling")

        print("\n" + "="*60)
        print("[OK] All 9 tests passed! Member Management is working correctly.")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(test_member_management())
