"""finance.py — Financial tracking routes for Agent OS.

Tenant-scoped financial management:
    GET    /api/agent-os/finance/revenue — list revenue entries
    POST   /api/agent-os/finance/revenue — record revenue
    GET    /api/agent-os/finance/costs — list cost entries
    POST   /api/agent-os/finance/costs — record cost
    GET    /api/agent-os/finance/invoices — list invoices
    POST   /api/agent-os/finance/invoices — create invoice
    PATCH  /api/agent-os/finance/invoices/{id}/status — update status
    GET    /api/agent-os/finance/summary — financial summary
    GET    /api/agent-os/finance/reports/monthly — monthly report

Design:
    - All routes are tenant-scoped (auth.tenant_id).
    - Stdlib-only.
    - Multi-currency support (USD default).
    - Invoice lifecycle: draft → sent → paid/overdue → cancelled.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from .auth import AuthContext, SessionStore, extract_bearer_token

log = logging.getLogger(__name__)

INVOICE_STATUSES = ["draft", "sent", "paid", "overdue", "cancelled"]
CURRENCIES = ["USD", "EUR", "GBP"]


def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return status, payload


def _error(status: int, message: str) -> tuple[int, dict[str, Any]]:
    return status, {"error": message}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_finance_routes(
    store: Any = None,
    session_store: SessionStore | None = None,
) -> dict[tuple[str, str], Callable]:
    """Create financial tracking route handlers."""
    _session_store = session_store or SessionStore()

    def _resolve_auth(body: Any, headers: dict[str, str] | None) -> AuthContext:
        if headers:
            token = extract_bearer_token(headers.get("Authorization"))
            if token:
                session = _session_store.get_session(token)
                if session:
                    return session
        return AuthContext(email="", tenant_id=None)

    def _resolve_tenant_id(body: dict[str, Any] | None, headers: dict[str, str] | None) -> tuple[AuthContext, str | None]:
        auth = _resolve_auth(body, headers)
        if not auth.is_authenticated:
            return auth, None
        return auth, auth.tenant_id

    # ── revenue ─────────────────────────────────────────────────

    def list_revenue(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/finance/revenue — list revenue entries."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            limit = 50
            offset = 0
            if body:
                if body.get("limit"):
                    limit = min(int(body["limit"]), 200)
                if body.get("offset"):
                    offset = int(body["offset"])

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            total_cursor = conn.execute(
                "SELECT COUNT(*) FROM revenue_entries WHERE tenant_id = ?", (tenant_id,)
            )
            total = total_cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT * FROM revenue_entries WHERE tenant_id = ? ORDER BY recorded_at DESC LIMIT ? OFFSET ?",
                (tenant_id, limit, offset),
            )
            entries = [dict(r) for r in cursor.fetchall()]

            return _json_response(200, {"entries": entries, "count": len(entries), "total": total})
        except Exception as e:
            log.exception("Failed to list revenue")
            return _error(500, str(e))

    def create_revenue(body: dict[str, Any], headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/finance/revenue — record revenue."""
        try:
            if not body or not isinstance(body, dict):
                return _error(400, "body must be a JSON object")

            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            description = (body.get("description") or "").strip()
            if not description:
                return _error(400, "description is required")
            if len(description) > 500:
                return _error(400, "description max 500 chars")

            amount = body.get("amount")
            if amount is None:
                return _error(400, "amount is required")
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return _error(400, "amount must be numeric")
            if amount < 0:
                return _error(400, "amount cannot be negative")

            currency = body.get("currency", "USD")
            if currency not in CURRENCIES:
                return _error(400, f"currency must be one of: {', '.join(CURRENCIES)}")

            source = body.get("source", "manual")
            engagement_id = body.get("engagementId")

            revenue_id = str(uuid.uuid4())
            now = _now()

            conn = store._get_conn()
            conn.execute(
                """INSERT INTO revenue_entries
                   (id, tenant_id, engagement_id, description, amount, currency, source, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (revenue_id, tenant_id, engagement_id, description, amount, currency, source, now),
            )
            conn.commit()

            return _json_response(201, {
                "id": revenue_id,
                "description": description,
                "amount": amount,
                "currency": currency,
                "source": source,
                "recorded_at": now,
            })
        except Exception as e:
            log.exception("Failed to create revenue entry")
            return _error(500, str(e))

    # ── costs ───────────────────────────────────────────────────

    def list_costs(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/finance/costs — list cost entries."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            limit = 50
            offset = 0
            if body:
                if body.get("limit"):
                    limit = min(int(body["limit"]), 200)
                if body.get("offset"):
                    offset = int(body["offset"])

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            total_cursor = conn.execute(
                "SELECT COUNT(*) FROM cost_entries WHERE tenant_id = ?", (tenant_id,)
            )
            total = total_cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT * FROM cost_entries WHERE tenant_id = ? ORDER BY recorded_at DESC LIMIT ? OFFSET ?",
                (tenant_id, limit, offset),
            )
            entries = [dict(r) for r in cursor.fetchall()]

            return _json_response(200, {"entries": entries, "count": len(entries), "total": total})
        except Exception as e:
            log.exception("Failed to list costs")
            return _error(500, str(e))

    def create_cost(body: dict[str, Any], headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/finance/costs — record cost."""
        try:
            if not body or not isinstance(body, dict):
                return _error(400, "body must be a JSON object")

            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            description = (body.get("description") or "").strip()
            if not description:
                return _error(400, "description is required")
            if len(description) > 500:
                return _error(400, "description max 500 chars")

            amount = body.get("amount")
            if amount is None:
                return _error(400, "amount is required")
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return _error(400, "amount must be numeric")
            if amount < 0:
                return _error(400, "amount cannot be negative")

            currency = body.get("currency", "USD")
            if currency not in CURRENCIES:
                return _error(400, f"currency must be one of: {', '.join(CURRENCIES)}")

            category = body.get("category", "operational")
            engagement_id = body.get("engagementId")

            cost_id = str(uuid.uuid4())
            now = _now()

            conn = store._get_conn()
            conn.execute(
                """INSERT INTO cost_entries
                   (id, tenant_id, engagement_id, description, amount, currency, category, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (cost_id, tenant_id, engagement_id, description, amount, currency, category, now),
            )
            conn.commit()

            return _json_response(201, {
                "id": cost_id,
                "description": description,
                "amount": amount,
                "currency": currency,
                "category": category,
                "recorded_at": now,
            })
        except Exception as e:
            log.exception("Failed to create cost entry")
            return _error(500, str(e))

    # ── invoices ────────────────────────────────────────────────

    def list_invoices(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/finance/invoices — list invoices."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            status_filter = None
            limit = 50
            offset = 0
            if body:
                if body.get("status"):
                    status_filter = body["status"]
                if body.get("limit"):
                    limit = min(int(body["limit"]), 200)
                if body.get("offset"):
                    offset = int(body["offset"])

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            where_clauses = ["tenant_id = ?"]
            params: list[Any] = [tenant_id]
            if status_filter:
                where_clauses.append("status = ?")
                params.append(status_filter)

            where_sql = " AND ".join(where_clauses)
            total_cursor = conn.execute(
                f"SELECT COUNT(*) FROM invoices WHERE {where_sql}", params
            )
            total = total_cursor.fetchone()[0]

            params.extend([limit, offset])
            cursor = conn.execute(
                f"SELECT * FROM invoices WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            )
            invoices = [dict(r) for r in cursor.fetchall()]

            return _json_response(200, {"invoices": invoices, "count": len(invoices), "total": total})
        except Exception as e:
            log.exception("Failed to list invoices")
            return _error(500, str(e))

    def create_invoice(body: dict[str, Any], headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/finance/invoices — create invoice."""
        try:
            if not body or not isinstance(body, dict):
                return _error(400, "body must be a JSON object")

            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            invoice_number = (body.get("invoiceNumber") or "").strip()
            if not invoice_number:
                return _error(400, "invoiceNumber is required")
            if len(invoice_number) > 50:
                return _error(400, "invoiceNumber max 50 chars")

            amount = body.get("amount")
            if amount is None:
                return _error(400, "amount is required")
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return _error(400, "amount must be numeric")
            if amount < 0:
                return _error(400, "amount cannot be negative")

            currency = body.get("currency", "USD")
            if currency not in CURRENCIES:
                return _error(400, f"currency must be one of: {', '.join(CURRENCIES)}")

            engagement_id = body.get("engagementId")
            notes = body.get("notes")
            due_at = body.get("dueAt")

            invoice_id = str(uuid.uuid4())
            now = _now()

            store._get_conn().execute(
                """INSERT INTO invoices
                   (id, tenant_id, engagement_id, invoice_number, amount, currency, status, notes, due_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (invoice_id, tenant_id, engagement_id, invoice_number, amount, currency, "draft", notes, due_at, now, now),
            )
            store._get_conn().commit()

            return _json_response(201, {
                "id": invoice_id,
                "invoice_number": invoice_number,
                "amount": amount,
                "currency": currency,
                "status": "draft",
                "created_at": now,
            })
        except Exception as e:
            log.exception("Failed to create invoice")
            return _error(500, str(e))

    def update_invoice_status(body: dict[str, Any], headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """PATCH /api/agent-os/finance/invoices/{id}/status — update status."""
        try:
            if not body or not isinstance(body, dict):
                return _error(400, "body must be a JSON object")

            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            invoice_id = path_params.get("id", "")
            if not invoice_id:
                return _error(400, "id required")

            new_status = (body.get("status") or "").strip()
            if new_status not in INVOICE_STATUSES:
                return _error(400, f"status must be one of: {', '.join(INVOICE_STATUSES)}")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            existing = conn.execute(
                "SELECT * FROM invoices WHERE id = ? AND tenant_id = ?",
                (invoice_id, tenant_id),
            ).fetchone()
            if not existing:
                return _error(404, "Invoice not found")

            now = _now()
            paid_at = existing["paid_at"]
            if new_status == "paid":
                paid_at = now

            conn.execute(
                """UPDATE invoices
                   SET status = ?, paid_at = ?, updated_at = ?
                   WHERE id = ? AND tenant_id = ?""",
                (new_status, paid_at, now, invoice_id, tenant_id),
            )
            conn.commit()

            return _json_response(200, {
                "id": invoice_id,
                "status": new_status,
                "paid_at": paid_at,
                "updated_at": now,
            })
        except Exception as e:
            log.exception("Failed to update invoice status")
            return _error(500, str(e))

    # ── summary & reports ───────────────────────────────────────

    def get_summary(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/finance/summary — financial summary."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

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
                """SELECT COALESCE(SUM(amount), 0) as total FROM invoices
                   WHERE tenant_id = ? AND status IN ('sent', 'overdue')""",
                (tenant_id,),
            ).fetchone()
            outstanding = outstanding_row["total"] if outstanding_row else 0

            overdue_row = conn.execute(
                """SELECT COALESCE(SUM(amount), 0) as total FROM invoices
                   WHERE tenant_id = ? AND status = 'overdue'""",
                (tenant_id,),
            ).fetchone()
            overdue = overdue_row["total"] if overdue_row else 0

            invoice_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM invoices WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()["cnt"]

            paid_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM invoices WHERE tenant_id = ? AND status = 'paid'",
                (tenant_id,),
            ).fetchone()["cnt"]

            profit = total_revenue - total_costs
            margin = (profit / total_revenue * 100) if total_revenue > 0 else 0

            return _json_response(200, {
                "totalRevenue": total_revenue,
                "totalCosts": total_costs,
                "profit": profit,
                "marginPercent": round(margin, 2),
                "outstandingInvoices": outstanding,
                "overdueInvoices": overdue,
                "invoiceCount": invoice_count,
                "paidInvoiceCount": paid_count,
            })
        except Exception as e:
            log.exception("Failed to get financial summary")
            return _error(500, str(e))

    def get_monthly_report(body: dict[str, Any] | None, headers: dict[str, str] | None = None, **path_params: str) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/finance/reports/monthly — monthly report."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            conn = store._get_conn()
            conn.row_factory = sqlite3.Row

            # Get monthly revenue for last 12 months
            revenue_rows = conn.execute(
                """SELECT strftime('%Y-%m', recorded_at) as month, SUM(amount) as total
                   FROM revenue_entries WHERE tenant_id = ?
                   GROUP BY month ORDER BY month DESC LIMIT 12""",
                (tenant_id,),
            ).fetchall()

            # Get monthly costs for last 12 months
            cost_rows = conn.execute(
                """SELECT strftime('%Y-%m', recorded_at) as month, SUM(amount) as total
                   FROM cost_entries WHERE tenant_id = ?
                   GROUP BY month ORDER BY month DESC LIMIT 12""",
                (tenant_id,),
            ).fetchall()

            revenue_by_month = {r["month"]: r["total"] for r in revenue_rows}
            costs_by_month = {r["month"]: r["total"] for r in cost_rows}

            all_months = sorted(set(list(revenue_by_month.keys()) + list(costs_by_month.keys())), reverse=True)

            monthly = []
            for month in all_months:
                rev = revenue_by_month.get(month, 0)
                cost = costs_by_month.get(month, 0)
                monthly.append({
                    "month": month,
                    "revenue": rev,
                    "costs": cost,
                    "profit": rev - cost,
                })

            return _json_response(200, {"monthly": monthly})
        except Exception as e:
            log.exception("Failed to get monthly report")
            return _error(500, str(e))

    routes: dict[tuple[str, str], Callable] = {
        ("GET", "/api/agent-os/finance/revenue"): list_revenue,
        ("POST", "/api/agent-os/finance/revenue"): create_revenue,
        ("GET", "/api/agent-os/finance/costs"): list_costs,
        ("POST", "/api/agent-os/finance/costs"): create_cost,
        ("GET", "/api/agent-os/finance/invoices"): list_invoices,
        ("POST", "/api/agent-os/finance/invoices"): create_invoice,
        ("PATCH", "/api/agent-os/finance/invoices/{id}/status"): update_invoice_status,
        ("GET", "/api/agent-os/finance/summary"): get_summary,
        ("GET", "/api/agent-os/finance/reports/monthly"): get_monthly_report,
    }
    return routes
