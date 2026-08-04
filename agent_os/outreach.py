"""outreach.py — Outreach lead pipeline routes for Agent OS.

Tenant-scoped endpoints:
    GET  /api/agent-os/outreach/leads — list leads
    POST /api/agent-os/outreach/leads — create lead
    GET  /api/agent-os/outreach/stats — pipeline counts
    GET  /api/agent-os/outreach/leads/{id} — get lead with activities
    PATCH /api/agent-os/outreach/leads/{id} — update lead
    DELETE /api/agent-os/outreach/leads/{id} — delete lead
    GET  /api/agent-os/outreach/leads/{id}/activities — list activities
    POST /api/agent-os/outreach/leads/{id}/activities — log activity

Design:
    - All routes are tenant-scoped. The tenant is resolved from
      the authenticated session (Authorization header), NOT from request body.
    - All routes require authentication (token-guarded, same as daemon).
    - Stdlib-only: matches the daemon's no-dependency approach.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from .auth import AuthContext

log = logging.getLogger(__name__)

# Validation constants
OUTREACH_SOURCES = ["sam_gov", "linkedin", "ptac", "sba_score", "trade_show", "referral", "manual"]
OUTREACH_STATUSES = ["identified", "contacted", "interested", "meeting", "trial", "customer", "lost"]
ACTIVITY_TYPES = ["email", "call", "meeting", "note"]
ACTIVITY_DIRECTIONS = ["outbound", "inbound"]
NAICS_CODE_REGEX = re.compile(r"^\d{2,6}$")


def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return status, payload


def _error(status: int, message: str) -> tuple[int, dict[str, Any]]:
    return status, {"error": message}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_outreach_routes(
    store: Any,  # AgentOSStore — has _get_conn() -> sqlite3.Connection
    get_auth: Callable[[dict[str, Any] | None], AuthContext],
) -> dict[tuple[str, str], Callable]:
    """Create outreach route handlers.
    Returns a dict of {(method, path): handler}.
    """

    def list_leads(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/outreach/leads — list all leads for tenant."""
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
                "SELECT * FROM outreach_leads WHERE tenant_id = ? ORDER BY updated_at DESC",
                (tenant_id,)
            )
            leads = [dict(row) for row in cursor.fetchall()]

            return _json_response(200, {"status": "success", "data": {"leads": leads}})
        except Exception as e:
            log.exception("Failed to list outreach leads")
            return _error(500, str(e))

    def get_stats(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/outreach/stats — pipeline counts per stage."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            cursor = conn.execute(
                "SELECT status, COUNT(*) as count FROM outreach_leads WHERE tenant_id = ? GROUP BY status",
                (tenant_id,)
            )
            stats = {}
            for row in cursor.fetchall():
                stats[row["status"]] = row["count"]

            return _json_response(200, {"status": "success", "data": {"stats": stats}})
        except Exception as e:
            log.exception("Failed to get outreach stats")
            return _error(500, str(e))

    def create_lead(body: dict[str, Any], **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/outreach/leads — create a lead."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            # Validate required fields
            company_name = (body.get("companyName") or "").strip()
            if not company_name:
                return _error(400, "companyName is required")

            # Optional fields with defaults
            source = (body.get("source") or "manual").strip()
            if source not in OUTREACH_SOURCES:
                return _error(400, f"source must be one of: {', '.join(OUTREACH_SOURCES)}")

            status = (body.get("status") or "identified").strip()
            if status not in OUTREACH_STATUSES:
                return _error(400, f"status must be one of: {', '.join(OUTREACH_STATUSES)}")

            # Optional string fields
            contact_name = body.get("contactName")
            contact_email = body.get("contactEmail")
            phone = body.get("phone")
            linkedin_url = body.get("linkedinUrl")
            naics_code = body.get("naicsCode")
            if naics_code and not NAICS_CODE_REGEX.match(naics_code):
                return _error(400, "NAICS code must be 2-6 digits")
            employee_count = body.get("employeeCount")
            notes = body.get("notes")
            assigned_to = body.get("assignedTo")

            lead_id = str(uuid.uuid4())
            now = _now()

            conn = store._get_conn()
            conn.execute(
                """INSERT INTO outreach_leads 
                   (id, tenant_id, company_name, contact_name, contact_email, phone, 
                    linkedin_url, naics_code, employee_count, source, status, notes, 
                    assigned_to, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (lead_id, tenant_id, company_name, contact_name, contact_email, phone,
                 linkedin_url, naics_code, employee_count, source, status, notes,
                 assigned_to, now, now)
            )
            conn.commit()

            return _json_response(201, {
                "status": "success",
                "data": {"lead": {"id": lead_id, "companyName": company_name, "status": status}},
                "message": "Lead created"
            })
        except Exception as e:
            log.exception("Failed to create outreach lead")
            return _error(500, str(e))

    def get_lead(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/outreach/leads/{id} — get single lead with activities."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            lead_id = path_params.get("id", "")
            if not lead_id:
                return _error(400, "id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM outreach_leads WHERE id = ? AND tenant_id = ?",
                (lead_id, tenant_id)
            )
            row = cursor.fetchone()
            if not row:
                return _error(404, "Lead not found")

            lead = dict(row)

            # Get activities
            conn.row_factory = sqlite3.Row
            activities_cursor = conn.execute(
                "SELECT * FROM outreach_activities WHERE lead_id = ? ORDER BY created_at DESC",
                (lead_id,)
            )
            lead["activities"] = [dict(r) for r in activities_cursor.fetchall()]

            return _json_response(200, {"status": "success", "data": {"lead": lead}})
        except Exception as e:
            log.exception("Failed to get outreach lead")
            return _error(500, str(e))

    def update_lead(body: dict[str, Any], **path_params: str) -> tuple[int, dict[str, Any]]:
        """PATCH /api/agent-os/outreach/leads/{id} — update a lead."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            lead_id = path_params.get("id", "")
            if not lead_id:
                return _error(400, "id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            # Check exists
            cursor = conn.execute(
                "SELECT * FROM outreach_leads WHERE id = ? AND tenant_id = ?",
                (lead_id, tenant_id)
            )
            if not cursor.fetchone():
                return _error(404, "Lead not found")

            # Build update fields
            updates = []
            values = []

            field_map = {
                "companyName": "company_name",
                "contactName": "contact_name",
                "contactEmail": "contact_email",
                "phone": "phone",
                "linkedinUrl": "linkedin_url",
                "naicsCode": "naics_code",
                "employeeCount": "employee_count",
                "source": "source",
                "status": "status",
                "notes": "notes",
                "assignedTo": "assigned_to",
            }

            for json_field, db_field in field_map.items():
                if json_field in body:
                    val = body[json_field]
                    # Validate enum fields
                    if json_field == "source" and val and val not in OUTREACH_SOURCES:
                        return _error(400, f"source must be one of: {', '.join(OUTREACH_SOURCES)}")
                    if json_field == "status" and val and val not in OUTREACH_STATUSES:
                        return _error(400, f"status must be one of: {', '.join(OUTREACH_STATUSES)}")
                    if json_field == "naicsCode" and val and not NAICS_CODE_REGEX.match(val):
                        return _error(400, "NAICS code must be 2-6 digits")
                    updates.append(f"{db_field} = ?")
                    values.append(val)

            if not updates:
                return _error(400, "no fields to update")

            updates.append("updated_at = ?")
            values.append(_now())
            values.extend([lead_id, tenant_id])

            conn.execute(
                f"UPDATE outreach_leads SET {', '.join(updates)} WHERE id = ? AND tenant_id = ?",
                values
            )
            conn.commit()

            return _json_response(200, {"status": "success", "message": "Lead updated"})
        except Exception as e:
            log.exception("Failed to update outreach lead")
            return _error(500, str(e))

    def delete_lead(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """DELETE /api/agent-os/outreach/leads/{id} — remove a lead."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            lead_id = path_params.get("id", "")
            if not lead_id:
                return _error(400, "id required")

            conn = store._get_conn()
            cursor = conn.execute(
                "SELECT id FROM outreach_leads WHERE id = ? AND tenant_id = ?",
                (lead_id, tenant_id)
            )
            if not cursor.fetchone():
                return _error(404, "Lead not found")

            # Delete activities first
            conn.execute("DELETE FROM outreach_activities WHERE lead_id = ?", (lead_id,))
            conn.execute("DELETE FROM outreach_leads WHERE id = ?", (lead_id,))
            conn.commit()

            return _json_response(200, {"status": "success", "message": "Lead deleted"})
        except Exception as e:
            log.exception("Failed to delete outreach lead")
            return _error(500, str(e))

    def list_activities(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/outreach/leads/{id}/activities — list activities for a lead."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            lead_id = path_params.get("id", "")
            if not lead_id:
                return _error(400, "id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            # Verify lead belongs to tenant
            cursor = conn.execute(
                "SELECT id FROM outreach_leads WHERE id = ? AND tenant_id = ?",
                (lead_id, tenant_id)
            )
            if not cursor.fetchone():
                return _error(404, "Lead not found")

            cursor = conn.execute(
                "SELECT * FROM outreach_activities WHERE lead_id = ? ORDER BY created_at DESC",
                (lead_id,)
            )
            activities = [dict(row) for row in cursor.fetchall()]

            return _json_response(200, {"status": "success", "data": {"activities": activities}})
        except Exception as e:
            log.exception("Failed to list activities")
            return _error(500, str(e))

    def create_activity(body: dict[str, Any], **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/outreach/leads/{id}/activities — log an activity."""
        try:
            auth = get_auth(body)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            lead_id = path_params.get("id", "")
            if not lead_id:
                return _error(400, "id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            # Verify lead belongs to tenant
            cursor = conn.execute(
                "SELECT id FROM outreach_leads WHERE id = ? AND tenant_id = ?",
                (lead_id, tenant_id)
            )
            if not cursor.fetchone():
                return _error(404, "Lead not found")

            activity_type = (body.get("type") or "note").strip()
            if activity_type not in ACTIVITY_TYPES:
                return _error(400, f"type must be one of: {', '.join(ACTIVITY_TYPES)}")

            direction = (body.get("direction") or "outbound").strip()
            if direction not in ACTIVITY_DIRECTIONS:
                return _error(400, f"direction must be one of: {', '.join(ACTIVITY_DIRECTIONS)}")

            subject = body.get("subject")
            summary = body.get("summary")
            next_follow_up = body.get("nextFollowUp")

            activity_id = str(uuid.uuid4())
            now = _now()

            conn.execute(
                """INSERT INTO outreach_activities 
                   (id, lead_id, type, direction, subject, summary, next_follow_up, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (activity_id, lead_id, activity_type, direction, subject, summary, next_follow_up, now)
            )
            conn.commit()

            return _json_response(201, {
                "status": "success",
                "data": {"activity": {"id": activity_id, "type": activity_type, "leadId": lead_id}},
                "message": "Activity logged"
            })
        except Exception as e:
            log.exception("Failed to create activity")
            return _error(500, str(e))

    routes: dict[tuple[str, str], Callable] = {
        ("GET", "/api/agent-os/outreach/leads"): list_leads,
        ("GET", "/api/agent-os/outreach/stats"): get_stats,
        ("POST", "/api/agent-os/outreach/leads"): create_lead,
        ("GET", "/api/agent-os/outreach/leads/{id}"): get_lead,
        ("PATCH", "/api/agent-os/outreach/leads/{id}"): update_lead,
        ("DELETE", "/api/agent-os/outreach/leads/{id}"): delete_lead,
        ("GET", "/api/agent-os/outreach/leads/{id}/activities"): list_activities,
        ("POST", "/api/agent-os/outreach/leads/{id}/activities"): create_activity,
    }

    return routes
