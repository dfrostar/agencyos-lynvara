"""weekly_self_improvement.py — Weekly self-improvement report generator for Agent OS.

B-10: Auto-summarize self-improvement outcomes into a week-over-week
delta report mirroring the B-08 weekly review pattern.

Endpoints:
    GET /api/agent-os/review/self-improvement — WoW delta report
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Callable

from .auth import AuthContext, SessionStore, extract_bearer_token

log = logging.getLogger(__name__)


def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return status, payload


def _error(status: int, message: str) -> tuple[int, dict[str, Any]]:
    return status, {"error": message}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _week_ago_timestamp() -> float:
    """Get Unix timestamp for 7 days ago."""
    return datetime.now(timezone.utc).timestamp() - 7 * 24 * 60 * 60


def create_self_improvement_review_routes(
    store: Any,
    session_store: SessionStore | None = None,
    get_auth: Callable[[dict[str, Any] | None], AuthContext] | None = None,
) -> dict[tuple[str, str], Callable]:
    """Create self-improvement review route handlers."""
    _session_store = session_store or SessionStore()

    def _resolve_auth(body: Any, headers: dict[str, str] | None) -> AuthContext:
        """Resolve auth from bearer <REDACTED>."""
        if headers:
            token = extract_bearer_token(headers.get("Authorization"))
            if token:
                session = _session_store.get_session(token)
                if session:
                    return session
        return get_auth(body) if get_auth else AuthContext(email="", tenant_id=None)

    def _resolve_tenant_id(
        body: dict[str, Any] | None, headers: dict[str, str] | None
    ) -> tuple[AuthContext, str | None]:
        auth = _resolve_auth(body, headers)
        if not auth.is_authenticated:
            return auth, None
        return auth, auth.tenant_id

    def _generate_report(
        conn: sqlite3.Connection, tenant_id: str
    ) -> dict[str, Any]:
        """Aggregate self-improvement data into a WoW delta report."""
        week_ago = _week_ago_timestamp()
        two_weeks_ago = datetime.now(timezone.utc).timestamp() - 14 * 24 * 60 * 60

        # ── This week's experiments ─────────────────────────────────
        exp_this_week = conn.execute(
            """SELECT COUNT(*) as cnt,
                      SUM(CASE WHEN verdict = 'promoted' THEN 1 ELSE 0 END) as promoted,
                      AVG(delta) as avg_delta
               FROM experiments
               WHERE tenant_id = ?
                 AND started_at >= datetime(?, 'unixepoch')""",
            (tenant_id, week_ago),
        ).fetchone()

        # ── Last week's experiments ─────────────────────────────────
        exp_last_week = conn.execute(
            """SELECT COUNT(*) as cnt,
                      SUM(CASE WHEN verdict = 'promoted' THEN 1 ELSE 0 END) as promoted,
                      AVG(delta) as avg_delta
               FROM experiments
               WHERE tenant_id = ?
                 AND started_at >= datetime(?, 'unixepoch')
                 AND started_at < datetime(?, 'unixepoch')""",
            (tenant_id, two_weeks_ago, week_ago),
        ).fetchone()

        run_this_week = exp_this_week["cnt"] if exp_this_week else 0
        run_last_week = exp_last_week["cnt"] if exp_last_week else 0
        delta_pct = ((run_this_week - run_last_week) / max(run_last_week, 1)) * 100

        promoted_this_week = exp_this_week["promoted"] if exp_this_week and exp_this_week["promoted"] else 0
        promotion_rate = promoted_this_week / max(run_this_week, 1)

        avg_delta_val = exp_this_week["avg_delta"] if exp_this_week and exp_this_week["avg_delta"] else 0.0

        # ── Tuner changes this week ─────────────────────────────────
        tuner_changes = conn.execute(
            """SELECT DISTINCT p.metric_name, p.baseline_value, p.candidate_value,
                      p.status as verdict, p.created_at
               FROM proposals p
               WHERE p.tenant_id = ?
                 AND p.updated_at >= datetime(?, 'unixepoch')
                 AND p.status IN ('promoted', 'rolled_back')
               ORDER BY p.updated_at DESC
               LIMIT 20""",
            (tenant_id, week_ago),
        ).fetchall()
        tuner_changes_list = [
            {
                "metric_name": row["metric_name"],
                "old_value": row["baseline_value"],
                "new_value": row["candidate_value"],
                "verdict": row["verdict"],
                "delta": round(row["candidate_value"] - row["baseline_value"], 6),
            }
            for row in tuner_changes
        ]

        # ── Threshold adjustments (from signal_states) ──────────────
        # Get all states and compare with historical (simplified: report
        # which metrics have non-default lambda or cooldown)
        signal_states = store.get_all_signal_states(tenant_id)
        threshold_adjustments = []
        for metric, state in signal_states.items():
            if state.get("lambda_threshold", 4.0) != 4.0:
                threshold_adjustments.append({
                    "metric_name": metric,
                    "parameter": "lambda_threshold",
                    "current_value": state["lambda_threshold"],
                    "default_value": 4.0,
                    "reason": "adjusted by behavior learner",
                })
            if state.get("cooldown_seconds", 60.0) != 60.0:
                threshold_adjustments.append({
                    "metric_name": metric,
                    "parameter": "cooldown_seconds",
                    "current_value": state["cooldown_seconds"],
                    "default_value": 60.0,
                    "reason": "adjusted by behavior learner",
                })

        # ── Proactive experiments this week ─────────────────────────
        proactive_experiments = conn.execute(
            """SELECT
                   COUNT(*) as proposed,
                   SUM(CASE WHEN status IN ('promoted', 'rolled_back') THEN 1 ELSE 0 END) as completed,
                   SUM(CASE WHEN status = 'promoted' THEN 1 ELSE 0 END) as promoted
               FROM proposals
               WHERE tenant_id = ?
                 AND tags LIKE '%proactive%'
                 AND created_at >= datetime(?, 'unixepoch')""",
            (tenant_id, week_ago),
        ).fetchone()
        proactive_data = {
            "proposed": proactive_experiments["proposed"] if proactive_experiments else 0,
            "run": proactive_experiments["completed"] if proactive_experiments else 0,
            "promoted": proactive_experiments["promoted"] if proactive_experiments else 0,
        }

        # ── Outcomes summary ────────────────────────────────────────
        outcome_stats = store.get_outcome_stats(tenant_id)

        # ── Learning summary ────────────────────────────────────────
        summary_parts = []
        if run_this_week > 0:
            summary_parts.append(
                f"This week the system ran {run_this_week} experiments, "
                f"promoted {promoted_this_week} "
                f"({'+' if delta_pct >= 0 else ''}{delta_pct:.0f}% vs last week)"
            )
        else:
            summary_parts.append("No experiments run this week")
        if threshold_adjustments:
            summary_parts.append(
                f"{len(threshold_adjustments)} threshold adjustments"
            )
        if proactive_data["proposed"]:
            summary_parts.append(
                f"{proactive_data['proactive']} proactive experiments proposed"
            )

        return {
            "period": "weekly",
            "generated_at": _now(),
            "summary": ". ".join(summary_parts),
            "experiments": {
                "run_this_week": run_this_week,
                "run_last_week": run_last_week,
                "delta_pct": round(delta_pct, 1),
                "promotion_rate": round(promotion_rate, 2),
                "avg_delta": round(avg_delta_val, 4),
            },
            "tuner_changes": tuner_changes_list,
            "threshold_adjustments": threshold_adjustments,
            "proactive_experiments": proactive_data,
            "outcome_stats": outcome_stats,
            "learning_summary": "; ".join(summary_parts),
        }

    def get_self_improvement_report(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/review/self-improvement"""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            report = _generate_report(conn, tenant_id)
            return _json_response(200, report)
        except Exception as e:
            log.exception("Failed to generate self-improvement report")
            return _error(500, str(e))

    def get_self_improvement_summary(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/review/self-improvement/summary"""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            report = _generate_report(conn, tenant_id)
            return _json_response(200, {
                "period": report["period"],
                "generated_at": report["generated_at"],
                "summary": report["summary"],
            })
        except Exception as e:
            log.exception("Failed to generate self-improvement summary")
            return _error(500, str(e))

    routes: dict[tuple[str, str], Callable] = {
        ("GET", "/api/agent-os/review/self-improvement"): get_self_improvement_report,
        ("GET", "/api/agent-os/review/self-improvement/summary"): get_self_improvement_summary,
    }
    return routes
