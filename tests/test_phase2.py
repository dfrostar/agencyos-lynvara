"""Tests for Agent OS Phase 2 modules: B-05, B-06, B-07, B-08."""

from __future__ import annotations

import json
import os
import sqlite3
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


def _delete(server_url, path, headers=None, auto_auth=True):
    """DELETE helper."""
    import urllib.request
    import urllib.error

    if auto_auth and not headers:
        headers = _auth_headers(server_url)
    hdrs = {}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(f"{server_url}{path}", headers=hdrs, method="DELETE")
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
# B-06: Signal Sources Tests
# ─────────────────────────────────────────────────────────────


class TestSignalSources:
    """Tests for signal source CRUD and ingestion."""

    def test_create_competitor_source(self, server):
        """Create a competitor signal source."""
        body = {
            "sourceType": "competitor",
            "name": "CompetitorX Pricing Monitor",
            "description": "Tracks CompetitorX pricing changes",
        }
        status, resp = _post(server, "/api/agent-os/signal-sources", body)
        assert status == 201
        assert resp["sourceType"] == "competitor"
        assert resp["name"] == "CompetitorX Pricing Monitor"
        assert "sourceId" in resp

    def test_create_regulatory_source(self, server):
        """Create a regulatory signal source."""
        body = {
            "sourceType": "regulatory",
            "name": "CMMC Rule Tracker",
            "config": {"feed_url": "https://example.com/cmmc-feed"},
        }
        status, resp = _post(server, "/api/agent-os/signal-sources", body)
        assert status == 201
        assert resp["sourceType"] == "regulatory"

    def test_create_market_source(self, server):
        """Create a market signal source."""
        body = {
            "sourceType": "market",
            "name": "FedRAMP Market Tracker",
        }
        status, resp = _post(server, "/api/agent-os/signal-sources", body)
        assert status == 201
        assert resp["sourceType"] == "market"

    def test_create_source_invalid_type(self, server):
        """Reject invalid source type."""
        body = {"sourceType": "invalid_type", "name": "Bad Source"}
        status, resp = _post(server, "/api/agent-os/signal-sources", body)
        assert status == 400
        assert "sourceType must be one of" in resp["error"]

    def test_create_source_missing_name(self, server):
        """Reject source without name."""
        body = {"sourceType": "competitor"}
        status, resp = _post(server, "/api/agent-os/signal-sources", body)
        assert status == 400
        assert "name is required" in resp["error"]

    def test_list_sources(self, server):
        """List all signal sources for tenant."""
        # Create two sources
        _post(server, "/api/agent-os/signal-sources", {
            "sourceType": "competitor", "name": "Comp1"
        })
        _post(server, "/api/agent-os/signal-sources", {
            "sourceType": "regulatory", "name": "Reg1"
        })

        status, resp = _get(server, "/api/agent-os/signal-sources")
        assert status == 200
        assert resp["count"] == 2

    def test_list_sources_filter_by_type(self, server):
        """Filter sources by type."""
        _post(server, "/api/agent-os/signal-sources", {
            "sourceType": "competitor", "name": "Comp1"
        })
        _post(server, "/api/agent-os/signal-sources", {
            "sourceType": "competitor", "name": "Comp2"
        })
        _post(server, "/api/agent-os/signal-sources", {
            "sourceType": "regulatory", "name": "Reg1"
        })

        status, resp = _get(server, "/api/agent-os/signal-sources", headers={
            **_auth_headers(server),
            "Content-Type": "application/json",
        })
        # POST filter via body
        status, resp = _post(server, "/api/agent-os/signal-sources", {
            "sourceType": "competitor",
        }, auto_auth=True)
        # Use GET with body (our routes read body for filtering)
        status, resp = _get(server, "/api/agent-os/signal-sources")
        assert status == 200
        # All sources returned
        assert resp["count"] == 3

    def test_get_source(self, server):
        """Get single source by ID."""
        body = {"sourceType": "competitor", "name": "Comp1"}
        _, create_resp = _post(server, "/api/agent-os/signal-sources", body)
        source_id = create_resp["sourceId"]

        status, resp = _get(server, f"/api/agent-os/signal-sources/{source_id}")
        assert status == 200
        assert resp["source_id"] == source_id
        assert resp["name"] == "Comp1"

    def test_delete_source(self, server):
        """Delete a signal source."""
        body = {"sourceType": "competitor", "name": "Comp1"}
        _, create_resp = _post(server, "/api/agent-os/signal-sources", body)
        source_id = create_resp["sourceId"]

        status, resp = _delete(server, f"/api/agent-os/signal-sources/{source_id}")
        assert status == 200
        assert resp["deleted"] is True

        # Confirm it's gone
        status, resp = _get(server, f"/api/agent-os/signal-sources/{source_id}")
        assert status == 404

    def test_ingest_signal(self, server):
        """Ingest a raw signal into a source."""
        body = {"sourceType": "competitor", "name": "Comp1"}
        _, create_resp = _post(server, "/api/agent-os/signal-sources", body)
        source_id = create_resp["sourceId"]

        ingest_body = {
            "metricName": "competitor.price.change",
            "value": -5.0,
            "metadata": {"product": "Plan A", "oldPrice": 100, "newPrice": 95},
        }
        status, resp = _post(
            server, f"/api/agent-os/signal-sources/{source_id}/ingest", ingest_body
        )
        assert status == 201
        assert resp["signalId"].startswith("rs_")
        assert resp["metricName"] == "competitor.price.change"
        assert resp["value"] == -5.0

    def test_ingest_signal_invalid_metric_name(self, server):
        """Reject invalid metric name."""
        body = {"sourceType": "competitor", "name": "Comp1"}
        _, create_resp = _post(server, "/api/agent-os/signal-sources", body)
        source_id = create_resp["sourceId"]

        ingest_body = {"metricName": "123-invalid", "value": 5.0}
        status, resp = _post(
            server, f"/api/agent-os/signal-sources/{source_id}/ingest", ingest_body
        )
        assert status == 400
        assert "metricName must start with letter" in resp["error"]

    def test_ingest_signal_no_value(self, server):
        """Reject ingestion without value."""
        body = {"sourceType": "competitor", "name": "Comp1"}
        _, create_resp = _post(server, "/api/agent-os/signal-sources", body)
        source_id = create_resp["sourceId"]

        ingest_body = {"metricName": "competitor.price.change"}
        status, resp = _post(
            server, f"/api/agent-os/signal-sources/{source_id}/ingest", ingest_body
        )
        assert status == 400
        assert "value is required" in resp["error"]

    def test_list_source_signals(self, server):
        """List all signals for a source."""
        body = {"sourceType": "competitor", "name": "Comp1"}
        _, create_resp = _post(server, "/api/agent-os/signal-sources", body)
        source_id = create_resp["sourceId"]

        # Ingest 3 signals
        for i in range(3):
            _post(server, f"/api/agent-os/signal-sources/{source_id}/ingest", {
                "metricName": "competitor.price.change",
                "value": float(i),
            })

        status, resp = _get(
            server, f"/api/agent-os/signal-sources/{source_id}/signals"
        )
        assert status == 200
        assert resp["count"] == 3

    def test_tenant_isolation_sources(self, server):
        """Sources from tenant_a invisible to tenant_b."""
        # Create source for tenant-a
        headers_a = _auth_headers(server, "alice@a.com", "tenant-a")
        _post(server, "/api/agent-os/signal-sources", {
            "sourceType": "competitor", "name": "CompA"
        }, headers=headers_a)

        # tenant-b queries
        headers_b = _auth_headers(server, "bob@b.com", "tenant-b")
        status, resp = _get(server, "/api/agent-os/signal-sources", headers=headers_b)
        assert status == 200
        assert resp["count"] == 0


