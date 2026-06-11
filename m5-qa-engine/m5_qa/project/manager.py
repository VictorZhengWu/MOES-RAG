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
    except Exception:
        return {}
