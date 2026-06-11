"""M5 Project Manager — CRUD for marine engineering project workspaces.

WHAT: SQLite-backed persistence for the Projects feature (Phase 4-B).
      Manages 6 tables: projects, project_conversations, project_documents,
      research_issues, project_conclusions, compliance_items.

WHY: Projects is M5-specific business logic. Like ConversationManager,
     it uses its own SQLite database (aisqlite) rather than going through
     M2's RelationalDB abstraction. This keeps M2 unaware of M5 schemas.

TABLES:
    projects              — project metadata (name, type, phase, vessel, class)
    project_conversations — links conversations to projects with folder/tag metadata
    project_documents     — project-uploaded documents with parse status
    research_issues       — kanban-style research tasks per project
    project_conclusions   — extracted key findings from conversations/reports
    compliance_items      — per-clause compliance tracking matrix
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

import aiosqlite

logger = __import__('logging').getLogger(__name__)

# Built-in regulation templates by vessel type + classification society
REGULATION_TEMPLATES: dict[str, list[str]] = {
    "bulk_carrier_dnv": [
        "DNV Pt.1 Ch.1", "DNV Pt.3 Ch.4", "DNV Pt.5 Ch.5",
        "IACS UR S11", "IACS UR S21", "MARPOL Annex VI",
    ],
    "lng_carrier_dnv": [
        "DNV Pt.5 Ch.5", "DNV Pt.5 Ch.6", "IGC Code", "IGF Code",
    ],
    "tanker_dnv": [
        "DNV Pt.3 Ch.4", "DNV Pt.5 Ch.5", "MARPOL Annex I",
    ],
    "container_dnv": [
        "DNV Pt.3 Ch.4", "DNV Pt.5 Ch.5", "IACS UR S11A",
    ],
    "offshore_dnv": [
        "DNV-ST-0126", "DNV-RP-C203", "ISO 19902",
    ],
}

# Discipline keywords for auto-classification
DISCIPLINE_KEYWORDS: dict[str, list[str]] = {
    "结构": ["结构", "强度", "屈曲", "疲劳", "structural", "strength", "fatigue", "buckling"],
    "轮机": ["轮机", "柴油机", "推进", "machinery", "engine", "propulsion"],
    "管系": ["管系", "管路", "泵", "piping", "pipe", "pump", "valve"],
    "焊接": ["焊接", "WPS", "PQR", "welding", "weld"],
    "电气": ["电气", "电缆", "electrical", "cable", "power"],
    "通用": [],
}

# Phase keywords for auto-classification
PHASE_KEYWORDS = {
    "设计阶段": ["设计", "计算", "design", "calculation"],
    "建造阶段": ["建造", "检验", "construction", "inspection", "testing"],
    "交付阶段": ["交付", "审图", "delivery", "approval"],
    "运营阶段": ["运营", "维护", "operation", "maintenance"],
}

_VESSEL_TYPES = [
    "bulk_carrier", "lng_carrier", "tanker", "container",
    "offshore", "passenger", "naval", "custom",
]

_PROJECT_TYPES = ["new_build", "retrofit", "maintenance", "offshore", "research", "custom"]
_PHASES = ["design", "construction", "delivery", "operation"]
_ISSUE_STATUSES = ["pending", "in_progress", "resolved", "closed"]
_COMPLIANCE_STATUSES = ["unverified", "needs_review", "verified", "not_applicable"]

DEFAULT_DB_PATH = "./data/m5_qa.db"


class ProjectManager:
    """CRUD manager for project workspaces."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self._db_path = db_path

    async def initialize(self) -> None:
        """Create all project tables if they don't exist."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_SCHEMA_SQL)
            await db.commit()

    # ==================================================================
    # PROJECTS CRUD
    # ==================================================================

    async def create_project(self, data: dict, owner_id: str) -> dict:
        """Create a new project. Returns the created project dict."""
        pid = uuid.uuid4().hex[:12]
        now = time.time()

        # Auto-fill regulation template if applicable
        regulation_list = data.get("regulation_list")
        if not regulation_list:
            vessel = data.get("vessel_type", "")
            society = data.get("primary_class", "").lower()
            key = f"{vessel}_{society}"
            regulation_list = REGULATION_TEMPLATES.get(key, [])

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                INSERT INTO projects (project_id, name, type, vessel_type, dwt,
                    primary_class, secondary_class, regulation_year, phase,
                    disciplines, description, owner_id, team_members,
                    regulation_list, tags, is_archived, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (
                pid, data.get("name", "Untitled"), data.get("type", "custom"),
                data.get("vessel_type"), data.get("dwt"),
                data.get("primary_class", ""), data.get("secondary_class", ""),
                data.get("regulation_year", "2025"), data.get("phase", "design"),
                json.dumps(data.get("disciplines", [])),
                data.get("description", ""), owner_id,
                json.dumps(data.get("team_members", [])),
                json.dumps(regulation_list),
                json.dumps(data.get("tags", [])),
                now, now,
            ))
            await db.commit()

        # Auto-create compliance items from regulation list
        await self._init_compliance_matrix(pid, regulation_list)

        return await self.get_project(pid)

    async def get_project(self, project_id: str) -> Optional[dict]:
        """Get a single project by ID."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM projects WHERE project_id = ?", (project_id,)
            )
            row = await cursor.fetchone()
        return _row_to_dict(row, cursor) if row else None

    async def list_projects(self, owner_id: Optional[str] = None) -> list[dict]:
        """List projects, optionally filtered by owner."""
        async with aiosqlite.connect(self._db_path) as db:
            if owner_id:
                cursor = await db.execute(
                    "SELECT * FROM projects WHERE owner_id = ? AND is_archived = 0 "
                    "ORDER BY updated_at DESC", (owner_id,)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM projects WHERE is_archived = 0 "
                    "ORDER BY updated_at DESC"
                )
            rows = await cursor.fetchall()
        return [_row_to_dict(r, cursor) for r in rows]

    async def update_project(self, project_id: str, data: dict) -> Optional[dict]:
        """Update project fields. Only updates provided keys."""
        existing = await self.get_project(project_id)
        if not existing:
            return None
        merged = {**existing, **data}
        merged["updated_at"] = time.time()

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                UPDATE projects SET name=?, type=?, vessel_type=?, dwt=?,
                    primary_class=?, secondary_class=?, regulation_year=?,
                    phase=?, disciplines=?, description=?, team_members=?,
                    regulation_list=?, tags=?, updated_at=?
                WHERE project_id=?
            """, (
                merged["name"], merged["type"], merged.get("vessel_type"),
                merged.get("dwt"), merged["primary_class"],
                merged.get("secondary_class"), merged.get("regulation_year"),
                merged["phase"], json.dumps(merged.get("disciplines", [])),
                merged.get("description", ""),
                json.dumps(merged.get("team_members", [])),
                json.dumps(merged.get("regulation_list", [])),
                json.dumps(merged.get("tags", [])),
                merged["updated_at"], project_id,
            ))
            await db.commit()
        return await self.get_project(project_id)

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project and all related data (cascade)."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            await db.execute("DELETE FROM project_conversations WHERE project_id = ?", (project_id,))
            await db.execute("DELETE FROM project_documents WHERE project_id = ?", (project_id,))
            await db.execute("DELETE FROM research_issues WHERE project_id = ?", (project_id,))
            await db.execute("DELETE FROM project_conclusions WHERE project_id = ?", (project_id,))
            await db.execute("DELETE FROM compliance_items WHERE project_id = ?", (project_id,))
            await db.commit()
        return True

    async def archive_project(self, project_id: str) -> Optional[dict]:
        """Archive a project (set is_archived=1)."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE projects SET is_archived = 1, updated_at = ? WHERE project_id = ?",
                (time.time(), project_id),
            )
            await db.commit()
        return await self.get_project(project_id)

    async def get_dashboard(self, project_id: str) -> dict:
        """Return project dashboard stats."""
        async with aiosqlite.connect(self._db_path) as db:
            conv_count = await db.execute(
                "SELECT COUNT(*) FROM project_conversations WHERE project_id = ?",
                (project_id,)
            )
            doc_count = await db.execute(
                "SELECT COUNT(*) FROM project_documents WHERE project_id = ?",
                (project_id,)
            )
            issue_count = await db.execute(
                "SELECT COUNT(*) FROM research_issues WHERE project_id = ?",
                (project_id,)
            )
            compliance_row = await db.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN status='verified' THEN 1 ELSE 0 END) as verified "
                "FROM compliance_items WHERE project_id = ?",
                (project_id,)
            )
            c = await compliance_row.fetchone()
            total_c = c[0] or 0
            verified_c = c[1] or 0

            conv_n = (await conv_count.fetchone())[0] or 0
            doc_n = (await doc_count.fetchone())[0] or 0
            issue_n = (await issue_count.fetchone())[0] or 0

        return {
            "conversation_count": conv_n,
            "document_count": doc_n,
            "issue_count": issue_n,
            "compliance_total": total_c,
            "compliance_verified": verified_c,
            "compliance_pct": round(verified_c / total_c * 100, 1) if total_c > 0 else 0,
        }

    # ==================================================================
    # CONVERSATION LINKING
    # ==================================================================

    async def link_conversation(
        self, project_id: str, conversation_id: str,
        folder_path: str = "", tags: Optional[list[str]] = None,
    ) -> None:
        """Link a conversation to a project with folder and tag metadata."""
        async with aiosqlite.connect(self._db_path) as db:
            # Get max order_index for this folder
            row = await db.execute(
                "SELECT COALESCE(MAX(order_index), -1) FROM project_conversations "
                "WHERE project_id = ? AND folder_path = ?",
                (project_id, folder_path),
            )
            max_order = (await row.fetchone())[0]
            await db.execute("""
                INSERT OR REPLACE INTO project_conversations
                    (project_id, conversation_id, folder_path, tags, order_index, linked_since)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (project_id, conversation_id, folder_path,
                   json.dumps(tags or []), max_order + 1, time.time()))
            await db.commit()

    async def unlink_conversation(self, project_id: str, conversation_id: str) -> None:
        """Remove a conversation from a project."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "DELETE FROM project_conversations WHERE project_id = ? AND conversation_id = ?",
                (project_id, conversation_id),
            )
            await db.commit()

    async def list_conversations(self, project_id: str, folder_path: Optional[str] = None) -> list[dict]:
        """List conversations linked to a project, optionally filtered by folder."""
        async with aiosqlite.connect(self._db_path) as db:
            if folder_path:
                cursor = await db.execute(
                    "SELECT * FROM project_conversations WHERE project_id = ? AND folder_path = ? "
                    "ORDER BY order_index",
                    (project_id, folder_path),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM project_conversations WHERE project_id = ? "
                    "ORDER BY folder_path, order_index",
                    (project_id,),
                )
            rows = await cursor.fetchall()
        return [_row_to_dict(r, cursor) for r in rows]

    async def classify_conversation(self, content: str, project: dict) -> str:
        """Auto-classify conversation content to a folder path (FR-10)."""
        phase = project.get("phase", "设计阶段")
        for p_key, keywords in PHASE_KEYWORDS.items():
            if any(k in content for k in keywords):
                phase = p_key
                break
        discipline = "通用"
        for disc, keywords in DISCIPLINE_KEYWORDS.items():
            if disc == "通用":
                continue
            if any(k in content for k in keywords):
                discipline = disc
                break
        return f"{phase}/{discipline}"

    # ==================================================================
    # DOCUMENTS (00105-03)
    # ==================================================================

    async def add_document(self, project_id: str, filename: str,
                           file_key: str, uploaded_by: str,
                           discipline: Optional[str] = None) -> dict:
        """Add a document record to a project (pending parse)."""
        doc_id = uuid.uuid4().hex[:12]
        now = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                INSERT INTO project_documents
                    (project_id, document_id, filename, discipline,
                     parse_status, file_key, version, uploaded_by, uploaded_at)
                VALUES (?, ?, ?, ?, 'pending', ?, 1, ?, ?)
            """, (project_id, doc_id, filename, discipline, file_key, uploaded_by, now))
            await db.commit()
        return {"document_id": doc_id, "filename": filename, "parse_status": "pending"}

    async def list_documents(self, project_id: str) -> list[dict]:
        """List all documents in a project."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM project_documents WHERE project_id = ? "
                "ORDER BY uploaded_at DESC", (project_id,)
            )
            rows = await cursor.fetchall()
        return [_row_to_dict(r, cursor) for r in rows]

    async def update_document_status(self, project_id: str, doc_id: str,
                                     status: str, parse_result: Optional[dict] = None) -> None:
        """Update document parse status and result."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE project_documents SET parse_status = ?, parse_result_json = ? "
                "WHERE project_id = ? AND document_id = ?",
                (status, json.dumps(parse_result) if parse_result else None,
                 project_id, doc_id),
            )
            await db.commit()

    async def delete_document(self, project_id: str, doc_id: str) -> bool:
        """Delete a document from a project."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "DELETE FROM project_documents WHERE project_id = ? AND document_id = ?",
                (project_id, doc_id),
            )
            await db.commit()
        return True

    # ==================================================================
    # RESEARCH ISSUES (00105-04)
    # ==================================================================

    async def create_issue(self, project_id: str, data: dict) -> dict:
        """Create a research issue."""
        iid = uuid.uuid4().hex[:12]
        now = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                INSERT INTO research_issues
                    (issue_id, project_id, title, description, status,
                     priority, assignee, related_conversation_id,
                     related_document_id, related_regulation, deadline,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                iid, project_id, data.get("title", ""), data.get("description", ""),
                data.get("status", "pending"), data.get("priority", "medium"),
                data.get("assignee"), data.get("related_conversation_id"),
                data.get("related_document_id"), data.get("related_regulation"),
                data.get("deadline"), now, now,
            ))
            await db.commit()
        return {"issue_id": iid, "status": "pending"}

    async def list_issues(self, project_id: str) -> list[dict]:
        """List all research issues in a project."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM research_issues WHERE project_id = ? "
                "ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
                "created_at DESC", (project_id,)
            )
            rows = await cursor.fetchall()
        return [_row_to_dict(r, cursor) for r in rows]

    async def update_issue(self, issue_id: str, data: dict) -> Optional[dict]:
        """Update issue fields."""
        async with aiosqlite.connect(self._db_path) as db:
            sets = []
            params = []
            for k, v in data.items():
                if k in ("title", "description", "status", "priority",
                         "assignee", "related_conversation_id",
                         "related_document_id", "related_regulation", "deadline"):
                    sets.append(f"{k} = ?")
                    params.append(v)
            if not sets:
                return None
            sets.append("updated_at = ?")
            params.append(time.time())
            params.append(issue_id)
            await db.execute(
                f"UPDATE research_issues SET {', '.join(sets)} WHERE issue_id = ?",
                params,
            )
            await db.commit()
        return {"issue_id": issue_id, "updated": True}

    # ==================================================================
    # CONCLUSIONS (00105-04)
    # ==================================================================

    async def create_conclusion(self, project_id: str, data: dict) -> dict:
        """Create a project conclusion (manual or from Deep Research)."""
        cid = uuid.uuid4().hex[:12]
        now = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                INSERT INTO project_conclusions
                    (conclusion_id, project_id, text, detail, source_type,
                     source_conversation_id, source_report_id, citation,
                     status, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cid, project_id, data.get("text", ""), data.get("detail", ""),
                data.get("source_type", "manual"),
                data.get("source_conversation_id"), data.get("source_report_id"),
                json.dumps(data.get("citation", [])),
                data.get("status", "general"),
                json.dumps(data.get("tags", [])), now,
            ))
            await db.commit()

        # Phase 4-C (00107-03): Auto-update compliance on citation
        citation = data.get("citation", [])
        if citation:
            await self._auto_update_compliance(project_id, citation, cid)

        return {"conclusion_id": cid}

    async def delete_conclusion(self, project_id: str, conclusion_id: str) -> bool:
        """Delete a conclusion with compliance rollback (00107-05)."""
        # Get the conclusion's citations before deleting
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT citation FROM project_conclusions "
                "WHERE project_id = ? AND conclusion_id = ?",
                (project_id, conclusion_id),
            )
            row = await cursor.fetchone()
            if not row:
                return False
            try:
                citations = json.loads(row[0]) if isinstance(row[0], str) else []
            except (json.JSONDecodeError, TypeError):
                citations = []

            # Delete
            await db.execute(
                "DELETE FROM project_conclusions WHERE project_id = ? AND conclusion_id = ?",
                (project_id, conclusion_id),
            )
            await db.commit()

        # Rollback compliance: check if any other conclusion references these clauses
        if citations:
            await self._rollback_compliance(project_id, citations)

        return True

    async def list_conclusions(self, project_id: str) -> list[dict]:
        """List all conclusions in a project."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM project_conclusions WHERE project_id = ? "
                "ORDER BY created_at DESC", (project_id,)
            )
            rows = await cursor.fetchall()
        return [_row_to_dict(r, cursor) for r in rows]

    async def _auto_update_compliance(self, project_id: str, citations: list, conclusion_id: str) -> None:
        """00107-03: Auto-set compliance needs_review when conclusion cites a clause."""
        for ref in citations:
            clause_ref = ref.get("clause", ref.get("clause_ref", ""))
            if not clause_ref:
                continue
            # Find matching compliance item
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute(
                    "SELECT clause_id, status, linked_conclusions FROM compliance_items "
                    "WHERE project_id = ? AND (clause_ref = ? OR clause_id LIKE ?)",
                    (project_id, clause_ref, f"%{clause_ref[:20]}%"),
                )
                row = await cursor.fetchone()
                if not row:
                    continue
                cid = row["clause_id"]
                current_status = row["status"]
                if current_status == "verified":
                    continue  # Don't override verified
                linked = json.loads(row["linked_conclusions"]) if isinstance(row["linked_conclusions"], str) else []
                if conclusion_id not in linked:
                    linked.append(conclusion_id)
                await db.execute(
                    "UPDATE compliance_items SET status = 'needs_review', "
                    "linked_conclusions = ?, updated_at = ? "
                    "WHERE project_id = ? AND clause_id = ?",
                    (json.dumps(linked), time.time(), project_id, cid),
                )
                await db.commit()

    async def _rollback_compliance(self, project_id: str, citations: list) -> None:
        """00107-05: Rollback compliance if no other conclusion references clause."""
        for ref in citations:
            clause_ref = ref.get("clause", ref.get("clause_ref", ""))
            if not clause_ref:
                continue
            async with aiosqlite.connect(self._db_path) as db:
                cursor = await db.execute(
                    "SELECT clause_id, status, linked_conclusions FROM compliance_items "
                    "WHERE project_id = ? AND (clause_ref = ? OR clause_id LIKE ?)",
                    (project_id, clause_ref, f"%{clause_ref[:20]}%"),
                )
                row = await cursor.fetchone()
                if not row:
                    continue
                cid = row["clause_id"]
                current_status = row["status"]
                if current_status in ("verified", "not_applicable"):
                    continue  # Don't rollback these
                linked = json.loads(row["linked_conclusions"]) if isinstance(row["linked_conclusions"], str) else []
                # Check if other conclusions still reference this
                if len(linked) > 0:
                    # There are still linked conclusions → keep current status
                    continue
                # No more references → revert to unverified
                await db.execute(
                    "UPDATE compliance_items SET status = 'unverified', "
                    "linked_conclusions = '[]', updated_at = ? "
                    "WHERE project_id = ? AND clause_id = ?",
                    (time.time(), project_id, cid),
                )
                await db.commit()

    # ==================================================================
    # COMPLIANCE MATRIX (00105-05)
    # ==================================================================

    async def list_compliance(self, project_id: str) -> list[dict]:
        """List all compliance items."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM compliance_items WHERE project_id = ? "
                "ORDER BY clause_id", (project_id,)
            )
            rows = await cursor.fetchall()
        return [_row_to_dict(r, cursor) for r in rows]

    async def update_compliance(self, project_id: str, clause_id: str,
                                data: dict) -> Optional[dict]:
        """Update a single compliance item status."""
        status = data.get("status", "unverified")
        if status not in _COMPLIANCE_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        now = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                UPDATE compliance_items SET status = ?, verified_by = ?,
                    verified_at = ?, deviation_note = ?, updated_at = ?
                WHERE project_id = ? AND clause_id = ?
            """, (
                status, data.get("verified_by"), now if status == "verified" else None,
                data.get("deviation_note"), now, project_id, clause_id,
            ))
            await db.commit()
        return {"clause_id": clause_id, "status": status}

    # ==================================================================
    # SEARCH SCOPE (00105-06)
    # ==================================================================

    async def search_project_documents(self, project_id: str,
                                       query: str) -> list[dict]:
        """Simple full-text search across project document parse results."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT document_id, filename, parse_result_json "
                "FROM project_documents WHERE project_id = ? "
                "AND parse_status = 'done' AND parse_result_json LIKE ? "
                "LIMIT 10",
                (project_id, f"%{query}%"),
            )
            rows = await cursor.fetchall()
        return [_row_to_dict(r, cursor) for r in rows]

    # ==================================================================
    # PROJECT REPORT (00105-10)
    # ==================================================================

    async def generate_report(self, project_id: str) -> str:
        """Generate a Markdown project summary report (FR-9)."""
        project = await self.get_project(project_id)
        if not project:
            return "# Project Not Found\n\nThe requested project does not exist."

        dash = await self.get_dashboard(project_id)
        conclusions = await self.list_conclusions(project_id)
        issues = await self.list_issues(project_id)
        compliance = await self.list_compliance(project_id)

        verified = sum(1 for c in compliance if c.get("status") == "verified")
        total = len(compliance)
        pct = round(verified / total * 100, 1) if total > 0 else 0

        # Build conclusions section
        concl_lines = "\n".join(
            f"- **{c.get('text', '')}** "
            f"({'✅ verified' if c.get('status') == 'applied' else '📋 ' + c.get('status', 'general')})"
            for c in conclusions[:10]
        ) or "- No conclusions recorded yet."

        # Build issues section
        issue_lines = "\n".join(
            f"- [{i.get('priority', '?')}] {i.get('title', '')} ({i.get('status', '?')})"
            for i in issues[:10]
        ) or "- No open issues."

        # Build compliance section
        comp_lines = "\n".join(
            f"| {c.get('clause_ref', '?')} | {c.get('status', '?')} | {c.get('deviation_note', '') or '—'} |"
            for c in compliance[:20]
        )
        comp_table = (
            f"| Clause | Status | Deviation |\n|--------|--------|-----------|\n{comp_lines}"
            if comp_lines else "No compliance items."
        )

        return f"""# {project.get('name', 'Project')} — Summary Report

