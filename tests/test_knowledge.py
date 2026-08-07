"""Tests for AgencyOS knowledge base module."""
from __future__ import annotations

import json
import os
import threading
from http.server import HTTPServer

import pytest

from agent_os.server import AgentOSHandler, create_default_store, create_app


@pytest.fixture
def server(tmp_path):
    """Start a test server with routes."""
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
    """Create a session for the given tenant, handling existing tenants."""
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


def _get(server_url, path, body=None, headers=None, auto_auth=True):
    import urllib.request
    import urllib.error
    if auto_auth and not headers:
        headers = _auth_headers(server_url)
    hdrs = {}
    if headers:
        hdrs.update(headers)
    data = None
    if body:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{server_url}{path}", data=data, headers=hdrs)
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


def _delete(server_url, path, headers=None, auto_auth=True):
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


class TestKnowledgeList:
    def test_list_empty(self, server):
        status, payload = _get(server, "/api/agent-os/knowledge")
        assert status == 200
        assert payload["count"] == 0

    def test_list_returns_entries(self, server):
        _post(server, "/api/agent-os/knowledge", {
            "title": "Test Decision",
            "content": "We chose X because Y",
        })
        status, payload = _get(server, "/api/agent-os/knowledge")
        assert status == 200
        assert payload["count"] == 1
        assert payload["entries"][0]["title"] == "Test Decision"


class TestKnowledgeCreate:
    def test_create_basic(self, server):
        status, payload = _post(server, "/api/agent-os/knowledge", {
            "title": "Architecture Decision",
            "content": "We chose microservices for scalability",
        })
        assert status == 201
        assert payload["title"] == "Architecture Decision"
        assert "id" in payload

    def test_create_requires_title(self, server):
        status, payload = _post(server, "/api/agent-os/knowledge", {
            "content": "Missing title",
        })
        assert status == 400

    def test_create_requires_content(self, server):
        status, payload = _post(server, "/api/agent-os/knowledge", {
            "title": "Missing content",
        })
        assert status == 400

    def test_create_with_metadata(self, server):
        status, payload = _post(server, "/api/agent-os/knowledge", {
            "title": "SOP: Incident Response",
            "content": "Steps for handling incidents",
            "entryType": "sop",
            "metadata": {"priority": "high"},
        })
        assert status == 201
        assert payload["entry_type"] == "sop"


class TestKnowledgeGet:
    def test_get_by_id(self, server):
        _, created = _post(server, "/api/agent-os/knowledge", {
            "title": "Test",
            "content": "Content",
        })
        status, payload = _get(server, f"/api/agent-os/knowledge/{created['id']}")
        assert status == 200
        assert payload["id"] == created["id"]
        assert payload["title"] == "Test"

    def test_get_not_found(self, server):
        status, payload = _get(server, "/api/agent-os/knowledge/nonexistent-id-12345")
        assert status == 404


class TestKnowledgeUpdate:
    def test_update_title(self, server):
        _, created = _post(server, "/api/agent-os/knowledge", {
            "title": "Old Title",
            "content": "Content",
        })
        status, payload = _patch(server, f"/api/agent-os/knowledge/{created['id']}", {
            "title": "New Title",
        })
        assert status == 200
        assert payload["title"] == "New Title"

    def test_update_not_found(self, server):
        status, payload = _patch(server, "/api/agent-os/knowledge/nonexistent-id-12345", {
            "title": "X",
        })
        assert status == 404


class TestKnowledgeDelete:
    def test_delete(self, server):
        _, created = _post(server, "/api/agent-os/knowledge", {
            "title": "To Delete",
            "content": "Content",
        })
        status, payload = _delete(server, f"/api/agent-os/knowledge/{created['id']}")
        assert status == 200
        status, _ = _get(server, f"/api/agent-os/knowledge/{created['id']}")
        assert status == 404


class TestKnowledgeSearch:
    def test_search_full_text(self, server):
        _post(server, "/api/agent-os/knowledge", {
            "title": "Python Performance",
            "content": "Optimizing Python code for speed",
        })
        _post(server, "/api/agent-os/knowledge", {
            "title": "Database Indexing",
            "content": "How to index SQL tables",
        })
        # GET search with query param
        import urllib.request
        import urllib.error
        headers = _auth_headers(server)
        req = urllib.request.Request(
            f"{server}/api/agent-os/knowledge/search?q=python",
            headers=headers
        )
        try:
            resp = urllib.request.urlopen(req)
            payload = json.loads(resp.read())
            assert payload["count"] >= 1
        except urllib.error.HTTPError as e:
            payload = json.loads(e.read())
            pytest.fail(f"Search failed: {e.code} {payload}")

    def test_search_requires_query(self, server):
        status, payload = _get(server, "/api/agent-os/knowledge/search")
        assert status == 400


class TestKnowledgeAuth:
    def test_unauthenticated_create_rejected(self, server):
        status, _ = _post(server, "/api/agent-os/knowledge", {
            "title": "X",
            "content": "Y",
        }, auto_auth=False)
        assert status == 401

    def test_unauthenticated_list_rejected(self, server):
        status, _ = _get(server, "/api/agent-os/knowledge", auto_auth=False)
        assert status == 401


class TestKnowledgeTenantIsolation:
    def test_entries_tenant_scoped(self, server):
        _post(server, "/api/agent-os/knowledge", {
            "title": "Test Tenant Secret",
            "content": "Test tenant content",
        })
        headers = _auth_headers(server, "other-tenant")
        status, payload = _get(server, "/api/agent-os/knowledge", headers=headers, auto_auth=False)
        assert status == 200
        assert payload["count"] == 0
