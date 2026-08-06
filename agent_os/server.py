"""server.py — HTTP server for Agent OS.

Runs on port 9000 (configurable via PORT env var).
Serves all Agent OS routes including outreach.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Callable

from .api import create_agent_os_routes
from .auth import AuthContext, SessionStore
from .engagements import create_engagement_routes
from .experiment import ExperimentRunner
from .feedback import create_feedback_routes
from .outreach import create_outreach_routes
from .signals import SignalDetector
from .store import AgentOSStore
from .tenant import TenantRegistry

log = logging.getLogger(__name__)

DEFAULT_PORT = int(os.environ.get("PORT", 9000))


def create_default_store() -> AgentOSStore:
    """Create AgentOSStore with outreach + engagement + feedback tables."""
    store = AgentOSStore()
    _ensure_outreach_tables(store)
    _ensure_engagement_tables(store)
    _ensure_feedback_tables(store)
    return store


def _ensure_outreach_tables(store: AgentOSStore) -> None:
    """Create outreach tables if they don't exist."""
    conn = store._get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS outreach_leads (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            company_name TEXT NOT NULL,
            contact_name TEXT,
            contact_email TEXT,
            phone TEXT,
            linkedin_url TEXT,
            naics_code TEXT,
            employee_count INTEGER,
            source TEXT DEFAULT 'manual',
            status TEXT DEFAULT 'identified',
            notes TEXT,
            assigned_to TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_outreach_leads_tenant ON outreach_leads (tenant_id);
        CREATE INDEX IF NOT EXISTS idx_outreach_leads_tenant_status ON outreach_leads (tenant_id, status);

        CREATE TABLE IF NOT EXISTS outreach_activities (
            id TEXT PRIMARY KEY,
            lead_id TEXT NOT NULL,
            type TEXT DEFAULT 'note',
            direction TEXT DEFAULT 'outbound',
            subject TEXT,
            summary TEXT,
            next_follow_up TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_outreach_activities_lead ON outreach_activities (lead_id);
    """)
    conn.commit()


def _ensure_engagement_tables(store: AgentOSStore) -> None:
    """Create engagement tables if they don't exist."""
    conn = store._get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS engagements (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            client_id TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT DEFAULT 'gap_assessment',
            target_cmmc_level TEXT DEFAULT 'L2_self',
            status TEXT DEFAULT 'active',
            start_date TEXT,
            target_end_date TEXT,
            actual_end_date TEXT,
            engagement_owner TEXT,
            assigned_assessors TEXT,
            coi_declared INTEGER DEFAULT 0,
            nda_signed INTEGER DEFAULT 0,
            msa_signed INTEGER DEFAULT 0,
            sow_reference TEXT,
            billing_model TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_engagements_tenant ON engagements (tenant_id);
        CREATE INDEX IF NOT EXISTS idx_engagements_client ON engagements (client_id);
        CREATE INDEX IF NOT EXISTS idx_engagements_tenant_status ON engagements (tenant_id, status);

        CREATE TABLE IF NOT EXISTS engagement_notes (
            id TEXT PRIMARY KEY,
            engagement_id TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_engagement_notes_engagement ON engagement_notes (engagement_id);
    """)
    conn.commit()


def _ensure_feedback_tables(store: AgentOSStore) -> None:
    """Create feedback tables if they don't exist."""
    conn = store._get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS skill_feedback (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            trigger_event TEXT NOT NULL,
            trigger_context TEXT NOT NULL,
            original_execution TEXT,
            user_correction TEXT,
            suggested_improvement TEXT NOT NULL,
            git_commit_sha TEXT,
            status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            applied_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_tenant ON skill_feedback (tenant_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_tenant_status ON skill_feedback (tenant_id, status);

        CREATE TABLE IF NOT EXISTS knowledge_entries (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            entry_type TEXT NOT NULL DEFAULT 'feedback',
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source_feedback_id TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_knowledge_tenant ON knowledge_entries (tenant_id);
    """)
    conn.commit()


def _default_get_auth(body: dict[str, Any] | None) -> AuthContext:
    """Default auth getter — requires bearer <REDACTED>, does NOT trust body tenant_id.
    
    CRITICAL C2 FIX: Previously trusted body['tenant_id'] for development.
    Now returns unauthenticated context — handlers must enforce auth.
    """
    # NOTE: For API-key-based auth (automated systems), add X-API-Key header check here.
    return AuthContext(email="", tenant_id=None)


class AgentOSHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Agent OS routes."""

    # Route registry: populated at server startup
    routes: dict[tuple[str, str], Callable] = {}

    def log_message(self, format: str, *args: Any) -> None:
        log.info("%s - %s", self.address_string(), format % args)

    def _read_body(self) -> dict[str, Any] | None:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw = self.rfile.read(content_length)
            try:
                return json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
        return None

    def _extract_path_params(self, pattern: str) -> dict[str, str] | None:
        """Extract path params from URL against a pattern.
        Pattern like '/api/agent-os/outreach/leads/{id}'
        """
        # Convert pattern to regex: {id} -> (?P<id>[^/]+)
        regex_pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', pattern)
        regex_pattern = f'^{regex_pattern}$'
        
        # Get path without query string
        path = self.path.split('?')[0]
        
        match = re.match(regex_pattern, path)
        if match:
            return match.groupdict()
        return None

    def _send_response(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _find_handler(self, method: str, path: str) -> tuple[Callable | None, dict[str, str] | None]:
        """Find handler for method + path, extracting path params."""
        clean_path = path.split('?')[0]
        
        for (route_method, route_path), handler in self.routes.items():
            if route_method != method:
                continue
            path_params = self._extract_path_params(route_path)
            if path_params is not None:
                regex_pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', route_path)
                regex_pattern = f'^{regex_pattern}$'
                if re.match(regex_pattern, clean_path):
                    return handler, path_params
        return None, None

    def do_GET(self) -> None:
        # Intercept webhook stats path
        if self.path.startswith("/api/agent-os/webhooks/stats"):
            auth_header = self.headers.get("Authorization", "").replace("Bearer ", "")
            session = self.server.session_store.get_session(auth_header) if hasattr(self.server, 'session_store') else None
            if not session and hasattr(self.server, 'session_store'):
                self._send_response(401, {"error": "unauthorized"})
                return
            tenant_id = session.tenant_id if session else "dev-tenant"
            if hasattr(self.server, 'store'):
                stats = self.server.store.get_webhook_stats(tenant_id)
                self._send_response(200, stats)
            else:
                self._send_response(200, {"total": 0, "processed": 0, "failed": 0, "last_event_at": None})
            return
        # Fall through to existing GET handler
        handler, params = self._find_handler("GET", self.path)
        if handler:
            body = self._read_body()
            # Parse query string for GET requests
            if "?" in self.path:
                from urllib.parse import parse_qs
                qs = parse_qs(self.path.split("?")[1])
                if body is None:
                    body = {}
                for k, v in qs.items():
                    body[k] = v[0] if len(v) == 1 else v
            try:
                status, response = handler(body, headers=dict(self.headers), **(params or {}))
                self._send_response(status, response)
            except Exception as e:
                log.exception("Error handling GET %s", self.path)
                self._send_response(500, {"error": str(e)})
        else:
            self._send_response(404, {"error": "Not found", "path": self.path})

    def do_POST(self) -> None:
        # Intercept webhook ingestion paths
        webhook_match = re.match(
            r"^/api/agent-os/webhooks/(?P<source>github|stripe|custom)$",
            self.path.split("?")[0],
        )
        if webhook_match:
            source = webhook_match.group("source")
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_response(400, {"error": "invalid JSON"})
                return
            if hasattr(self.server, 'webhook_ingester'):
                status, response = self.server.webhook_ingester.ingest(
                    source=source,
                    payload=payload,
                    headers=dict(self.headers),
                    raw_body=raw_body,
                )
                self._send_response(status, response)
            else:
                self._send_response(503, {"error": "webhook ingestion not enabled"})
            return
        # Fall through to existing POST handler
        handler, params = self._find_handler("POST", self.path)
        if handler:
            body = self._read_body()
            try:
                status, response = handler(body, headers=dict(self.headers), **(params or {}))
                self._send_response(status, response)
            except Exception as e:
                log.exception("Error handling POST %s", self.path)
                self._send_response(500, {"error": str(e)})
        else:
            self._send_response(404, {"error": "Not found", "path": self.path})

    def do_PATCH(self) -> None:
        handler, params = self._find_handler("PATCH", self.path)
        if handler:
            body = self._read_body()
            try:
                status, response = handler(body, headers=dict(self.headers), **(params or {}))
                self._send_response(status, response)
            except Exception as e:
                log.exception("Error handling PATCH %s", self.path)
                self._send_response(500, {"error": str(e)})
        else:
            self._send_response(404, {"error": "Not found", "path": self.path})

    def do_DELETE(self) -> None:
        handler, params = self._find_handler("DELETE", self.path)
        if handler:
            body = self._read_body()
            try:
                status, response = handler(body, headers=dict(self.headers), **(params or {}))
                self._send_response(status, response)
            except Exception as e:
                log.exception("Error handling DELETE %s", self.path)
                self._send_response(500, {"error": str(e)})
        else:
            self._send_response(404, {"error": "Not found", "path": self.path})


def create_app(
    store: AgentOSStore | None = None,
    session_store: SessionStore | None = None,
) -> dict[tuple[str, str], Callable]:
    """Create all route handlers."""
    if store is None:
        store = create_default_store()
    
    if session_store is None:
        session_store = SessionStore()

    # Create component registry
    registry = TenantRegistry()
    signal_detector = SignalDetector()
    experiment_runner = ExperimentRunner()

    # Get existing routes from api.py
    existing_routes = create_agent_os_routes(
        tenant_registry=registry,
        signal_detector=signal_detector,
        experiment_runner=experiment_runner,
        session_store=session_store,
        store=store,
    )

    # Get outreach routes
    outreach_routes = create_outreach_routes(
        store=store,
        get_auth=_default_get_auth,
    )

    # Get engagement routes
    engagement_routes = create_engagement_routes(
        store=store,
        get_auth=_default_get_auth,
    )

    # Get feedback routes
    feedback_routes = create_feedback_routes(
        store=store,
        get_auth=_default_get_auth,
    )

    # Merge routes
    all_routes = {**existing_routes, **outreach_routes, **engagement_routes, **feedback_routes}
    
    # Add webhook config routes
    all_routes.update(_create_webhook_config_routes(store))
    
    return all_routes


def _create_webhook_config_routes(store: AgentOSStore) -> dict[tuple[str, str], Callable]:
    """Create webhook configuration routes."""
    routes: dict[tuple[str, str], Callable] = {}
    
    def list_configs(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        tenant_id = body.get("tenant_id", "dev-tenant") if body else "dev-tenant"
        configs = store.list_webhook_configs(tenant_id)
        return 200, {"configs": configs, "count": len(configs)}
    
    def create_config(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        if not body:
            return 400, {"error": "body required"}
        tenant_id = body.get("tenant_id", "dev-tenant")
        source = body.get("source")
        secret = body.get("secret")
        if not source or not secret:
            return 400, {"error": "source and secret required"}
        config_id = store.create_webhook_config(
            tenant_id=tenant_id,
            source=source,
            secret=secret,
            enabled_events=body.get("enabled_events"),
            project_mapping=body.get("project_mapping"),
        )
        return 201, {"config_id": config_id, "tenant_id": tenant_id, "source": source}
    
    def delete_config(body: dict[str, Any] | None, **path_params: str) -> tuple[int, dict[str, Any]]:
        if not body:
            return 400, {"error": "body required"}
        tenant_id = body.get("tenant_id", "dev-tenant")
        source = body.get("source")
        if not source:
            return 400, {"error": "source required"}
        deleted = store.delete_webhook_config(tenant_id, source)
        if deleted:
            return 200, {"status": "deleted"}
        return 404, {"error": "config not found"}
    
    routes[("GET", "/api/agent-os/webhooks/configs")] = list_configs
    routes[("POST", "/api/agent-os/webhooks/configs")] = create_config
    routes[("DELETE", "/api/agent-os/webhooks/configs")] = delete_config
    
    return routes


def main() -> None:
    """Run the Agent OS HTTP server."""
    logging.basicConfig(level=logging.INFO)
    
    store = create_default_store()
    session_store = SessionStore()
    
    routes = create_app(store, session_store)
    
    # Inject routes into handler class
    AgentOSHandler.routes = routes
    
    port = DEFAULT_PORT
    server = HTTPServer(("0.0.0.0", port), AgentOSHandler)
    
    # Inject webhook ingester and store into server for access in handler
    from .webhooks import WebhookIngester
    server.webhook_ingester = WebhookIngester(store)
    server.store = store
    server.session_store = session_store
    
    log.info("Agent OS server starting on port %d", port)
    log.info("Routes registered: %d", len(routes))
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
