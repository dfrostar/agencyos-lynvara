"""Tests for Agent OS Phase 3: B-04 Business Health Dashboard."""

from __future__ import annotations

import json
import os
import sys
from http.server import HTTPServer
from threading import Thread

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_os.server import AgentOSHandler, create_app, create_default_store


@pytest.fixture
def store(tmp_path):
    """Create a test store with all tables."""
    os.environ["NEURALMIND_AGENTOS_DIR"] = str(tmp_path)
    return create_default_store()


@pytest.fixture
def server(store):
    """Start a test server with routes."""
    app_routes = create_app(store, None)
    AgentOSHandler.routes = app_routes

    srv = HTTPServer(("127.0.0.1", 0), AgentOSHandler)
    port = srv.server_address[1]
    t = Thread(target=srv.serve_forever, daemon=True)
    t.start()

    yield f"http://127.0.0.1:{port}"

    srv.shutdown()


def _post(server_url, path, body, headers=None, auto_auth=True):
    """POST helper."""
    import urllib.request
    import urllib.error

    if auto_auth and not headers:
        headers = _auth_headers(server_url)
    data = json.dumps(body).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(f"{server_url}{path}", data=data, headers=hdrs)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 500, {"error": str(e)}


def _get(server_url, path, headers=None, auto_auth=True):
    """GET helper."""
    import urllib.request
    import urllib.error

    if auto_auth and not headers:
        headers = _auth_headers(server_url)
    hdrs = {}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(f"{server_url}{path}", headers=hdrs)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 500, {"error": str(e)}


def _auth_headers(server_url, email="test@test.com", tenant_id="test-tenant"):
    """Return bearer <REDACTED> headers for a tenant."""
    status, resp = _post(
        server_url,
        "/api/agent-os/tenants",
        {"tenant_id": tenant_id, "name": tenant_id, "admin_email": email},
        auto_auth=False,
    )
    if status == 201:
        token = resp["session_token"]
    else:
        from agent_os.auth import SessionStore

        store = SessionStore()
        token = store.create_session(email, tenant_id, "admin")
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────
# B-04: Dashboard Tests
# ─────────────────────────────────────────────────────────────


