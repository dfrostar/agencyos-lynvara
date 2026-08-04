"""Tests for Agent OS feedback loop routes."""

from __future__ import annotations

import json
import sys
import os
import pytest
from http.server import HTTPServer
from threading import Thread
from unittest.mock import patch

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_os.server import AgentOSHandler, create_default_store, create_app


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


def _post(server_url, path, body):
    """POST helper."""
    import urllib.request
    import urllib.error
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{server_url}{path}", data=data, headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 500, {"error": str(e)}


def _get(server_url, path):
    """GET helper."""
    import urllib.request
    import urllib.error
    req = urllib.request.Request(f"{server_url}{path}")
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 500, {"error": str(e)}


def _patch(server_url, path, body):
    """PATCH helper."""
    import urllib.request
    import urllib.error
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{server_url}{path}", data=data, headers={"Content-Type": "application/json"}, method="PATCH"
    )
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 500, {"error": str(e)}


class TestFeedbackRoutes:
    def test_create_feedback(self, server):
        body = {
            "tenant_id": "test-tenant",
            "skillName": "acm-01",
            "triggerEvent": "user_correction",
            "triggerContext": "User edited output",
            "suggestedImprovement": "Fix guidance",
        }
        status, resp = _post(server, "/api/agent-os/feedback", body)
        assert status == 201
        assert resp["status"] == "success"
        assert resp["data"]["feedback"]["skillName"] == "acm-01"
        assert resp["data"]["feedback"]["status"] == "pending"

    def test_create_feedback_validation(self, server):
        """Missing required fields returns 400."""
        body = {"tenant_id": "test-tenant", "skillName": ""}
        status, resp = _post(server, "/api/agent-os/feedback", body)
        assert status == 400
        assert "error" in resp

    def test_create_feedback_invalid_trigger(self, server):
        body = {
            "tenant_id": "test-tenant",
            "skillName": "acm-01",
            "triggerEvent": "invalid_event",
            "triggerContext": "test",
            "suggestedImprovement": "test",
        }
        status, resp = _post(server, "/api/agent-os/feedback", body)
        assert status == 400

    def test_list_feedback(self, server):
        """List feedback returns created items."""
        # Create one first
        body = {
            "tenant_id": "test-tenant",
            "skillName": "acm-02",
            "triggerEvent": "test_failure",
            "triggerContext": "Test failed",
            "suggestedImprovement": "Fix",
        }
        _post(server, "/api/agent-os/feedback", body)

        # List
        status, resp = _get(server, "/api/agent-os/feedback")
        assert status == 200
        assert "data" in resp
        assert "feedback" in resp["data"]

    def test_get_feedback_by_id(self, server):
        """Get single feedback."""
        body = {
            "tenant_id": "test-tenant",
            "skillName": "acm-03",
            "triggerEvent": "qa_finding",
            "triggerContext": "Gap found",
            "suggestedImprovement": "Address it",
        }
        _, create_resp = _post(server, "/api/agent-os/feedback", body)
        feedback_id = create_resp["data"]["feedback"]["id"]

        status, resp = _get(server, f"/api/agent-os/feedback/{feedback_id}?tenant_id=test-tenant")
        assert status == 200
        assert resp["data"]["feedback"]["id"] == feedback_id

    def test_get_feedback_not_found(self, server):
        status, resp = _get(server, "/api/agent-os/feedback/nonexistent?tenant_id=test-tenant")
        assert status == 404

    def test_update_status(self, server):
        """Update feedback status."""
        body = {
            "tenant_id": "test-tenant",
            "skillName": "acm-04",
            "triggerEvent": "user_correction",
            "triggerContext": "test",
            "suggestedImprovement": "test",
        }
        _, create_resp = _post(server, "/api/agent-os/feedback", body)
        feedback_id = create_resp["data"]["feedback"]["id"]

        status, resp = _patch(
            server,
            f"/api/agent-os/feedback/{feedback_id}/status",
            {"tenant_id": "test-tenant", "status": "reviewed"},
        )
        assert status == 200
        assert resp["data"]["feedback"]["status"] == "reviewed"

    def test_update_status_invalid(self, server):
        body = {"tenant_id": "test-tenant", "skillName": "x", "triggerEvent": "test_failure",
                "triggerContext": "y", "suggestedImprovement": "z"}
        _, create_resp = _post(server, "/api/agent-os/feedback", body)
        feedback_id = create_resp["data"]["feedback"]["id"]

        status, resp = _patch(
            server,
            f"/api/agent-os/feedback/{feedback_id}/status",
            {"tenant_id": "test-tenant", "status": "invalid_status"},
        )
        assert status == 400

    def test_stats(self, server):
        """Stats endpoint returns counts."""
        body = {
            "tenant_id": "test-tenant",
            "skillName": "acm-05",
            "triggerEvent": "support_ticket",
            "triggerContext": "ticket",
            "suggestedImprovement": "improve",
        }
        _post(server, "/api/agent-os/feedback", body)

        status, resp = _get(server, "/api/agent-os/feedback/stats?tenant_id=test-tenant")
        assert status == 200
        assert "stats" in resp["data"]

    def test_digest(self, server):
        """Digest endpoint returns summary."""
        body = {
            "tenant_id": "test-tenant",
            "skillName": "acm-06",
            "triggerEvent": "test_failure",
            "triggerContext": "fail",
            "suggestedImprovement": "fix",
        }
        _post(server, "/api/agent-os/feedback", body)

        status, resp = _get(server, "/api/agent-os/feedback/digest?tenant_id=test-tenant")
        assert status == 200
        assert "digest" in resp["data"]

    def test_capture_user_correction(self, server):
        body = {
            "tenant_id": "test-tenant",
            "skillName": "acm-07",
            "originalOutput": "AI output",
            "userEditedOutput": "User edited",
        }
        status, resp = _post(server, "/api/agent-os/feedback/capture/user-correction", body)
        assert status == 201
        assert resp["data"]["feedback"]["skillName"] == "acm-07"

    def test_capture_test_failure(self, server):
        body = {
            "tenant_id": "test-tenant",
            "skillName": "acm-08",
            "testName": "test_auth",
            "errorMessage": "Expected 201 got 500",
        }
        status, resp = _post(server, "/api/agent-os/feedback/capture/test-failure", body)
        assert status == 201

    def test_capture_qa_finding(self, server):
        body = {
            "tenant_id": "test-tenant",
            "skillName": "acm-09",
            "finding": "Missing encryption detail",
            "severity": "high",
        }
        status, resp = _post(server, "/api/agent-os/feedback/capture/qa-finding", body)
        assert status == 201

    def test_closed_loop_applied_creates_knowledge(self, server, tmp_path):
        """When status transitions to 'applied', a knowledge entry is created."""
        body = {
            "tenant_id": "test-tenant",
            "skillName": "acm-10",
            "triggerEvent": "user_correction",
            "triggerContext": "test",
            "suggestedImprovement": "test",
            "originalExecution": "AI said X",
            "userCorrection": "Actually Y",
        }
        _, create_resp = _post(server, "/api/agent-os/feedback", body)
        feedback_id = create_resp["data"]["feedback"]["id"]

        # Apply
        _patch(
            server,
            f"/api/agent-os/feedback/{feedback_id}/status",
            {"tenant_id": "test-tenant", "status": "applied", "reviewedBy": "admin@test"},
        )

        # Check knowledge entry was created
        import sqlite3
        db_path = tmp_path / "agent-os.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM knowledge_entries WHERE source_feedback_id = ?", (feedback_id,)
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row["entry_type"] == "feedback"
        assert "acm-10" in row["title"]
        assert "AI said X" in row["content"]
        assert "Actually Y" in row["content"]

    def test_tenant_isolation(self, server):
        """Feedback from tenant_a is invisible to tenant_b."""
        body_a = {
            "tenant_id": "tenant-a",
            "skillName": "acm-11",
            "triggerEvent": "user_correction",
            "triggerContext": "test",
            "suggestedImprovement": "test",
        }
        _post(server, "/api/agent-os/feedback", body_a)

        # tenant-b queries
        status, resp = _get(server, "/api/agent-os/feedback?tenant_id=tenant-b")
        assert status == 200
        # Should not see tenant-a's data
        for fb in resp["data"]["feedback"]:
            assert fb["tenant_id"] != "tenant-a"
