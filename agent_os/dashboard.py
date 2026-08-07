"""dashboard.py — Business health dashboard for Agent OS.

B-04: Single pane of glass — real-time business health view
aggregating all modules: finance, outreach, engagements, feedback,
signals, webhooks, knowledge.

Endpoints:
    GET /api/agent-os/dashboard — full dashboard
    GET /api/agent-os/dashboard/health — health score only
    GET /api/agent-os/dashboard/metrics — key metrics only
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


def create_dashboard_routes(
    store: Any,
    session_store: SessionStore | None = None,
    get_auth: Callable[[dict[str, Any] | None], AuthContext] | None = None,
) -> dict[tuple[str, str], Callable]:
    """Create dashboard route handlers."""
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

    def _build_dashboard_data(
        conn: sqlite3.Connection, tenant_id: str
    ) -> dict[str, Any]:
        """Build the full dashboard payload."""
        # ── Finance ────────────────────────────────────────────────
        revenue_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM revenue_entries WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        total_revenue = revenue_row["total"] if revenue_row else 0

        costs_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM cost_entries WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        total_costs = costs_row["total"] if costs_row else 0

        outstanding_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count "
            "FROM invoices WHERE tenant_id = ? AND status IN ('sent', 'overdue')",
            (tenant_id,),
        ).fetchone()
        outstanding = outstanding_row["total"] if outstanding_row else 0
        outstanding_count = outstanding_row["count"] if outstanding_row else 0

        overdue_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count "
            "FROM invoices WHERE tenant_id = ? AND status = 'overdue'",
            (tenant_id,),
        ).fetchone()
        overdue = overdue_row["total"] if overdue_row else 0
        overdue_count = overdue_row["count"] if overdue_row else 0

        profit = total_revenue - total_costs
        margin = (profit / total_revenue * 100) if total_revenue > 0 else 0

        # ── Outreach ───────────────────────────────────────────────
        leads_total_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM outreach_leads WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        leads_total = leads_total_row["cnt"] if leads_total_row else 0

        lead_status_rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM outreach_leads "
            "WHERE tenant_id = ? GROUP BY status",
            (tenant_id,),
        ).fetchall()
        lead_status = {row["status"]: row["cnt"] for row in lead_status_rows}

        customers_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM outreach_leads "
            "WHERE tenant_id = ? AND status = 'customer'",
            (tenant_id,),
        ).fetchone()
        customers = customers_row["cnt"] if customers_row else 0

        # ── Engagements ────────────────────────────────────────────
        active_engagements_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM engagements "
            "WHERE tenant_id = ? AND status = 'active'",
            (tenant_id,),
        ).fetchone()
        active_engagements = active_engagements_row["cnt"] if active_engagements_row else 0

        engagement_status_rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM engagements "
            "WHERE tenant_id = ? GROUP BY status",
            (tenant_id,),
        ).fetchall()
        engagement_status = {row["status"]: row["cnt"] for row in engagement_status_rows}

        # ── Feedback ───────────────────────────────────────────────
        feedback_stats_rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM skill_feedback "
            "WHERE tenant_id = ? GROUP BY status",
            (tenant_id,),
        ).fetchall()
        feedback_stats = {row["status"]: row["cnt"] for row in feedback_stats_rows}

        # ── Signal Sources ─────────────────────────────────────────
        raw_signal_stats = store.get_raw_signal_stats(tenant_id)

        # ── Webhooks ───────────────────────────────────────────────
        webhook_stats = store.get_webhook_stats(tenant_id, hours=24)

        # ── Knowledge ──────────────────────────────────────────────
        knowledge_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM knowledge_entries WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        knowledge_entries = knowledge_row["cnt"] if knowledge_row else 0

        # ── Health Score ───────────────────────────────────────────
        health_score = _compute_health_score(
            total_revenue=total_revenue,
            total_costs=total_costs,
            active_engagements=active_engagements,
            leads_total=leads_total,
            customers=customers,
            feedback_pending=feedback_stats.get("pending", 0),
            overdue_invoices=overdue_count,
        )

        return {
            "generated_at": _now(),
            "health_score": health_score,
            "finance": {
                "totalRevenue": total_revenue,
                "totalCosts": total_costs,
                "profit": profit,
                "marginPercent": round(margin, 2),
                "outstandingInvoices": outstanding,
                "outstandingInvoiceCount": outstanding_count,
                "overdueInvoices": overdue,
                "overdueInvoiceCount": overdue_count,
            },
            "outreach": {
                "totalLeads": leads_total,
                "customers": customers,
                "pipeline": lead_status,
            },
            "engagements": {
                "active": active_engagements,
                "status": engagement_status,
            },
            "feedback": {
                "stats": feedback_stats,
                "pendingCount": feedback_stats.get("pending", 0),
            },
            "signals": raw_signal_stats,
            "webhooks": webhook_stats,
            "knowledge": {
                "totalEntries": knowledge_entries,
            },
        }

    def _compute_health_score(
        total_revenue: float,
        total_costs: float,
        active_engagements: int,
        leads_total: int,
        customers: int,
        feedback_pending: int,
        overdue_invoices: int,
    ) -> dict[str, Any]:
        """Compute a 0-100 health score with component breakdown."""
        score = 50  # baseline
        components: dict[str, int] = {}

        # Profitability (0-20 points)
        if total_revenue > 0:
            margin = (total_revenue - total_costs) / total_revenue
            profit_points = min(20, int(margin * 40))
            components["profitability"] = max(0, profit_points)
        else:
            components["profitability"] = 0
        score += components["profitability"]

        # Pipeline (0-15 points)
        if leads_total > 0:
            conversion = customers / leads_total if leads_total > 0 else 0
            pipeline_points = min(15, int(conversion * 30))
            components["pipeline"] = max(0, pipeline_points)
        else:
            components["pipeline"] = 0
        score += components["pipeline"]

        # Active engagements (0-10 points)
        engagement_points = min(10, active_engagements * 2)
        components["engagements"] = engagement_points
        score += engagement_points

        # Penalties
        if feedback_pending > 5:
            components["feedback_backlog"] = -5
            score -= 5
        if overdue_invoices > 2:
            components["overdue_penalty"] = -5
            score -= 5

        return {
            "score": max(0, min(100, score)),
            "rating": "healthy" if score >= 70 else "attention" if score >= 40 else "critical",
            "components": components,
        }

    def get_dashboard(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/dashboard — full dashboard."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            dashboard = _build_dashboard_data(conn, tenant_id)
            return _json_response(200, dashboard)
        except Exception as e:
            log.exception("Failed to build dashboard")
            return _error(500, str(e))

    def get_health(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/dashboard/health — health score only."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            dashboard = _build_dashboard_data(conn, tenant_id)
            return _json_response(200, {
                "generated_at": dashboard["generated_at"],
                "health_score": dashboard["health_score"],
            })
        except Exception as e:
            log.exception("Failed to get health score")
            return _error(500, str(e))

    def get_metrics(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/dashboard/metrics — key metrics only."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            dashboard = _build_dashboard_data(conn, tenant_id)
            return _json_response(200, {
                "generated_at": dashboard["generated_at"],
                "finance": dashboard["finance"],
                "outreach": dashboard["outreach"],
                "engagements": dashboard["engagements"],
                "feedback": dashboard["feedback"],
                "signals": dashboard["signals"],
                "webhooks": dashboard["webhooks"],
            })
        except Exception as e:
            log.exception("Failed to get metrics")
            return _error(500, str(e))

    routes: dict[tuple[str, str], Callable] = {
        ("GET", "/api/agent-os/dashboard"): get_dashboard,
        ("GET", "/api/agent-os/dashboard/health"): get_health,
        ("GET", "/api/agent-os/dashboard/metrics"): get_metrics,
    }
    return routes
