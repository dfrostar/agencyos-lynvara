"""signal_sources.py — Signal source management routes for Agent OS.

Tenant-scoped endpoints for B-06:
    GET    /api/agent-os/signal-sources — list sources
    POST   /api/agent-os/signal-sources — create source
    GET    /api/agent-os/signal-sources/{id} — get single
    DELETE /api/agent-os/signal-sources/{id} — delete source
    POST   /api/agent-os/signal-sources/{id}/ingest — ingest raw signal
    GET    /api/agent-os/signal-sources/{id}/signals — list signals for source
    GET    /api/agent-os/signals/raw — list all raw signals (cross-source)

Signal source types:
    - competitor: competitor product changes, pricing, announcements
    - regulatory: CMMC/NIST FedRAMP rule changes, DFARS updates
    - market: TAM shifts, sector growth, new entrants
    - custom: tenant-defined source
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from .auth import AuthContext, SessionStore, extract_bearer_token

log = logging.getLogger(__name__)

# Source type enum
SOURCE_TYPES = ["competitor", "regulatory", "market", "custom"]

# Validation
SOURCE_TYPE_REGEX = re.compile(r"^[a-z_]{1,50}$")
METRIC_NAME_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.]{0,127}$")


def _json_response(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return status, payload


def _error(status: int, message: str) -> tuple[int, dict[str, Any]]:
    return status, {"error": message}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_signal_source_routes(
    store: Any,
    session_store: SessionStore | None = None,
    get_auth: Callable[[dict[str, Any] | None], AuthContext] | None = None,
) -> dict[tuple[str, str], Callable]:
    """Create signal source route handlers."""
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

    # ── CRUD ──────────────────────────────────────────────────────

    def list_sources(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/signal-sources — list sources for tenant."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            source_type = None
            if body and body.get("sourceType"):
                source_type = body["sourceType"]

            sources = store.list_signal_sources(tenant_id, source_type)
            return _json_response(200, {
                "sources": sources,
                "count": len(sources),
            })
        except Exception as e:
            log.exception("Failed to list signal sources")
            return _error(500, str(e))

    def create_source(
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/signal-sources — register a new source."""
        try:
            if not body or not isinstance(body, dict):
                return _error(400, "body must be a JSON object")

            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            source_type = (body.get("sourceType") or "").strip()
            if source_type not in SOURCE_TYPES:
                return _error(
                    400,
                    f"sourceType must be one of: {', '.join(SOURCE_TYPES)}",
                )

            name = (body.get("name") or "").strip()
            if not name:
                return _error(400, "name is required")
            if len(name) > 200:
                return _error(400, "name max 200 chars")

            description = body.get("description")
            if description and len(str(description)) > 2000:
                return _error(400, "description max 2000 chars")

            config = body.get("config")
            if config and not isinstance(config, dict):
                return _error(400, "config must be an object")

            source_id = store.create_signal_source(
                tenant_id=tenant_id,
                source_type=source_type,
                name=name,
                description=description,
                config=config,
            )
            return _json_response(201, {
                "sourceId": source_id,
                "tenantId": tenant_id,
                "sourceType": source_type,
                "name": name,
            })
        except Exception as e:
            log.exception("Failed to create signal source")
            return _error(500, str(e))

    def get_source(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/signal-sources/{id} — get single source."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            source_id = path_params.get("id", "")
            if not source_id:
                return _error(400, "id required")

            source = store.get_signal_source(tenant_id, source_id)
            if not source:
                return _error(404, "Signal source not found")

            return _json_response(200, source)
        except Exception as e:
            log.exception("Failed to get signal source")
            return _error(500, str(e))

    def delete_source(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """DELETE /api/agent-os/signal-sources/{id} — delete source."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            source_id = path_params.get("id", "")
            if not source_id:
                return _error(400, "id required")

            deleted = store.delete_signal_source(tenant_id, source_id)
            if not deleted:
                return _error(404, "Signal source not found")

            return _json_response(200, {"deleted": True, "sourceId": source_id})
        except Exception as e:
            log.exception("Failed to delete signal source")
            return _error(500, str(e))

    # ── Signal ingestion ──────────────────────────────────────────

    def ingest_signal(
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/signal-sources/{id}/ingest — ingest raw signal."""
        try:
            if not body or not isinstance(body, dict):
                return _error(400, "body must be a JSON object")

            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            source_id = path_params.get("id", "")
            if not source_id:
                return _error(400, "id required")

            # Verify source belongs to tenant
            source = store.get_signal_source(tenant_id, source_id)
            if not source:
                return _error(404, "Signal source not found")

            # Validate metric_name
            metric_name = (body.get("metricName") or "").strip()
            if not metric_name:
                return _error(400, "metricName is required")
            if not METRIC_NAME_REGEX.match(metric_name):
                return _error(
                    400,
                    "metricName must start with letter, contain only "
                    "alphanumerics/dots/underscores, max 128 chars",
                )

            # Validate value
            value = body.get("value")
            if value is None:
                return _error(400, "value is required")
            try:
                value = float(value)
            except (TypeError, ValueError):
                return _error(400, "value must be numeric")

            metadata = body.get("metadata")
            if metadata and not isinstance(metadata, dict):
                return _error(400, "metadata must be an object")

            signal_id = store.insert_raw_signal(
                tenant_id=tenant_id,
                source_id=source_id,
                metric_name=metric_name,
                value=value,
                metadata=metadata,
            )
            return _json_response(201, {
                "signalId": signal_id,
                "sourceId": source_id,
                "metricName": metric_name,
                "value": value,
            })
        except Exception as e:
            log.exception("Failed to ingest signal")
            return _error(500, str(e))

    def list_source_signals(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/signal-sources/{id}/signals — signals for source."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            source_id = path_params.get("id", "")
            if not source_id:
                return _error(400, "id required")

            # Verify source belongs to tenant
            source = store.get_signal_source(tenant_id, source_id)
            if not source:
                return _error(404, "Signal source not found")

            limit = 100
            if body and body.get("limit"):
                limit = min(int(body["limit"]), 500)

            signals = store.get_raw_signals(
                tenant_id=tenant_id,
                source_id=source_id,
                limit=limit,
            )
            return _json_response(200, {
                "signals": signals,
                "count": len(signals),
            })
        except Exception as e:
            log.exception("Failed to list source signals")
            return _error(500, str(e))

    def list_all_raw_signals(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/signals/raw — all raw signals across sources."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return _error(401, "authentication required")
            if not tenant_id:
                return _error(400, "tenant_id required")

            metric_name = None
            limit = 100
            if body:
                if body.get("metricName"):
                    metric_name = body["metricName"]
                if body.get("limit"):
                    limit = min(int(body["limit"]), 500)

            signals = store.get_raw_signals(
                tenant_id=tenant_id,
                metric_name=metric_name,
                limit=limit,
            )
            return _json_response(200, {
                "signals": signals,
                "count": len(signals),
            })
        except Exception as e:
            log.exception("Failed to list raw signals")
            return _error(500, str(e))

    # ── Route table ───────────────────────────────────────────────

    routes: dict[tuple[str, str], Callable] = {
        ("GET", "/api/agent-os/signal-sources"): list_sources,
        ("POST", "/api/agent-os/signal-sources"): create_source,
        ("GET", "/api/agent-os/signal-sources/{id}"): get_source,
        ("DELETE", "/api/agent-os/signal-sources/{id}"): delete_source,
        ("POST", "/api/agent-os/signal-sources/{id}/ingest"): ingest_signal,
        ("GET", "/api/agent-os/signal-sources/{id}/signals"): list_source_signals,
        ("GET", "/api/agent-os/signals/raw"): list_all_raw_signals,
    }
    return routes
