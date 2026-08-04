"""engagements.py — Engagement management routes for Agent OS.

Tenant-scoped endpoints:
    GET  /api/agent-os/engagements — list engagements
    POST /api/agent-os/engagements — create engagement
    GET  /api/agent-os/engagements/{id} — get engagement with assessments
    PATCH /api/agent-os/engagements/{id} — update engagement
    DELETE /api/agent-os/engagements/{id} — delete engagement
    GET  /api/agent-os/engagements/{id}/notes — list notes
    POST /api/agent-os/engagements/{id}/notes — add note

Design:
    - All routes are tenant-scoped. The tenant is resolved from
      the authenticated session (Authorization header), NOT from request body.
    - All routes require authentication (token-guarded, same as daemon).
    - Stdlib-only: matches the daemon's no-dependency approach.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from .auth import AuthContext

log = logging.getLogger(__name__)

# Validation constants
ENGAGEMENT_TYPES = ["gap_assessment", "full_readiness", "mock_c3pao", "continuous", "remediation"]
ENGAGEMENT_STATUSES = ["active", "paused", "completed", "archived"]
TARGET_CMMC_LEVELS = ["L1", "L2_self", "L2_c3pao"]
BILLING_MODELS = ["fixed_fee", "time_materials", "retainer"]
UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return status, payload


def _error(status: int, message: str) -> tuple[int, dict[str, Any]]:
    return status, {"error": message}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_date(s: str) -> str | None:
    """Parse ISO date string, return ISO format or None."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).isoformat()
    except (ValueError, AttributeError):
        return None


def _validate_uuid(val: str | None) -> bool:
    return bool(val and UUID_REGEX.match(val))


