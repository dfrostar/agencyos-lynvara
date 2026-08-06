"""feedback.py — Feedback loop routes for Agent OS.

Tenant-scoped endpoints for the closed-loop feedback system:
    GET  /api/agent-os/feedback — list feedback
    POST /api/agent-os/feedback — create feedback
    GET  /api/agent-os/feedback/stats — counts by status
    GET  /api/agent-os/feedback/digest — weekly digest
    GET  /api/agent-os/feedback/{id} — get single
    PATCH /api/agent-os/feedback/{id}/status — update status (closed-loop)
    POST /api/agent-os/feedback/capture/user-correction
    POST /api/agent-os/feedback/capture/test-failure
    POST /api/agent-os/feedback/capture/qa-finding

Design:
    - All routes are tenant-scoped (auth.tenant_id).
    - Stdlib-only.
    - Closed-loop: status='applied' creates a knowledge entry for future AI guidance.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from .auth import AuthContext

log = logging.getLogger(__name__)

# Validation constants
TRIGGER_EVENTS = ["user_correction", "test_failure", "qa_finding", "support_ticket"]
FEEDBACK_STATUSES = ["pending", "reviewed", "applied", "dismissed"]


def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return status, payload


def _error(status: int, message: str) -> tuple[int, dict[str, Any]]:
    return status, {"error": message}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_feedback_routes(
    store: Any,
    get_auth: Callable[[dict[str, Any] | None], AuthContext],
) -> dict[tuple[str, str], Callable]:
    """Create feedback route handlers."""
    
    def _resolve_auth(body, headers):
        """Resolve auth from headers first, then fall back to get_auth."""
        if headers:
            from .auth import extract_bearer_token, SessionStore
            token = extract_bearer_token(headers.get("Authorization"))
            if token:
                session = SessionStore().get_session(token)
                if session:
                    return session
        return get_auth(body)

    # ── helpers ──────────────────────────────────────────────────

    def _create_knowledge_entry(
        conn: sqlite3.Connection,
        tenant_id: str,
        feedback_id: str,
        skill_name: str,
        trigger_event: str,
        original_execution: str | None,
        user_correction: str | None,
        suggested_improvement: str,
        reviewed_by: str | None,
        git_commit_sha: str | None,
    ) -> None:
        """Closed-loop: when feedback is applied, create a knowledge entry."""
        content_parts = [f'Feedback applied for "{skill_name}" ({trigger_event}):']
        if original_execution:
            content_parts.append(f"\nOriginal: {original_execution}")
        if user_correction:
            content_parts.append(f"\nCorrected: {user_correction}")
        content_parts.append(f"\nImprovement: {suggested_improvement}")

        knowledge_id = str(uuid.uuid4())
        now = _now()
        conn.execute(
            """INSERT INTO knowledge_entries
               (id, tenant_id, entry_type, title, content, source_feedback_id,
                metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                knowledge_id,
                tenant_id,
                "feedback",
                f"Feedback applied: {skill_name}",
                "\n".join(content_parts),
                feedback_id,
                str({
                    "trigger_event": trigger_event,
                    "reviewed_by": reviewed_by,
                    "git_commit_sha": git_commit_sha,
                }),
                now,
            ),
        )

    # ── list ────────────────────────────────────────────────────

    def list_feedback(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/feedback — list feedback for tenant."""
        try:
            auth = _resolve_auth(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            # Parse query params (from body for simplicity)
            status_filter = None
            skill_name = None
            limit = 20
            offset = 0

            if body:
                if body.get("status"):
                    s = body["status"]
                    if s not in FEEDBACK_STATUSES:
                        return _error(400, f"status must be one of: {', '.join(FEEDBACK_STATUSES)}")
                    status_filter = s
                if body.get("skillName"):
                    skill_name = body["skillName"]
                if body.get("limit"):
                    limit = min(int(body["limit"]), 100)
                if body.get("offset"):
                    offset = int(body["offset"])

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            where_clauses = ["tenant_id = ?"]
            params: list[Any] = [tenant_id]

            if status_filter:
                where_clauses.append("status = ?")
                params.append(status_filter)
            if skill_name:
                where_clauses.append("skill_name = ?")
                params.append(skill_name)

            where_sql = " AND ".join(where_clauses)

            # Get total
            total_cursor = conn.execute(
                f"SELECT COUNT(*) FROM skill_feedback WHERE {where_sql}", params
            )
            total = total_cursor.fetchone()[0]

            # Get rows
            query = f"SELECT * FROM skill_feedback WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor = conn.execute(query, params)
            rows = [dict(r) for r in cursor.fetchall()]

            return _json_response(200, {
                "status": "success",
                "data": {"feedback": rows},
                "pagination": {"total": total, "limit": limit, "offset": offset},
            })
        except Exception as e:
            log.exception("Failed to list feedback")
            return _error(500, str(e))

    # ── create ──────────────────────────────────────────────────

    def create_feedback(body: dict[str, Any], headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/feedback — create a feedback entry."""
        try:
            auth = _resolve_auth(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            # Validate required fields
            skill_name = (body.get("skillName") or "").strip()
            if not skill_name:
                return _error(400, "skillName is required")
            if len(skill_name) > 200:
                return _error(400, "skillName max 200 chars")

            trigger_event = (body.get("triggerEvent") or "").strip()
            if trigger_event not in TRIGGER_EVENTS:
                return _error(400, f"triggerEvent must be one of: {', '.join(TRIGGER_EVENTS)}")

            trigger_context = (body.get("triggerContext") or "").strip()
            if not trigger_context:
                return _error(400, "triggerContext is required")
            if len(trigger_context) > 5000:
                return _error(400, "triggerContext max 5000 chars")

            suggested_improvement = (body.get("suggestedImprovement") or "").strip()
            if not suggested_improvement:
                return _error(400, "suggestedImprovement is required")
            if len(suggested_improvement) > 5000:
                return _error(400, "suggestedImprovement max 5000 chars")

            # Optional fields
            original_execution = body.get("originalExecution")
            if original_execution and len(original_execution) > 5000:
                return _error(400, "originalExecution max 5000 chars")
            user_correction = body.get("userCorrection")
            if user_correction and len(user_correction) > 5000:
                return _error(400, "userCorrection max 5000 chars")
            git_commit_sha = body.get("gitCommitSha")
            if git_commit_sha and len(git_commit_sha) > 40:
                return _error(400, "gitCommitSha max 40 chars")

            feedback_id = str(uuid.uuid4())
            now = _now()

            conn = store._get_conn()
            conn.execute(
                """INSERT INTO skill_feedback
                   (id, tenant_id, skill_name, trigger_event, trigger_context,
                    original_execution, user_correction, suggested_improvement,
                    git_commit_sha, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (feedback_id, tenant_id, skill_name, trigger_event, trigger_context,
                 original_execution, user_correction, suggested_improvement,
                 git_commit_sha, "pending", now, now),
            )
            conn.commit()

            return _json_response(201, {
                "status": "success",
                "data": {"feedback": {"id": feedback_id, "skillName": skill_name, "status": "pending"}},
                "message": "Feedback created",
            })
        except Exception as e:
            log.exception("Failed to create feedback")
            return _error(500, str(e))

    # ── get one ─────────────────────────────────────────────────

    def get_feedback(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/feedback/{id} — get single feedback entry."""
        try:
            auth = _resolve_auth(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            feedback_id = path_params.get("id", "")
            if not feedback_id:
                return _error(400, "id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM skill_feedback WHERE id = ? AND tenant_id = ?",
                (feedback_id, tenant_id),
            )
            row = cursor.fetchone()
            if not row:
                return _error(404, "Feedback not found")

            return _json_response(200, {"status": "success", "data": {"feedback": dict(row)}})
        except Exception as e:
            log.exception("Failed to get feedback")
            return _error(500, str(e))

    # ── update status (closed-loop) ─────────────────────────────

    def update_status(body: dict[str, Any], headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """PATCH /api/agent-os/feedback/{id}/status — update feedback status."""
        try:
            auth = _resolve_auth(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            feedback_id = path_params.get("id", "")
            if not feedback_id:
                return _error(400, "id required")

            new_status = (body.get("status") or "").strip()
            if new_status not in FEEDBACK_STATUSES:
                return _error(400, f"status must be one of: {', '.join(FEEDBACK_STATUSES)}")

            reviewed_by = body.get("reviewedBy")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            # Check exists
            cursor = conn.execute(
                "SELECT * FROM skill_feedback WHERE id = ? AND tenant_id = ?",
                (feedback_id, tenant_id),
            )
            row = cursor.fetchone()
            if not row:
                return _error(404, "Feedback not found")

            feedback = dict(row)
            now = _now()
            applied_at = feedback.get("applied_at")
            if new_status == "applied":
                applied_at = now

            conn.execute(
                """UPDATE skill_feedback
                   SET status = ?, reviewed_by = ?, applied_at = ?, updated_at = ?
                   WHERE id = ? AND tenant_id = ?""",
                (new_status, reviewed_by, applied_at, now, feedback_id, tenant_id),
            )

            # Closed-loop: on 'applied', create knowledge entry
            if new_status == "applied":
                _create_knowledge_entry(
                    conn, tenant_id, feedback_id,
                    feedback["skill_name"], feedback["trigger_event"],
                    feedback.get("original_execution"), feedback.get("user_correction"),
                    feedback["suggested_improvement"], reviewed_by,
                    feedback.get("git_commit_sha"),
                )

            conn.commit()

            return _json_response(200, {
                "status": "success",
                "message": "Feedback status updated",
                "data": {"feedback": {"id": feedback_id, "status": new_status}},
            })
        except Exception as e:
            log.exception("Failed to update feedback status")
            return _error(500, str(e))

    # ── stats ───────────────────────────────────────────────────

    def get_stats(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/feedback/stats — counts by status."""
        try:
            auth = _resolve_auth(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            cursor = conn.execute(
                "SELECT status, COUNT(*) as count FROM skill_feedback WHERE tenant_id = ? GROUP BY status",
                (tenant_id,),
            )
            stats = {}
            for r in cursor.fetchall():
                stats[r["status"]] = r["count"]

            return _json_response(200, {"status": "success", "data": {"stats": stats}})
        except Exception as e:
            log.exception("Failed to get feedback stats")
            return _error(500, str(e))

    # ── digest ──────────────────────────────────────────────────

    def get_digest(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/feedback/digest — weekly digest."""
        try:
            auth = _resolve_auth(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row
            week_ago = datetime.now(timezone.utc).timestamp() - 7 * 24 * 60 * 60

            cursor = conn.execute(
                """SELECT * FROM skill_feedback
                   WHERE tenant_id = ? AND created_at >= datetime(?, 'unixepoch')
                   ORDER BY created_at DESC""",
                (tenant_id, week_ago),
            )
            feedbacks = [dict(r) for r in cursor.fetchall()]

            # Aggregate stats
            by_status: dict[str, int] = {}
            by_trigger: dict[str, int] = {}
            by_skill: dict[str, int] = {}

            for fb in feedbacks:
                by_status[fb["status"]] = (by_status.get(fb["status"], 0)) + 1
                by_trigger[fb["trigger_event"]] = (by_trigger.get(fb["trigger_event"], 0)) + 1
                by_skill[fb["skill_name"]] = (by_skill.get(fb["skill_name"], 0)) + 1

            top_pending = [
                {"id": fb["id"], "skillName": fb["skill_name"], "triggerEvent": fb["trigger_event"]}
                for fb in feedbacks if fb["status"] == "pending"
            ][:5]

            summary = (
                f"This week captured {len(feedbacks)} feedback entries "
                f"across {len(by_skill)} skills. "
                f"{by_status.get('pending', 0)} pending review, "
                f"{by_status.get('applied', 0)} applied. "
                f"Top trigger: {max(by_trigger, key=lambda k: by_trigger[k]) if by_trigger else 'none'}."
            )

            return _json_response(200, {
                "status": "success",
                "data": {
                    "digest": {
                        "totalFeedback": len(feedbacks),
                        "byStatus": by_status,
                        "byTrigger": by_trigger,
                        "topPending": top_pending,
                        "summary": summary,
                    }
                },
            })
        except Exception as e:
            log.exception("Failed to generate digest")
            return _error(500, str(e))

    # ── capture: user-correction ────────────────────────────────

    def capture_user_correction(body: dict[str, Any], headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/feedback/capture/user-correction"""
        try:
            auth = _resolve_auth(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            skill_name = (body.get("skillName") or "").strip()
            if not skill_name:
                return _error(400, "skillName is required")

            original_output = (body.get("originalOutput") or "").strip()
            if not original_output:
                return _error(400, "originalOutput is required")

            user_edited = (body.get("userEditedOutput") or "").strip()
            if not user_edited:
                return _error(400, "userEditedOutput is required")

            context = body.get("context")

            feedback_id = str(uuid.uuid4())
            now = _now()

            conn = store._get_conn()
            conn.execute(
                """INSERT INTO skill_feedback
                   (id, tenant_id, skill_name, trigger_event, trigger_context,
                    original_execution, user_correction, suggested_improvement,
                    status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (feedback_id, tenant_id, skill_name, "user_correction",
                 context or "User modified AI-generated output",
                 original_output, user_edited,
                 "User edited the original output. Review diff and update skill guidance.",
                 "pending", now, now),
            )
            conn.commit()

            return _json_response(201, {
                "status": "success",
                "data": {"feedback": {"id": feedback_id, "skillName": skill_name, "status": "pending"}},
                "message": "User correction captured",
            })
        except Exception as e:
            log.exception("Failed to capture user correction")
            return _error(500, str(e))

    # ── capture: test-failure ───────────────────────────────────

    def capture_test_failure(body: dict[str, Any], headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/feedback/capture/test-failure"""
        try:
            auth = _resolve_auth(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            skill_name = (body.get("skillName") or "").strip()
            if not skill_name:
                return _error(400, "skillName is required")

            test_name = (body.get("testName") or "").strip()
            if not test_name:
                return _error(400, "testName is required")

            error_message = (body.get("errorMessage") or "").strip()
            if not error_message:
                return _error(400, "errorMessage is required")

            commit_sha = body.get("commitSha")

            feedback_id = str(uuid.uuid4())
            now = _now()

            conn = store._get_conn()
            conn.execute(
                """INSERT INTO skill_feedback
                   (id, tenant_id, skill_name, trigger_event, trigger_context,
                    suggested_improvement, git_commit_sha, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (feedback_id, tenant_id, skill_name, "test_failure",
                 f'Test "{test_name}" failed: {error_message}',
                 f'Fix skill guidance for "{skill_name}" — test failure indicates incorrect implementation.',
                 commit_sha, "pending", now, now),
            )
            conn.commit()

            return _json_response(201, {
                "status": "success",
                "data": {"feedback": {"id": feedback_id, "skillName": skill_name, "status": "pending"}},
                "message": "Test failure captured",
            })
        except Exception as e:
            log.exception("Failed to capture test failure")
            return _error(500, str(e))

    # ── capture: qa-finding ─────────────────────────────────────

    def capture_qa_finding(body: dict[str, Any], headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/feedback/capture/qa-finding"""
        try:
            auth = _resolve_auth(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")

            tenant_id = auth.tenant_id
            if not tenant_id:
                return _error(400, "tenant_id required")

            skill_name = (body.get("skillName") or "").strip()
            if not skill_name:
                return _error(400, "skillName is required")

            finding = (body.get("finding") or "").strip()
            if not finding:
                return _error(400, "finding is required")

            severity = (body.get("severity") or "").strip()
            if not severity:
                return _error(400, "severity is required")

            commit_sha = body.get("commitSha")

            feedback_id = str(uuid.uuid4())
            now = _now()

            conn = store._get_conn()
            conn.execute(
                """INSERT INTO skill_feedback
                   (id, tenant_id, skill_name, trigger_event, trigger_context,
                    suggested_improvement, git_commit_sha, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (feedback_id, tenant_id, skill_name, "qa_finding",
                 f"[{severity}] {finding}",
                 f'Address {severity} finding in "{skill_name}": {finding}',
                 commit_sha, "pending", now, now),
            )
            conn.commit()

            return _json_response(201, {
                "status": "success",
                "data": {"feedback": {"id": feedback_id, "skillName": skill_name, "status": "pending"}},
                "message": "QA finding captured",
            })
        except Exception as e:
            log.exception("Failed to capture QA finding")
            return _error(500, str(e))

    # ── route table ─────────────────────────────────────────────

    routes: dict[tuple[str, str], Callable] = {
        ("GET", "/api/agent-os/feedback"): list_feedback,
        ("POST", "/api/agent-os/feedback"): create_feedback,
        ("GET", "/api/agent-os/feedback/stats"): get_stats,
        ("GET", "/api/agent-os/feedback/digest"): get_digest,
        ("GET", "/api/agent-os/feedback/{id}"): get_feedback,
        ("PATCH", "/api/agent-os/feedback/{id}/status"): update_status,
        ("POST", "/api/agent-os/feedback/capture/user-correction"): capture_user_correction,
        ("POST", "/api/agent-os/feedback/capture/test-failure"): capture_test_failure,
        ("POST", "/api/agent-os/feedback/capture/qa-finding"): capture_qa_finding,
    }

    return routes
