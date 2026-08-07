"""weekly_review.py — Weekly business review generator for Agent OS.

B-08: Auto-summarize pipeline, revenue, signals, and feedback
into a single weekly business review document.

Endpoints:
    GET /api/agent-os/review/weekly — generate weekly review
    GET /api/agent-os/review/weekly/summary — condensed summary only
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


def create_weekly_review_routes(
    store: Any,
    session_store: SessionStore | None = None,
    get_auth: Callable[[dict[str, Any] | None], AuthContext] | None = None,
) -> dict[tuple[str, str], Callable]:
    """Create weekly review route handlers."""
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

    def _generate_review_data(
        conn: sqlite3.Connection, tenant_id: str
    ) -> dict[str, Any]:
        """Aggregate all module data into a weekly review."""
        week_ago = _week_ago_timestamp()

        # ── Finance ────────────────────────────────────────────────
        revenue_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM revenue_entries "
            "WHERE tenant_id = ? AND recorded_at >= datetime(?, 'unixepoch')",
            (tenant_id, week_ago),
        ).fetchone()
        weekly_revenue = revenue_row["total"] if revenue_row else 0

        costs_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM cost_entries "
            "WHERE tenant_id = ? AND recorded_at >= datetime(?, 'unixepoch')",
            (tenant_id, week_ago),
        ).fetchone()
        weekly_costs = costs_row["total"] if costs_row else 0

        # Outstanding invoices
        outstanding_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count "
            "FROM invoices WHERE tenant_id = ? AND status IN ('sent', 'overdue')",
            (tenant_id,),
        ).fetchone()
        outstanding = outstanding_row["total"] if outstanding_row else 0
        outstanding_count = outstanding_row["count"] if outstanding_row else 0

        # ── Outreach ───────────────────────────────────────────────
        leads_created_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM outreach_leads "
            "WHERE tenant_id = ? AND created_at >= datetime(?, 'unixepoch')",
            (tenant_id, week_ago),
        ).fetchone()
        leads_created = leads_created_row["cnt"] if leads_created_row else 0

        # Lead status distribution
        lead_status_rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM outreach_leads "
            "WHERE tenant_id = ? GROUP BY status",
            (tenant_id,),
        ).fetchall()
        lead_status = {row["status"]: row["cnt"] for row in lead_status_rows}

        # New customers this week
        new_customers_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM outreach_leads "
            "WHERE tenant_id = ? AND status = 'customer' "
            "AND updated_at >= datetime(?, 'unixepoch')",
            (tenant_id, week_ago),
        ).fetchone()
        new_customers = new_customers_row["cnt"] if new_customers_row else 0

        # ── Engagements ────────────────────────────────────────────
        active_engagements_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM engagements "
            "WHERE tenant_id = ? AND status = 'active'",
            (tenant_id,),
        ).fetchone()
        active_engagements = active_engagements_row["cnt"] if active_engagements_row else 0

        completed_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM engagements "
            "WHERE tenant_id = ? AND status = 'completed' "
            "AND updated_at >= datetime(?, 'unixepoch')",
            (tenant_id, week_ago),
        ).fetchone()
        completed_engagements = completed_row["cnt"] if completed_row else 0

        # ── Feedback ───────────────────────────────────────────────
        feedback_stats_rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM skill_feedback "
            "WHERE tenant_id = ? AND created_at >= datetime(?, 'unixepoch') "
            "GROUP BY status",
            (tenant_id, week_ago),
        ).fetchall()
        feedback_stats = {row["status"]: row["cnt"] for row in feedback_stats_rows}

        # ── Signal Sources ─────────────────────────────────────────
        raw_signal_stats = store.get_raw_signal_stats(tenant_id)

        # ── Webhooks ───────────────────────────────────────────────
        webhook_stats = store.get_webhook_stats(tenant_id, hours=168)  # 7 days

        # ── Knowledge ──────────────────────────────────────────────
        knowledge_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM knowledge_entries "
            "WHERE tenant_id = ? AND created_at >= datetime(?, 'unixepoch')",
            (tenant_id, week_ago),
        ).fetchone()
        knowledge_entries = knowledge_row["cnt"] if knowledge_row else 0

        # ── Build summary ──────────────────────────────────────────
        profit = weekly_revenue - weekly_costs
        summary_parts = [
            f"Weekly Business Review",
            f"Revenue: ${weekly_revenue:,.2f} | Costs: ${weekly_costs:,.2f} | "
            f"Profit: ${profit:,.2f}",
            f"Pipeline: {leads_created} new leads, {new_customers} new customers, "
            f"{active_engagements} active engagements",
            f"Feedback: {feedback_stats.get('pending', 0)} pending, "
            f"{feedback_stats.get('applied', 0)} applied",
            f"Signals: {raw_signal_stats.get('total', 0)} raw signals from "
            f"{raw_signal_stats.get('sources', 0)} sources",
            f"Webhooks: {webhook_stats.get('processed', 0)} processed, "
            f"{webhook_stats.get('failed', 0)} failed",
        ]

        return {
            "period": "weekly",
            "generated_at": _now(),
            "finance": {
                "weeklyRevenue": weekly_revenue,
                "weeklyCosts": weekly_costs,
                "profit": profit,
                "outstandingInvoices": outstanding,
                "outstandingInvoiceCount": outstanding_count,
            },
            "outreach": {
                "leadsCreated": leads_created,
                "newCustomers": new_customers,
                "activeLeadStatus": lead_status,
            },
            "engagements": {
                "active": active_engagements,
                "completedThisWeek": completed_engagements,
            },
            "feedback": {
                "weeklyStats": feedback_stats,
            },
            "signals": raw_signal_stats,
            "webhooks": webhook_stats,
            "knowledge": {
                "newEntries": knowledge_entries,
            },
            "summary": "\n".join(summary_parts),
        }

    def get_weekly_review(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/review/weekly — full weekly review."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            review = _generate_review_data(conn, tenant_id)
            return _json_response(200, review)
        except Exception as e:
            log.exception("Failed to generate weekly review")
            return _error(500, str(e))

    def get_weekly_summary(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/review/weekly/summary — condensed summary."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            review = _generate_review_data(conn, tenant_id)
            return _json_response(200, {
                "period": review["period"],
                "generated_at": review["generated_at"],
                "summary": review["summary"],
            })
        except Exception as e:
            log.exception("Failed to generate weekly summary")
            return _error(500, str(e))

    routes: dict[tuple[str, str], Callable] = {
        ("GET", "/api/agent-os/review/weekly"): get_weekly_review,
        ("GET", "/api/agent-os/review/weekly/summary"): get_weekly_summary,
    }
    return routes