def create_engagement_routes(
    store: Any,  # AgentOSStore — has _get_conn() -> sqlite3.Connection
    get_auth: Callable[[dict[str, Any] | None], AuthContext],
) -> dict[tuple[str, str], Callable]:
    """Create engagement route handlers.
    Returns a dict of {(method, path): handler}.
    """

    def list_engagements(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/engagements — list all engagements for tenant."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM engagements WHERE tenant_id = ? ORDER BY updated_at DESC",
                (tenant_id,)
            )
            engagements = [dict(row) for row in cursor.fetchall()]

            return _json_response(200, {"status": "success", "data": {"engagements": engagements}})
        except Exception as e:
            log.exception("Failed to list engagements")
            return _error(500, str(e))

    def get_engagement(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/engagements/{id} — get single engagement."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            engagement_id = path_params.get("id", "")
            if not engagement_id:
                return _error(400, "id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM engagements WHERE id = ? AND tenant_id = ?",
                (engagement_id, tenant_id)
            )
            row = cursor.fetchone()
            if not row:
                return _error(404, "Engagement not found")

            engagement = dict(row)

            # Parse JSON fields
            if engagement.get("assigned_assessors"):
                try:
                    engagement["assigned_assessors"] = json.loads(engagement["assigned_assessors"])
                except (json.JSONDecodeError, TypeError):
                    engagement["assigned_assessors"] = []

            # Get notes
            notes_cursor = conn.execute(
                "SELECT * FROM engagement_notes WHERE engagement_id = ? ORDER BY created_at DESC",
                (engagement_id,)
            )
            engagement["notes"] = [dict(r) for r in notes_cursor.fetchall()]

            return _json_response(200, {"status": "success", "data": {"engagement": engagement}})
        except Exception as e:
            log.exception("Failed to get engagement")
            return _error(500, str(e))

    def create_engagement(body: dict[str, Any], **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/engagements — create an engagement."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            # Validate required fields
            name = (body.get("name") or "").strip()
            if not name:
                return _error(400, "name is required")

            client_id = body.get("clientId")
            if not client_id or not _validate_uuid(client_id):
                return _error(400, "clientId must be a valid UUID")

            # Optional fields with defaults
            eng_type = (body.get("type") or "gap_assessment").strip()
            if eng_type not in ENGAGEMENT_TYPES:
                return _error(400, f"type must be one of: {', '.join(ENGAGEMENT_TYPES)}")

            target_level = (body.get("targetCmmcLevel") or "L2_self").strip()
            if target_level not in TARGET_CMMC_LEVELS:
                return _error(400, f"targetCmmcLevel must be one of: {', '.join(TARGET_CMMC_LEVELS)}")

            status = (body.get("status") or "active").strip()
            if status not in ENGAGEMENT_STATUSES:
                return _error(400, f"status must be one of: {', '.join(ENGAGEMENT_STATUSES)}")

            # Date fields
            start_date = _parse_date(body.get("startDate")) if body.get("startDate") else None
            target_end = _parse_date(body.get("targetEndDate")) if body.get("targetEndDate") else None
            actual_end = _parse_date(body.get("actualEndDate")) if body.get("actualEndDate") else None

            # String fields
            engagement_owner = body.get("engagementOwner")
            assigned_assessors = body.get("assignedAssessors")
            if assigned_assessors and isinstance(assigned_assessors, list):
                if len(assigned_assessors) > 20:
                    return _error(400, "assignedAssessors max 20 items")
                assigned_assessors = json.dumps(assigned_assessors)
            coi_declared = 1 if body.get("coiDeclared") else 0
            nda_signed = 1 if body.get("ndaSigned") else 0
            msa_signed = 1 if body.get("msaSigned") else 0
            sow_reference = body.get("sowReference")

            billing_model = body.get("billingModel")
            if billing_model and billing_model not in BILLING_MODELS:
                return _error(400, f"billingModel must be one of: {', '.join(BILLING_MODELS)}")

            notes = body.get("notes")

            engagement_id = str(uuid.uuid4())
            now = _now()

            conn = store._get_conn()
            conn.execute(
                """INSERT INTO engagements 
                   (id, tenant_id, client_id, name, type, target_cmmc_level, status,
                    start_date, target_end_date, actual_end_date, engagement_owner,
                    assigned_assessors, coi_declared, nda_signed, msa_signed,
                    sow_reference, billing_model, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (engagement_id, tenant_id, client_id, name, eng_type, target_level, status,
                 start_date, target_end, actual_end, engagement_owner,
                 assigned_assessors, coi_declared, nda_signed, msa_signed,
                 sow_reference, billing_model, notes, now, now)
            )
            conn.commit()

            return _json_response(201, {
                "status": "success",
                "data": {"engagement": {"id": engagement_id, "name": name, "status": status}},
                "message": "Engagement created"
            })
        except Exception as e:
            log.exception("Failed to create engagement")
            return _error(500, str(e))

    def update_engagement(body: dict[str, Any], **path_params: str) -> tuple[int, dict[str, Any]]:
        """PATCH /api/agent-os/engagements/{id} — update an engagement."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            engagement_id = path_params.get("id", "")
            if not engagement_id:
                return _error(400, "id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            # Check exists
            cursor = conn.execute(
                "SELECT id FROM engagements WHERE id = ? AND tenant_id = ?",
                (engagement_id, tenant_id)
            )
            if not cursor.fetchone():
                return _error(404, "Engagement not found")

            # Build update fields
            updates = []
            values = []

            field_map = {
                "name": ("name", str),
                "type": ("type", str),
                "targetCmmcLevel": ("target_cmmc_level", str),
                "status": ("status", str),
                "engagementOwner": ("engagement_owner", str),
                "sowReference": ("sow_reference", str),
                "billingModel": ("billing_model", str),
                "notes": ("notes", str),
            }

            for json_field, (db_field, field_type) in field_map.items():
                if json_field in body:
                    val = body[json_field]
                    if field_type == str:
                        val = (val or "").strip()
                        # Validate enum fields
                        if json_field == "type" and val and val not in ENGAGEMENT_TYPES:
                            return _error(400, f"type must be one of: {', '.join(ENGAGEMENT_TYPES)}")
                        if json_field == "targetCmmcLevel" and val and val not in TARGET_CMMC_LEVELS:
                            return _error(400, f"targetCmmcLevel must be one of: {', '.join(TARGET_CMMC_LEVELS)}")
                        if json_field == "status" and val and val not in ENGAGEMENT_STATUSES:
                            return _error(400, f"status must be one of: {', '.join(ENGAGEMENT_STATUSES)}")
                        if json_field == "billingModel" and val and val not in BILLING_MODELS:
                            return _error(400, f"billingModel must be one of: {', '.join(BILLING_MODELS)}")
                    updates.append(f"{db_field} = ?")
                    values.append(val)

            # Date fields
            if "startDate" in body:
                updates.append("start_date = ?")
                values.append(_parse_date(body["startDate"]))
            if "targetEndDate" in body:
                updates.append("target_end_date = ?")
                values.append(_parse_date(body["targetEndDate"]))
            if "actualEndDate" in body:
                updates.append("actual_end_date = ?")
                values.append(_parse_date(body["actualEndDate"]))

            # Boolean fields
            if "coiDeclared" in body:
                updates.append("coi_declared = ?")
                values.append(1 if body["coiDeclared"] else 0)
            if "ndaSigned" in body:
                updates.append("nda_signed = ?")
                values.append(1 if body["ndaSigned"] else 0)
            if "msaSigned" in body:
                updates.append("msa_signed = ?")
                values.append(1 if body["msaSigned"] else 0)

            # JSON array
            if "assignedAssessors" in body:
                aa = body["assignedAssessors"]
                if aa and isinstance(aa, list):
                    if len(aa) > 20:
                        return _error(400, "assignedAssessors max 20 items")
                    updates.append("assigned_assessors = ?")
                    values.append(json.dumps(aa))

            if not updates:
                return _error(400, "no fields to update")

            updates.append("updated_at = ?")
            values.append(_now())
            values.extend([engagement_id, tenant_id])

            conn.execute(
                f"UPDATE engagements SET {', '.join(updates)} WHERE id = ? AND tenant_id = ?",
                values
            )
            conn.commit()

            return _json_response(200, {"status": "success", "message": "Engagement updated"})
        except Exception as e:
            log.exception("Failed to update engagement")
            return _error(500, str(e))

    def delete_engagement(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """DELETE /api/agent-os/engagements/{id} — remove an engagement."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            engagement_id = path_params.get("id", "")
            if not engagement_id:
                return _error(400, "id required")

            conn = store._get_conn()
            cursor = conn.execute(
                "SELECT id FROM engagements WHERE id = ? AND tenant_id = ?",
                (engagement_id, tenant_id)
            )
            if not cursor.fetchone():
                return _error(404, "Engagement not found")

            # Delete notes first
            conn.execute("DELETE FROM engagement_notes WHERE engagement_id = ?", (engagement_id,))
            conn.execute("DELETE FROM engagements WHERE id = ?", (engagement_id,))
            conn.commit()

            return _json_response(200, {"status": "success", "message": "Engagement deleted"})
        except Exception as e:
            log.exception("Failed to delete engagement")
            return _error(500, str(e))

    def list_notes(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/engagements/{id}/notes — list notes for an engagement."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            engagement_id = path_params.get("id", "")
            if not engagement_id:
                return _error(400, "id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            # Verify engagement belongs to tenant
            cursor = conn.execute(
                "SELECT id FROM engagements WHERE id = ? AND tenant_id = ?",
                (engagement_id, tenant_id)
            )
            if not cursor.fetchone():
                return _error(404, "Engagement not found")

            cursor = conn.execute(
                "SELECT * FROM engagement_notes WHERE engagement_id = ? ORDER BY created_at DESC",
                (engagement_id,)
            )
            notes = [dict(row) for row in cursor.fetchall()]

            return _json_response(200, {"status": "success", "data": {"notes": notes}})
        except Exception as e:
            log.exception("Failed to list notes")
            return _error(500, str(e))

    def add_note(body: dict[str, Any], **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/engagements/{id}/notes — add a note to an engagement."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            engagement_id = path_params.get("id", "")
            if not engagement_id:
                return _error(400, "id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            # Verify engagement belongs to tenant
            cursor = conn.execute(
                "SELECT id FROM engagements WHERE id = ? AND tenant_id = ?",
                (engagement_id, tenant_id)
            )
            if not cursor.fetchone():
                return _error(404, "Engagement not found")

            content = (body.get("content") or "").strip()
            if not content:
                return _error(400, "content is required")
            if len(content) > 2000:
                return _error(400, "content max 2000 chars")

            author = (body.get("author") or auth.email or "unknown").strip()

            note_id = str(uuid.uuid4())
            now = _now()

            conn.execute(
                """INSERT INTO engagement_notes 
                   (id, engagement_id, content, author, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (note_id, engagement_id, content, author, now)
            )
            conn.commit()

            return _json_response(201, {
                "status": "success",
                "data": {"note": {"id": note_id, "content": content, "author": author}},
                "message": "Note added"
            })
        except Exception as e:
            log.exception("Failed to add note")
            return _error(500, str(e))

    routes: dict[tuple[str, str], Callable] = {
        ("GET", "/api/agent-os/engagements"): list_engagements,
        ("GET", "/api/agent-os/engagements/{id}"): get_engagement,
        ("POST", "/api/agent-os/engagements"): create_engagement,
        ("PATCH", "/api/agent-os/engagements/{id}"): update_engagement,
        ("DELETE", "/api/agent-os/engagements/{id}"): delete_engagement,
        ("GET", "/api/agent-os/engagements/{id}/notes"): list_notes,
        ("POST", "/api/agent-os/engagements/{id}/notes"): add_note,
    }

    return routes
