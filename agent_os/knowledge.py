"""knowledge.py — Knowledge base routes for Agent OS.

Tenant-scoped CRUD for organizational knowledge:
    GET    /api/agent-os/knowledge — list entries
    POST   /api/agent-os/knowledge — create entry
    GET    /api/agent-os/knowledge/{id} — get single
    PATCH  /api/agent-os/knowledge/{id} — update
    DELETE /api/agent-os/knowledge/{id} — delete
    GET    /api/agent-os/knowledge/search?q=... — full-text search

Design:
    - All routes are tenant-scoped (auth.tenant_id).
    - Stdlib-only.
    - Entry types: decision, sop, research, feedback, custom.
    - Search uses LIKE-based full-text scan (stdlib, no external index).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from .auth import AuthContext, SessionStore, extract_bearer_token

log = logging.getLogger(__name__)

ENTRY_TYPES = ["decision", "sop", "research", "feedback", "custom"]


def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return status, payload


def _error(status: int, message: str) -> tuple[int, dict[str, Any]]:
    return status, {"error": message}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_knowledge_routes(
    store: Any = None,
    session_store: SessionStore | None = None,
    get_auth: Callable[[dict[str, Any] | None], AuthContext] | None = None,
) -> dict[tuple[str, str], Callable]:
    """Create knowledge base route handlers."""
    _session_store = session_store or SessionStore()

    def _resolve_auth(body: Any, headers: dict[str, str] | None) -> AuthContext:
        """Resolve auth from bearer <REDACTED>."""
        if headers:
            token = extract_bearer_token(headers.get("Authorization"))
            if token:
                session = _session_store.get_session(token)
                if session:
                    return session
        return AuthContext(email="", tenant_id=None)

    def _resolve_tenant_id(body: dict[str, Any] | None, headers: dict[str, str] | None) -> tuple[AuthContext, str | None]:
        """Resolve auth and tenant_id."""
        auth = _resolve_auth(body, headers)
        if not auth.is_authenticated:
            return auth, None
        return auth, auth.tenant_id

    def list_knowledge(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/knowledge — list entries for tenant."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            entry_type = None
            limit = 50
            offset = 0
            if body:
                if body.get("entryType"):
                    entry_type = body["entryType"]
                if body.get("limit"):
                    limit = min(int(body["limit"]), 200)
                if body.get("offset"):
                    offset = int(body["offset"])

            where_clauses = ["tenant_id = ?"]
            params: list[Any] = [tenant_id]

            if entry_type:
                where_clauses.append("entry_type = ?")
                params.append(entry_type)

            where_sql = " AND ".join(where_clauses)

            total_cursor = conn.execute(
                f"SELECT COUNT(*) FROM knowledge_entries WHERE {where_sql}", params
            )
            total = total_cursor.fetchone()[0]

            params.extend([limit, offset])
            cursor = conn.execute(
                f"SELECT * FROM knowledge_entries WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            )
            entries = [dict(r) for r in cursor.fetchall()]

            return _json_response(200, {
                "entries": entries,
                "count": len(entries),
                "total": total,
                "limit": limit,
                "offset": offset,
            })
        except Exception as e:
            log.exception("Failed to list knowledge entries")
            return _error(500, str(e))

    def create_knowledge(body: dict[str, Any], headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/knowledge — create an entry."""
        try:
            if not body or not isinstance(body, dict):
                return _error(400, "body must be a JSON object")

            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            title = (body.get("title") or "").strip()
            if not title:
                return _error(400, "title is required")
            if len(title) > 500:
                return _error(400, "title max 500 chars")

            content = (body.get("content") or "").strip()
            if not content:
                return _error(400, "content is required")
            if len(content) > 50000:
                return _error(400, "content max 50000 chars")

            entry_type = body.get("entryType", "decision")
            if entry_type not in ENTRY_TYPES:
                return _error(400, f"entryType must be one of: {', '.join(ENTRY_TYPES)}")

            metadata = body.get("metadata", {})
            if not isinstance(metadata, dict):
                return _error(400, "metadata must be an object")

            knowledge_id = str(uuid.uuid4())
            now = _now()

            store._get_conn().execute(
                """INSERT INTO knowledge_entries
                   (id, tenant_id, entry_type, title, content, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (knowledge_id, tenant_id, entry_type, title, content, json.dumps(metadata), now),
            )
            store._get_conn().commit()

            return _json_response(201, {
                "id": knowledge_id,
                "title": title,
                "content": content,
                "entry_type": entry_type,
                "metadata": metadata,
                "created_at": now,
            })
        except Exception as e:
            log.exception("Failed to create knowledge entry")
            return _error(500, str(e))

    def get_knowledge(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/knowledge/{id} — get single entry."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            entry_id = path_params.get("id", "")
            if not entry_id:
                return _error(400, "id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM knowledge_entries WHERE id = ? AND tenant_id = ?",
                (entry_id, tenant_id),
            )
            row = cursor.fetchone()
            if not row:
                return _error(404, "Knowledge entry not found")

            return _json_response(200, dict(row))
        except Exception as e:
            log.exception("Failed to get knowledge entry")
            return _error(500, str(e))

    def update_knowledge(body: dict[str, Any], headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """PATCH /api/agent-os/knowledge/{id} — update an entry."""
        try:
            if not body or not isinstance(body, dict):
                return _error(400, "body must be a JSON object")

            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            entry_id = path_params.get("id", "")
            if not entry_id:
                return _error(400, "id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            existing = conn.execute(
                "SELECT * FROM knowledge_entries WHERE id = ? AND tenant_id = ?",
                (entry_id, tenant_id),
            ).fetchone()
            if not existing:
                return _error(404, "Knowledge entry not found")

            updates = []
            params: list[Any] = []

            if "title" in body:
                title = body["title"].strip() if body["title"] else ""
                if not title:
                    return _error(400, "title cannot be empty")
                if len(title) > 500:
                    return _error(400, "title max 500 chars")
                updates.append("title = ?")
                params.append(title)

            if "content" in body:
                content = body["content"].strip() if body["content"] else ""
                if not content:
                    return _error(400, "content cannot be empty")
                if len(content) > 50000:
                    return _error(400, "content max 50000 chars")
                updates.append("content = ?")
                params.append(content)

            if "entryType" in body:
                if body["entryType"] not in ENTRY_TYPES:
                    return _error(400, f"entryType must be one of: {', '.join(ENTRY_TYPES)}")
                updates.append("entry_type = ?")
                params.append(body["entryType"])

            if "metadata" in body:
                if not isinstance(body["metadata"], dict):
                    return _error(400, "metadata must be an object")
                updates.append("metadata = ?")
                params.append(json.dumps(body["metadata"]))

            if not updates:
                return _error(400, "no valid fields to update")

            updates.append("created_at = ?")
            params.append(_now())

            params.extend([entry_id, tenant_id])
            conn.execute(
                f"UPDATE knowledge_entries SET {', '.join(updates)} WHERE id = ? AND tenant_id = ?",
                params,
            )
            conn.commit()

            cursor = conn.execute(
                "SELECT * FROM knowledge_entries WHERE id = ? AND tenant_id = ?",
                (entry_id, tenant_id),
            )
            return _json_response(200, dict(cursor.fetchone()))
        except Exception as e:
            log.exception("Failed to update knowledge entry")
            return _error(500, str(e))

    def delete_knowledge(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """DELETE /api/agent-os/knowledge/{id} — delete an entry."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            entry_id = path_params.get("id", "")
            if not entry_id:
                return _error(400, "id required")

            conn = store._get_conn()
            cursor = conn.execute(
                "DELETE FROM knowledge_entries WHERE id = ? AND tenant_id = ?",
                (entry_id, tenant_id),
            )
            conn.commit()

            if cursor.rowcount == 0:
                return _error(404, "Knowledge entry not found")

            return _json_response(200, {"deleted": True, "id": entry_id})
        except Exception as e:
            log.exception("Failed to delete knowledge entry")
            return _error(500, str(e))

    def search_knowledge(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/knowledge/search?q=... — full-text search."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            query = ""
            # Try body first, then query string
            if body and body.get("q"):
                query = body["q"].strip()
            elif "?" in (headers.get("_path", "") if headers else ""):
                from urllib.parse import parse_qs
                qs = parse_qs(headers["_path"].split("?")[1])
                if "q" in qs:
                    query = qs["q"][0].strip()

            if not query:
                return _error(400, "q parameter is required")

            if len(query) > 200:
                return _error(400, "q max 200 chars")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            search_pattern = f"%{query}%"
            cursor = conn.execute(
                """SELECT * FROM knowledge_entries
                   WHERE tenant_id = ? AND (title LIKE ? OR content LIKE ?)
                   ORDER BY created_at DESC LIMIT 50""",
                (tenant_id, search_pattern, search_pattern),
            )
            entries = [dict(r) for r in cursor.fetchall()]

            return _json_response(200, {
                "entries": entries,
                "count": len(entries),
                "query": query,
            })
        except Exception as e:
            log.exception("Failed to search knowledge entries")
            return _error(500, str(e))

    routes: dict[tuple[str, str], Callable] = {
        ("GET", "/api/agent-os/knowledge"): list_knowledge,
        ("POST", "/api/agent-os/knowledge"): create_knowledge,
        # search MUST be registered before {id} so literal route wins
        ("GET", "/api/agent-os/knowledge/search"): search_knowledge,
        ("GET", "/api/agent-os/knowledge/{id}"): get_knowledge,
        ("PATCH", "/api/agent-os/knowledge/{id}"): update_knowledge,
        ("DELETE", "/api/agent-os/knowledge/{id}"): delete_knowledge,
    }
    return routes
