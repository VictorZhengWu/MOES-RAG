"""
Mock data generators for the Mock Server.

WHY: All mock data must be realistic enough that M6 and M7 frontend
developers can test UI rendering properly. Placeholder text like
"lorem ipsum" won't reveal layout bugs with actual maritime content.
Realistic fake data with classification society names, clause
references, and domain terminology catches these issues early.

Every generator function returns data matching a contracts/ schema.
"""

import json
import time
import uuid
from datetime import datetime, timezone


def now_iso() -> str:
    """Current UTC time as ISO 8601 string.

    WHY: Timestamps in API responses must be ISO 8601 formatted
    for frontend date parsing libraries (dayjs, date-fns) to
    work correctly across all 5 supported locales.
    """
    return datetime.now(timezone.utc).isoformat()


def generate_id(prefix: str = "") -> str:
    """Generate a short unique ID with an optional prefix.

    WHY: 12-char hex IDs are long enough to avoid collisions in mock
    data (probability < 10^-7 for < 1000 items) while being short
    enough for readable API responses during debugging.
    """
    uid = uuid.uuid4().hex[:12]
    return f"{prefix}_{uid}" if prefix else uid


# ── Chat Mock Data ──────────────────────────────────────────────────

def mock_chat_response(query: str) -> dict:
    """
    Generate a fake chat completion response.

    The response includes realistic marine engineering citations
    so M6 can test citation rendering and link formatting.
    """
    return {
        "id": f"chatcmpl-{generate_id()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "marine-rag-mock",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": (
                    "According to DNV Rules for Classification of Ships, "
                    "Pt.4 Ch.3 Section 5, the scantlings of the cargo tank "
                    "boundary structures for LNG carriers shall be determined "
                    "based on the design vapour pressure and the dynamic loads "
                    "due to liquid motion. The minimum design temperature for "
                    "the inner hull shall account for the cargo temperature of "
                    "-163°C for LNG.\n\n"
                    "ABS Rules for Building and Classing Steel Vessels (Pt.5B, "
                    "Section 3-2) have equivalent requirements, with additional "
                    "guidance on fatigue assessment of the cargo containment "
                    "system under sloshing loads."
                ),
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 156,
            "completion_tokens": 142,
            "total_tokens": 298,
        },
        "citations": [
            {
                "index": 1,
                "source_doc": "DNV Rules for Classification of Ships",
                "section": "Pt.4 Ch.3 Sec.5",
                "clause_id": "5.2.3",
                "excerpt": (
                    "The scantlings of cargo tank boundary structures shall..."
                ),
            },
            {
                "index": 2,
                "source_doc": "ABS Rules for Building and Classing Steel Vessels",
                "section": "Pt.5B Sec.3-2",
                "clause_id": "3-2/5.1",
                "excerpt": (
                    "Fatigue assessment of the cargo containment system..."
                ),
            },
        ],
    }


def mock_stream_chunks(query: str) -> list[str]:
    """
    Generate simulated SSE streaming chunks as raw JSON strings.

    WHY: M6's streaming UI needs realistic token-by-token output
    to verify real-time rendering. Returning pre-split tokens
    simulates what a real LLM stream would produce. Chunks are
    raw JSON strings — the SSE framing (data: prefix, \\n\\n suffix)
    is added by EventSourceResponse in routes_chat.py.

    The last element is the string "[DONE]" to signal stream end.
    """
    text = mock_chat_response(query)["choices"][0]["message"]["content"]
    words = text.split()
    chunks = []
    for i, word in enumerate(words):
        chunk = {
            "id": f"chatcmpl-stream-{generate_id()}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "marine-rag-mock",
            "choices": [{
                "index": 0,
                "delta": {"content": word + " "},
                "finish_reason": None if i < len(words) - 1 else "stop",
            }],
        }
        chunks.append(json.dumps(chunk))
    # Append citations as a metadata chunk before [DONE]
    citations = mock_chat_response(query).get("citations", [])
    if citations:
        citation_chunk = {
            "id": f"chatcmpl-citations-{generate_id()}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "marine-rag-mock",
            "choices": [],
            "citations": citations,
        }
        chunks.append(json.dumps(citation_chunk))
    chunks.append("[DONE]")
    return chunks


# ── Conversation Mock Data ──────────────────────────────────────────

