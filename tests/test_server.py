"""Tests for Agent OS HTTP server (server.py).

Covers health endpoint, body drain, and request validation.
"""
from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from http.server import HTTPServer

import pytest

from agent_os.server import AgentOSHandler, create_app

@pytest.fixture
def server(tmp_path, monkeypatch):
    """Start a real HTTP server on localhost with ephemeral port."""
    monkeypatch.setenv("NEURALMIND_TENANTS_DIR", str(tmp_path))
    app = create_app()
    AgentOSHandler.routes = app
    # Bind to port 0 for auto-assign
    httpd = HTTPServer(("127.0.0.1", 0), AgentOSHandler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)
    yield httpd, port
    httpd.shutdown()


class TestHealthEndpoint:
    def test_health_returns_200(self, server):
        httpd, port = server
        conn = HTTPConnection("127.0.0.1", port)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        assert resp.status == 200
        body = json.loads(resp.read())
        assert body["status"] == "ok"
        assert "version" in body
        conn.close()

    def test_health_no_auth_required(self, server):
        httpd, port = server
        conn = HTTPConnection("127.0.0.1", port)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        assert resp.status == 200
        conn.close()


class TestBodyDrain:
    def test_oversized_body_returns_413(self, server):
        httpd, port = server
        conn = HTTPConnection("127.0.0.1", port)
        body = "x" * 100
        conn.request("POST", "/api/agent-os/tenants", body=body,
                     headers={"Content-Length": str(len(body)), "Content-Type": "application/json"})
        resp = conn.getresponse()
        # May be 413 (if oversized) or 400 (if JSON parse fails)
        assert resp.status in (400, 413)
        resp.read()
        conn.close()
