"""Tests for AgencyOS financial tracking module."""
from __future__ import annotations

import json
import os
import threading
from http.server import HTTPServer

import pytest

from agent_os.server import AgentOSHandler, create_default_store, create_app


@pytest.fixture
def server(tmp_path):
    os.environ["NEURALMIND_AGENTOS_DIR"] = str(tmp_path)
    store = create_default_store()
    app_routes = create_app(store, None)
    AgentOSHandler.routes = app_routes

    srv = HTTPServer(("127.0.0.1", 0), AgentOSHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def _create_session(server_url, tenant_id):
    import urllib.request
    body = json.dumps({"tenant_id": tenant_id, "name": tenant_id.title(), "admin_email": f"@{tenant_id}.com"}).encode()
    req = urllib.request.Request(
        f"{server_url}/api/agent-os/tenants", data=body,
        headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        return data.get("session_token", "")
    except Exception:
        from agent_os.auth import SessionStore
        ss = SessionStore()
        return ss.create_session(f"@{tenant_id}.com", tenant_id, "admin")


def _auth_headers(server_url, tenant_id="test-tenant"):
    token = _create_session(server_url, tenant_id)
    return {"Authorization": f"Bearer {token}"}


def _post(server_url, path, body, headers=None, auto_auth=True):
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


def _patch(server_url, path, body, headers=None, auto_auth=True):
    import urllib.request
    import urllib.error
    if auto_auth and not headers:
        headers = _auth_headers(server_url)
    data = json.dumps(body).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(f"{server_url}{path}", data=data, headers=hdrs, method="PATCH")
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 500, {"error": str(e)}


class TestRevenue:
    def test_list_empty(self, server):
        status, payload = _get(server, "/api/agent-os/finance/revenue")
        assert status == 200
        assert payload["count"] == 0

    def test_create_revenue(self, server):
        status, payload = _post(server, "/api/agent-os/finance/revenue", {
            "description": "Consulting fee",
            "amount": 5000.00,
        })
        assert status == 201
        assert payload["amount"] == 5000.00

    def test_revenue_requires_description(self, server):
        status, _ = _post(server, "/api/agent-os/finance/revenue", {"amount": 100})
        assert status == 400

    def test_revenue_requires_amount(self, server):
        status, _ = _post(server, "/api/agent-os/finance/revenue", {"description": "Test"})
        assert status == 400

    def test_revenue_negative_amount_rejected(self, server):
        status, _ = _post(server, "/api/agent-os/finance/revenue", {
            "description": "Bad", "amount": -100
        })
        assert status == 400


class TestCosts:
    def test_create_cost(self, server):
        status, payload = _post(server, "/api/agent-os/finance/costs", {
            "description": "AWS hosting",
            "amount": 200.00,
            "category": "infrastructure",
        })
        assert status == 201
        assert payload["category"] == "infrastructure"


class TestInvoices:
    def test_create_invoice(self, server):
        status, payload = _post(server, "/api/agent-os/finance/invoices", {
            "invoiceNumber": "INV-001",
            "amount": 10000.00,
        })
        assert status == 201
        assert payload["status"] == "draft"
        assert payload["invoice_number"] == "INV-001"

    def test_invoice_requires_number(self, server):
        status, _ = _post(server, "/api/agent-os/finance/invoices", {"amount": 100})
        assert status == 400

    def test_invoice_status_lifecycle(self, server):
        _, inv = _post(server, "/api/agent-os/finance/invoices", {
            "invoiceNumber": "INV-002", "amount": 5000
        })
        inv_id = inv["id"]

        # Send
        status, _ = _patch(server, f"/api/agent-os/finance/invoices/{inv_id}/status", {
            "status": "sent"
        })
        assert status == 200

        # Pay
        status, payload = _patch(server, f"/api/agent-os/finance/invoices/{inv_id}/status", {
            "status": "paid"
        })
        assert status == 200
        assert payload["paid_at"] is not None

    def test_invalid_status_rejected(self, server):
        _, inv = _post(server, "/api/agent-os/finance/invoices", {
            "invoiceNumber": "INV-003", "amount": 500
        })
        status, _ = _patch(server, f"/api/agent-os/finance/invoices/{inv['id']}/status", {
            "status": "invalid"
        })
        assert status == 400


class TestSummary:
    def test_summary(self, server):
        # Create some data
        _post(server, "/api/agent-os/finance/revenue", {
            "description": "Revenue 1", "amount": 10000
        })
        _post(server, "/api/agent-os/finance/costs", {
            "description": "Cost 1", "amount": 3000
        })

        status, payload = _get(server, "/api/agent-os/finance/summary")
        assert status == 200
        assert payload["totalRevenue"] == 10000
        assert payload["totalCosts"] == 3000
        assert payload["profit"] == 7000
        assert payload["marginPercent"] == 70.0


class TestMonthlyReport:
    def test_monthly_report(self, server):
        _post(server, "/api/agent-os/finance/revenue", {
            "description": "Revenue", "amount": 5000
        })
        status, payload = _get(server, "/api/agent-os/finance/reports/monthly")
        assert status == 200
        assert "monthly" in payload


class TestFinanceAuth:
    def test_unauthenticated_revenue_rejected(self, server):
        status, _ = _post(server, "/api/agent-os/finance/revenue", {
            "description": "X", "amount": 100
        }, auto_auth=False)
        assert status == 401

    def test_unauthenticated_summary_rejected(self, server):
        status, _ = _get(server, "/api/agent-os/finance/summary", auto_auth=False)
        assert status == 401


class TestFinanceTenantIsolation:
    def test_revenue_tenant_scoped(self, server):
        _post(server, "/api/agent-os/finance/revenue", {
            "description": "Acme Revenue", "amount": 5000
        })
        headers = _auth_headers(server, "other-tenant")
        status, payload = _get(server, "/api/agent-os/finance/revenue", headers=headers, auto_auth=False)
        assert status == 200
        assert payload["count"] == 0