def mock_conversations() -> list[dict]:
    """Generate a list of fake conversation summaries."""
    return [
        {
            "conversation_id": "conv_lng_tank_design",
            "title": "LNG cargo tank structural requirements",
            "created_at": "2026-05-10T08:30:00Z",
            "updated_at": "2026-05-10T09:15:00Z",
            "message_count": 12,
        },
        {
            "conversation_id": "conv_dnv_abs_comparison",
            "title": "DNV vs ABS — bulk carrier hatch cover rules",
            "created_at": "2026-05-09T14:00:00Z",
            "updated_at": "2026-05-09T14:45:00Z",
            "message_count": 8,
        },
        {
            "conversation_id": "conv_ballast_system",
            "title": "Ballast water treatment system requirements",
            "created_at": "2026-05-08T10:00:00Z",
            "updated_at": "2026-05-08T11:30:00Z",
            "message_count": 15,
        },
    ]


def mock_conversation_messages(conv_id: str) -> list[dict]:
    """Generate fake conversation message history."""
    return [
        {
            "role": "user",
            "content": (
                "What are DNV requirements for LNG cargo tank structures?"
            ),
        },
        {
            "role": "assistant",
            "content": (
                "According to DNV Pt.4 Ch.3 Sec.5, the cargo tank boundary "
                "structures shall..."
            ),
        },
        {
            "role": "user",
            "content": "How does ABS compare on the same topic?",
        },
        {
            "role": "assistant",
            "content": (
                "ABS Pt.5B Sec.3-2 has equivalent requirements with additional "
                "guidance on fatigue..."
            ),
        },
    ]


# ── Admin: Document Mock Data ───────────────────────────────────────

def mock_parse_task() -> dict:
    """Generate a fake document parse task status."""
    return {
        "task_id": generate_id("task"),
        "doc_id": generate_id("doc"),
        "status": "completed",
        "progress_pct": 100.0,
        "chunks_count": 47,
        "error_message": None,
        "started_at": now_iso(),
        "completed_at": now_iso(),
    }


def mock_documents() -> list[dict]:
    """Generate a list of fake ingested documents."""
    return [
        {
            "doc_id": "doc_dnv_pt4_2024",
            "source_filename": "DNV-RU-SHIP-Pt4Ch3-2024.pdf",
            "classification_society": "DNV",
            "regulation_name": "Rules for Classification of Ships",
            "version_year": 2024,
            "domain": "structure",
            "chunks_count": 312,
            "ingested_at": "2026-05-01T10:00:00Z",
            "status": "active",
        },
        {
            "doc_id": "doc_abs_pt5b_2024",
            "source_filename": "ABS-Rules-Pt5B-2024.pdf",
            "classification_society": "ABS",
            "regulation_name": "Rules for Building and Classing Steel Vessels",
            "version_year": 2024,
            "domain": "structure",
            "chunks_count": 278,
            "ingested_at": "2026-05-02T10:00:00Z",
            "status": "active",
        },
        {
            "doc_id": "doc_imo_ballast_2023",
            "source_filename": "IMO-BWMS-Code-2023.pdf",
            "classification_society": "IMO",
            "regulation_name": "Ballast Water Management Convention",
            "version_year": 2023,
            "domain": "machinery",
            "chunks_count": 156,
            "ingested_at": "2026-05-03T10:00:00Z",
            "status": "active",
        },
    ]


# ── Admin: KG Mock Data ─────────────────────────────────────────────

def mock_kg_entities() -> list[dict]:
    """Generate fake knowledge graph entities."""
    return [
        {
            "entity_id": "ent_lng_cargo_tank",
            "name": "LNG Cargo Tank",
            "entity_type": "equipment",
            "properties": {"design_temp_c": -163, "material": "9% Ni steel"},
            "source_doc_id": "doc_dnv_pt4_2024",
        },
        {
            "entity_id": "ent_dnv_pt4_ch3_sec5",
            "name": "DNV Pt.4 Ch.3 Sec.5 — Cargo Tank Boundaries",
            "entity_type": "regulation_clause",
            "properties": {"society": "DNV", "version": 2024},
            "source_doc_id": "doc_dnv_pt4_2024",
        },
        {
            "entity_id": "ent_abs_pt5b_sec32",
            "name": "ABS Pt.5B Sec.3-2 — LNG Cargo Containment",
            "entity_type": "regulation_clause",
            "properties": {"society": "ABS", "version": 2024},
            "source_doc_id": "doc_abs_pt5b_2024",
        },
    ]