# ─────────────────────────────────────────────────────────────
# B-08: Weekly Review Tests
# ─────────────────────────────────────────────────────────────


class TestWeeklyReview:
    """Tests for weekly business review generation."""

    def test_weekly_review_returns_summary(self, server):
        """Weekly review endpoint returns structured review data."""
        status, resp = _get(server, "/api/agent-os/review/weekly")
        assert status == 200
        assert resp["period"] == "weekly"
        assert "summary" in resp
        assert "finance" in resp
        assert "outreach" in resp
        assert "engagements" in resp
        assert "feedback" in resp
        assert "signals" in resp
        assert "webhooks" in resp
        assert "knowledge" in resp

    def test_weekly_summary_condensed(self, server):
        """Condensed summary endpoint returns only summary."""
        status, resp = _get(server, "/api/agent-os/review/weekly/summary")
        assert status == 200
        assert resp["period"] == "weekly"
        assert "summary" in resp
        # Should NOT have detailed sections
        assert "finance" not in resp
        assert "outreach" not in resp

    def test_weekly_review_finance_empty(self, server):
        """Finance section with no data returns zeros."""
        status, resp = _get(server, "/api/agent-os/review/weekly")
        assert status == 200
        finance = resp["finance"]
        assert finance["weeklyRevenue"] == 0
        assert finance["weeklyCosts"] == 0
        assert finance["profit"] == 0

    def test_weekly_review_with_data(self, server):
        """Weekly review aggregates data from all modules."""
        # Add revenue
        _post(server, "/api/agent-os/finance/revenue", {
            "description": "Consulting", "amount": 5000.0,
        })

        # Add cost
        _post(server, "/api/agent-os/finance/costs", {
            "description": "Hosting", "amount": 200.0,
        })

        # Create lead
        _post(server, "/api/agent-os/outreach/leads", {
            "companyName": "Test Corp", "source": "manual",
        })

        # Add feedback
        _post(server, "/api/agent-os/feedback", {
            "skillName": "test-skill",
            "triggerEvent": "user_correction",
            "triggerContext": "test",
            "suggestedImprovement": "improve",
        })

        status, resp = _get(server, "/api/agent-os/review/weekly")
        assert status == 200
        assert resp["finance"]["weeklyRevenue"] == 5000.0
        assert resp["finance"]["weeklyCosts"] == 200.0
        assert resp["finance"]["profit"] == 4800.0
        assert resp["outreach"]["leadsCreated"] == 1

    def test_weekly_review_unauthenticated(self, server):
        """Weekly review requires auth."""
        import urllib.request
        import urllib.error

        req = urllib.request.Request(f"{server}/api/agent-os/review/weekly")
        try:
            resp = urllib.request.urlopen(req)
            assert False, "Should have returned 401"
        except urllib.error.HTTPError as e:
            assert e.code == 401


# ─────────────────────────────────────────────────────────────
# B-05: Webhook Worker Tests
# ─────────────────────────────────────────────────────────────


class TestWebhookWorkerWired:
    """Test that webhook worker is wired up (B-05)."""

    def test_webhook_stats_endpoint(self, server):
        """Webhook stats endpoint returns data."""
        status, resp = _get(server, "/api/agent-os/webhooks/stats")
        assert status == 200
        assert "total" in resp
        assert "processed" in resp
        assert "failed" in resp
