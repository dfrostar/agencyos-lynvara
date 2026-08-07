"""webhooks.py — Webhook ingestion layer for Agent OS.

Receives webhook events from external sources, verifies signatures,
queues them for async processing, and creates Signals from normalized
event data.

Supported sources:
    - GitHub (push, pull_request, issues, workflow_run)
    - Stripe (payment_intent.*, customer.subscription.*, charge.refunded, invoice.paid)
    - Custom (tenant-defined mapping)

All webhook events are persisted in webhook_events table before processing.
A background worker polls for pending events and processes them asynchronously.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import json
import logging
import uuid
from typing import Any

from .sources import github as github_norm
from .sources import stripe as stripe_norm
from .sources import custom as custom_norm
from .store import AgentOSStore

log = logging.getLogger(__name__)


# ── Ingester ────────────────────────────────────────────────────────


class WebhookIngester:
    """Receive and queue webhook events for async processing.
    
    Usage:
        ingester = WebhookIngester(store)
        status, response = ingester.ingest("github", payload, headers, raw_body)
    """

    def __init__(self, store: AgentOSStore) -> None:
        self._store = store

    def ingest(
        self,
        source: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        raw_body: bytes,
    ) -> tuple[int, dict[str, Any]]:
        """Ingest a webhook event. Returns (status, response)."""

        # 1. Extract event ID (provider-specific)
        event_id = self._extract_event_id(source, headers, payload)

        # 2. Resolve tenant from payload
        tenant_id = self._resolve_tenant(source, payload, headers)
        if not tenant_id:
            return 403, {"error": "tenant not found"}

        # 3. Verify signature
        config = self._store.get_webhook_config(tenant_id, source)
        if not config:
            return 403, {"error": "webhook not configured"}

        if not self._verify_signature(source, raw_body, headers, config["secret"]):
            return 400, {"error": "invalid signature"}

        # 4. Idempotency check
        if self._store.webhook_event_exists(event_id):
            return 200, {"status": "duplicate", "event_id": event_id}

        # 5. Queue for processing
        self._store.insert_webhook_event(
            event_id=event_id,
            tenant_id=tenant_id,
            source=source,
            event_type=self._extract_event_type(source, headers, payload),
            payload=json.dumps(payload),
        )

        return 200, {"status": "queued", "event_id": event_id}

    def _extract_event_id(self, source: str, headers: dict, payload: dict) -> str:
        """Extract unique event ID from provider headers/payload."""
        if source == "github":
            return headers.get("X-GitHub-Delivery", str(uuid.uuid4()))
        elif source == "stripe":
            return payload.get("id", str(uuid.uuid4()))
        elif source == "custom":
            return payload.get("event_id", str(uuid.uuid4()))
        return str(uuid.uuid4())

    def _verify_signature(
        self,
        source: str,
        raw_body: bytes,
        headers: dict,
        secret: str,
    ) -> bool:
        """Verify HMAC-SHA256 signature."""
        if source == "github":
            sig_header = headers.get("X-Hub-Signature-256", "")
            if not sig_header.startswith("sha256="):
                return False
            expected = "sha256=" + hmac.new(
                secret.encode(), raw_body, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, sig_header)

        elif source == "stripe":
            sig_header = headers.get("Stripe-Signature", "")
            if not sig_header:
                return False
            # Stripe: t=timestamp,v1=signature
            parts = {}
            for item in sig_header.split(","):
                if "=" in item:
                    k, v = item.split("=", 1)
                    parts[k.strip()] = v.strip()
            if "t" not in parts or "v1" not in parts:
                return False
            timestamp = parts["t"]
            expected_sig = parts["v1"]
            # Reject replayed webhooks: timestamp must be within 5 minutes of now
            try:
                sig_time = int(timestamp)
            except (ValueError, TypeError):
                return False
            if abs(int(time.time()) - sig_time) > 300:
                return False
            # signed_payload = timestamp + "." + raw_body
            signed_payload = f"{timestamp}.{raw_body.decode('utf-8')}"
            computed = hmac.new(
                secret.encode(), signed_payload.encode(), hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(computed, expected_sig)

        elif source == "custom":
            sig_header = headers.get("X-Signature", "")
            if not sig_header:
                return False
            expected = hmac.new(
                secret.encode(), raw_body, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, sig_header)

        return False

    def _resolve_tenant(
        self,
        source: str,
        payload: dict,
        headers: dict,
    ) -> str | None:
        """Resolve tenant_id from webhook payload."""
        if source == "github":
            repo = payload.get("repository", {}).get("full_name")
            if repo:
                return self._store.resolve_project_to_tenant(f"github:{repo}")
            return None

        elif source == "stripe":
            # Stripe account = tenant_id (Stripe-Account header for Connect)
            account = headers.get("Stripe-Account")
            if account:
                return account
            # Fallback: try to get from payload data
            data = payload.get("data", {}).get("object", {})
            return data.get("tenant_id")

        elif source == "custom":
            return headers.get("X-Tenant-ID")

        return None

    def _extract_event_type(self, source: str, headers: dict, payload: dict) -> str:
        """Extract event type from provider headers/payload."""
        if source == "github":
            return headers.get("X-GitHub-Event", "unknown")
        elif source == "stripe":
            return payload.get("type", "unknown")
        elif source == "custom":
            return payload.get("event_type", "unknown")
        return "unknown"


# ── Background Worker ───────────────────────────────────────────────

import asyncio


class WebhookWorker:
    """Process queued webhook events asynchronously.
    
    Polls webhook_events table for pending events and processes them.
    Each event is normalized to a Signal record, which can then be
    consumed by the Detector role.
    """

    def __init__(self, store: AgentOSStore) -> None:
        self._store = store
        self._normalizers = {
            "github": github_norm.normalize,
            "stripe": stripe_norm.normalize,
            "custom": custom_norm.normalize,
        }
        self._running = False

    async def run(self) -> None:
        """Main worker loop. Runs until stop() is called."""
        self._running = True
        log.info("Webhook worker started")
        while self._running:
            try:
                events = self._store.get_pending_webhook_events(limit=10)
                for event in events:
                    await self._process_event(event)
                if not events:
                    await asyncio.sleep(1)  # No events, brief pause
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Webhook worker error")
                await asyncio.sleep(5)  # Back off on error
        log.info("Webhook worker stopped")

    def stop(self) -> None:
        """Stop the worker loop."""
        self._running = False

    async def _process_event(self, event: dict[str, Any]) -> None:
        """Process a single webhook event."""
        self._store.mark_webhook_processing(event["event_id"])

        try:
            normalizer = self._normalizers.get(event["source"])
            if not normalizer:
                raise ValueError(f"Unknown source: {event['source']}")

            payload = json.loads(event["payload"])
            normalized = normalizer(event["event_type"], payload)

            if normalized:
                # Create signal
                signal_id = f"sig_{uuid.uuid4().hex[:12]}"
                self._store.insert_signal(
                    tenant_id=event["tenant_id"],
                    signal_dict={
                        "signal_id": signal_id,
                        "timestamp": normalized.get("timestamp", asyncio.get_event_loop().time()),
                        "metric_name": normalized["metric_name"],
                        "value": normalized["value"],
                        "baseline": 0.0,  # Webhook events don't have baselines yet
                        "delta": 0.0,
                        "severity": 1.0,
                        "level": "info",
                        "acknowledged": False,
                    },
                )

                # Update webhook event with signal reference
                self._store.mark_webhook_processed(event["event_id"], signal_id)
                log.info(
                    "Webhook %s → Signal %s (%s)",
                    event["event_id"],
                    signal_id,
                    normalized["metric_name"],
                )
            else:
                # Unsupported event type — mark as processed, no signal
                self._store.mark_webhook_processed(event["event_id"], None)

        except Exception as e:
            log.exception("Failed to process webhook event %s", event["event_id"])
            self._store.mark_webhook_failed(event["event_id"], str(e))