def mock_kg_relations() -> list[dict]:
    """Generate fake knowledge graph relations."""
    return [
        {
            "relation_id": "rel_01",
            "source_entity_id": "ent_dnv_pt4_ch3_sec5",
            "target_entity_id": "ent_lng_cargo_tank",
            "relation_type": "regulates",
            "source_entity_name": "DNV Pt.4 Ch.3 Sec.5",
            "target_entity_name": "LNG Cargo Tank",
            "confidence": 0.98,
        },
        {
            "relation_id": "rel_02",
            "source_entity_id": "ent_dnv_pt4_ch3_sec5",
            "target_entity_id": "ent_abs_pt5b_sec32",
            "relation_type": "equivalent_to",
            "source_entity_name": "DNV Pt.4 Ch.3 Sec.5",
            "target_entity_name": "ABS Pt.5B Sec.3-2",
            "confidence": 0.92,
        },
    ]


# ── Admin: LLM Backend Mock Data ─────────────────────────────────────

def mock_llm_backends() -> list[dict]:
    """Generate fake LLM backend configurations with purpose classification."""
    return [
        {
            "backend_id": "deepseek-chat",
            "backend_type": "deepseek",
            "model_name": "deepseek-chat",
            "purpose": "chat",
            "base_url": "https://api.deepseek.com",
            "api_key": None,
            "max_tokens": 4096,
            "temperature": 0.7,
            "is_default": True,
            "assigned_agents": ["structure", "machinery", "piping"],
        },
        {
            "backend_id": "deepseek-reasoner",
            "backend_type": "deepseek",
            "model_name": "deepseek-reasoner",
            "purpose": "thinking",
            "base_url": "https://api.deepseek.com",
            "api_key": None,
            "max_tokens": 32768,
            "temperature": 0.3,
            "is_default": False,
            "assigned_agents": ["structure", "machinery", "piping", "electrical", "communication", "automation"],
        },
        {
            "backend_id": "bge-m3-embed",
            "backend_type": "ollama",
            "model_name": "bge-m3",
            "purpose": "embedding",
            "base_url": "http://localhost:11434",
            "api_key": None,
            "max_tokens": 8192,
            "temperature": 0.0,
            "is_default": False,
            "assigned_agents": [],
        },
        {
            "backend_id": "bge-reranker",
            "backend_type": "ollama",
            "model_name": "bge-reranker-v2-m3",
            "purpose": "reranking",
            "base_url": "http://localhost:11434",
            "api_key": None,
            "max_tokens": 8192,
            "temperature": 0.0,
            "is_default": False,
            "assigned_agents": [],
        },
        {
            "backend_id": "gpt4o-vision",
            "backend_type": "openai",
            "model_name": "gpt-4o",
            "purpose": "vision",
            "base_url": "https://api.openai.com",
            "api_key": None,
            "max_tokens": 4096,
            "temperature": 0.3,
            "is_default": False,
            "assigned_agents": ["structure", "piping", "electrical"],
        },
    ]


# ── Admin: Misc Mock Data ───────────────────────────────────────────

def mock_users() -> list[dict]:
    """Generate fake admin user list."""
    return [
        {
            "user_id": "user_admin_01",
            "username": "admin",
            "email": "admin@shipyard.no",
            "role": "admin",
            "is_active": True,
            "api_key_count": 2,
            "total_queries": 1250,
            "created_at": "2026-01-15T08:00:00Z",
        },
        {
            "user_id": "user_editor_01",
            "username": "editor_li",
            "email": "li.wang@shipyard.cn",
            "role": "editor",
            "is_active": True,
            "api_key_count": 1,
            "total_queries": 340,
            "created_at": "2026-02-20T09:00:00Z",
        },
    ]


def mock_system_stats() -> dict:
    """Generate fake system statistics for the admin dashboard."""
    return {
        "total_documents": 47,
        "total_chunks": 12850,
        "total_entities": 3821,
        "total_relations": 7842,
        "total_conversations": 215,
        "total_users": 12,
        "storage_size_bytes": 2_147_483_648,  # 2 GB
        "avg_retrieval_latency_ms": 245.3,
    }