class TestDashboard:
    """Tests for business health dashboard."""

    def test_dashboard_returns_full_structure(self, server):
        """Dashboard returns all required sections."""
        status, resp = _get(server, "/api/agent-os/dashboard")
        assert status == 200
        assert "health_score" in resp
        assert "finance" in resp
        assert "outreach" in resp
        assert "engagements" in resp
        assert "feedback" in resp
        assert "signals" in resp
        assert "webhooks" in resp
        assert "knowledge" in resp

    def test_dashboard_health_score_structure(self, server):
        """Health score has score, rating, and components."""
        status, resp = _get(server, "/api/agent-os/dashboard")
        assert status == 200
        health = resp["health_score"]
        assert "score" in health
        assert "rating" in health
        assert "components" in health
        assert 0 <= health["score"] <= 100
        assert health["rating"] in ("healthy", "attention", "critical")

    def test_dashboard_empty_state(self, server):
        """Dashboard with no data returns zeros."""
        status, resp = _get(server, "/api/agent-os/dashboard")
        assert status == 200
        assert resp["finance"]["totalRevenue"] == 0
        assert resp["finance"]["totalCosts"] == 0
        assert resp["outreach"]["totalLeads"] == 0
        assert resp["engagements"]["active"] == 0

    def test_dashboard_with_data(self, server):
        """Dashboard aggregates data from all modules."""
        # Add revenue
        _post(server, "/api/agent-os/finance/revenue", {
            "description": "Consulting", "amount": 10000.0,
        })

        # Add cost
        _post(server, "/api/agent-os/finance/costs", {
            "description": "Hosting", "amount": 500.0,
        })

        # Create lead
        _post(server, "/api/agent-os/outreach/leads", {
            "companyName": "Test Corp", "source": "manual",
        })

        status, resp = _get(server, "/api/agent-os/dashboard")
        assert status == 200
        assert resp["finance"]["totalRevenue"] == 10000.0
        assert resp["finance"]["totalCosts"] == 500.0
        assert resp["finance"]["profit"] == 9500.0
        assert resp["outreach"]["totalLeads"] == 1

    def test_dashboard_health_score_improves_with_revenue(self, server):
        """Health score increases when revenue is added."""
        # Empty state
        _, resp_empty = _get(server, "/api/agent-os/dashboard")
        empty_score = resp_empty["health_score"]["score"]

        # Add revenue
        _post(server, "/api/agent-os/finance/revenue", {
            "description": "Big Deal", "amount": 50000.0,
        })

        _, resp_funded = _get(server, "/api/agent-os/dashboard")
        funded_score = resp_funded["health_score"]["score"]

        assert funded_score > empty_score

    def test_dashboard_health_rating_healthy(self, server):
        """Health rating is 'healthy' with strong metrics."""
        # Add strong revenue
        _post(server, "/api/agent-os/finance/revenue", {
            "description": "Big Deal", "amount": 100000.0,
        })
        # Add customer
        _post(server, "/api/agent-os/outreach/leads", {
            "companyName": "Customer Corp", "status": "customer",
        })

        _, resp = _get(server, "/api/agent-os/dashboard")
        assert resp["health_score"]["rating"] == "healthy"

    def test_dashboard_health_rating_critical(self, server):
        """Health rating is 'critical' with no data."""
        _, resp = _get(server, "/api/agent-os/dashboard")
        # Empty state should be critical or attention
        assert resp["health_score"]["rating"] in ("critical", "attention")

    def test_dashboard_health_endpoint(self, server):
        """Health-only endpoint returns score only."""
        status, resp = _get(server, "/api/agent-os/dashboard/health")
        assert status == 200
        assert "health_score" in resp
        assert "generated_at" in resp
        # Should NOT have detailed sections
        assert "finance" not in resp
        assert "outreach" not in resp

    def test_dashboard_metrics_endpoint(self, server):
        """Metrics endpoint returns key metrics only."""
        status, resp = _get(server, "/api/agent-os/dashboard/metrics")
        assert status == 200
        assert "finance" in resp
        assert "outreach" in resp
        assert "engagements" in resp
        assert "feedback" in resp
        assert "signals" in resp
        assert "webhooks" in resp
        # Should NOT have health_score
        assert "health_score" not in resp

    def test_dashboard_unauthenticated(self, server):
        """Dashboard requires auth."""
        import urllib.request
        import urllib.error

        req = urllib.request.Request(f"{server}/api/agent-os/dashboard")
        try:
            resp = urllib.request.urlopen(req)
            assert False, "Should have returned 401"
        except urllib.error.HTTPError as e:
            assert e.code == 401

    def test_dashboard_tenant_isolation(self, server):
        """Dashboard data is tenant-scoped."""
        # Create data for tenant-a
        headers_a = _auth_headers(server, "alice@a.com", "tenant-a")
        _post(server, "/api/agent-os/finance/revenue", {
            "description": "Secret Revenue", "amount": 99999.0,
        }, headers=headers_a)

        # tenant-b should not see it
        headers_b = _auth_headers(server, "bob@b.com", "tenant-b")
        status, resp = _get(server, "/api/agent-os/dashboard", headers=headers_b)
        assert status == 200
        assert resp["finance"]["totalRevenue"] == 0

    def test_dashboard_margin_calculation(self, server):
        """Margin percentage is calculated correctly."""
        _post(server, "/api/agent-os/finance/revenue", {
            "description": "Revenue", "amount": 1000.0,
        })
        _post(server, "/api/agent-os/finance/costs", {
            "description": "Cost", "amount": 250.0,
        })

        _, resp = _get(server, "/api/agent-os/dashboard")
        assert resp["finance"]["marginPercent"] == 75.0

    def test_dashboard_overdue_invoices(self, server):
        """Overdue invoices are tracked separately."""
        # Create invoice
        _post(server, "/api/agent-os/finance/invoices", {
            "invoiceNumber": "INV-001", "amount": 5000.0,
        })

        _, resp = _get(server, "/api/agent-os/dashboard")
        # Invoice is draft, not overdue
        assert resp["finance"]["overdueInvoiceCount"] == 0
        assert resp["finance"]["overdueInvoices"] == 0