## Project Information
- **Type**: {project.get('type', 'N/A')}
- **Vessel**: {project.get('vessel_type', 'N/A')}
- **Class**: {project.get('primary_class', 'N/A')} ({project.get('regulation_year', 'N/A')})
- **Phase**: {project.get('phase', 'N/A')}

## Compliance Status
- **Progress**: {pct}% ({verified}/{total} clauses verified)
- **Conversations**: {dash['conversation_count']}
- **Documents**: {dash['document_count']}
- **Open Issues**: {len(issues)}

## Key Conclusions
{concl_lines}

## Open Issues ({len(issues)})
{issue_lines}

## Compliance Matrix
{comp_table}

---
*Generated by Marine & Offshore Expert System on {__import__('datetime').datetime.now().isoformat()}*
"""

    # ==================================================================
    # INTERNAL HELPERS
    # ==================================================================

    async def _init_compliance_matrix(self, project_id: str, regulation_list: list[str]) -> None:
        """Create initial compliance items from regulation list."""
        now = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            for i, clause in enumerate(regulation_list):
                clause_id = f"{project_id}-{i:03d}"
                await db.execute("""
                    INSERT OR IGNORE INTO compliance_items
                        (project_id, clause_id, clause_ref, title, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'unverified', ?, ?)
                """, (project_id, clause_id, clause, clause, now, now))
            await db.commit()


# ======================================================================
# SQL SCHEMA
# ======================================================================

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'custom',
    vessel_type TEXT,
    dwt INTEGER,
    primary_class TEXT NOT NULL DEFAULT '',
    secondary_class TEXT DEFAULT '',
    regulation_year TEXT DEFAULT '2025',
    phase TEXT DEFAULT 'design',
    disciplines TEXT DEFAULT '[]',
    description TEXT DEFAULT '',
    owner_id TEXT NOT NULL,
    team_members TEXT DEFAULT '[]',
    regulation_list TEXT DEFAULT '[]',
    tags TEXT DEFAULT '[]',
    is_archived INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS project_conversations (
    project_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    folder_path TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    order_index INTEGER DEFAULT 0,
    linked_since REAL NOT NULL,
    PRIMARY KEY (project_id, conversation_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_documents (
    project_id TEXT NOT NULL,
    document_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    discipline TEXT,
    parse_status TEXT DEFAULT 'pending',
    parse_result_json TEXT,
    file_key TEXT,
    version INTEGER DEFAULT 1,
    uploaded_by TEXT,
    uploaded_at REAL NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS research_issues (
    issue_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    priority TEXT DEFAULT 'medium',
    assignee TEXT,
    related_conversation_id TEXT,
    related_document_id TEXT,
    related_regulation TEXT,
    deadline REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_conclusions (
    conclusion_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    text TEXT NOT NULL,
    detail TEXT,
    source_type TEXT DEFAULT 'manual',
    source_conversation_id TEXT,
    source_report_id TEXT,
    citation TEXT DEFAULT '[]',
    status TEXT DEFAULT 'general',
    tags TEXT DEFAULT '[]',
    created_at REAL NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS compliance_items (
    project_id TEXT NOT NULL,
    clause_id TEXT NOT NULL,
    clause_ref TEXT NOT NULL,
    title TEXT,
    status TEXT DEFAULT 'unverified',
    verified_by TEXT,
    verified_at REAL,
    deviation_note TEXT,
    linked_conclusions TEXT DEFAULT '[]',
    linked_conversations TEXT DEFAULT '[]',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (project_id, clause_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
"""


_JSON_FIELDS = {"disciplines", "team_members", "regulation_list", "tags",
                "parse_result_json", "citation", "linked_conclusions",
                "linked_conversations"}


def _row_to_dict(row, cursor=None) -> dict:
    """Convert aiosqlite Row to dict using cursor description for column names."""
    if row is None:
        return {}
    try:
        if cursor and cursor.description:
            cols = [c[0] for c in cursor.description]
            d = {cols[i]: row[i] for i in range(len(cols))}
        else:
            d = {k: row[k] for k in row.keys()}
        # Deserialize known JSON fields
        for field in _JSON_FIELDS:
            if field in d and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
    except Exception as e:
        logger.warning("Failed to deserialize row: %s", e)
        return {}
