# AgencyOS — Technical Requirements Document (TRD)
## Levels 5/7/8 Gap Closure

**Version:** 1.0.0
**Date:** 2026-08-05
**Owner:** Darren Frost (Cheval-Volant, LLC)
**Repo:** `/home/dtfrost5/agencyOS/`
**Status:** DRAFT

---

## 1. Technical Overview

### 1.1 Architecture Pattern

AgencyOS uses a **modular monolith** pattern:
- Single process, multiple async tasks
- SQLite for persistence (no external DB required)
- Stdlib HTTP server (no FastAPI/Flask dependency)
- Message bus for inter-module communication

### 1.2 Technology Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| HTTP Server | `http.server.ThreadingHTTPServer` | Stdlib, thread-safe, proven |
| Persistence | SQLite (via `sqlite3` stdlib) | Zero-config, file-based, ACID |
| Async | `asyncio` (stdlib) | Role concurrency without threads |
| Cryptography | `hmac`, `hashlib` (stdlib) | Webhook signature verification |
| Typing | Python 3.10+ type hints | MyPy strict mode compliance |
| Testing | `pytest`, `pytest-asyncio` | Existing test infrastructure |
| Linting | `ruff`, `black`, `mypy` | Existing CI pipeline |

### 1.3 Module Dependency Graph

```
agent_os/
├── __init__.py
├── cli.py                    # Level 1-2 (existing)
├── server.py                 # HTTP server (existing, extended)
├── store.py                  # SQLite persistence (extended)
├── signals.py                # Signal detection (existing)
├── correlator.py             # Root cause correlation (existing)
├── auto_trigger.py           # Auto-trigger loop (existing)
├── experiment.py             # A/B experiment runner (existing)
├── promotion.py              # Promotion/rollback engine (existing)
├── governance.py             # RBAC governance (existing)
├── auth.py                   # Session management (existing)
├── api.py                    # Core API routes (existing)
├── outreach.py               # Outreach extraction (existing)
├── engagements.py            # Engagement extraction (existing)
├── feedback.py               # Feedback extraction (existing)
├── postgres.py               # PostgreSQL client (existing)
├── adversarial.py            # Adversarial QA (existing)
│
├── webhooks.py               # NEW: Webhook ingestion layer
├── sources/
│   ├── __init__.py
│   ├── github.py             # NEW: GitHub event normalizer
│   ├── stripe.py             # NEW: Stripe event normalizer
│   └── custom.py             # NEW: Custom event normalizer
│
├── roles/
│   ├── __init__.py
│   ├── base.py               # NEW: AgentRole abstract class
│   ├── detector.py           # NEW: Detector role wrapper
│   ├── correlator.py         # NEW: Correlator role wrapper
│   └── evolver.py            # NEW: Evolver role
│
├── bus.py                    # NEW: Message bus
├── coordinator.py            # NEW: Role lifecycle manager
└── departments/
    ├── __init__.py
    ├── base.py               # NEW: Department base class
    ├── outreach.py           # NEW: Outreach orchestrator
    └── engagements.py        # NEW: Engagement orchestrator
```

---

## 2. Data Layer

### 2.1 Schema Extensions

#### webhook_events Table

```sql
CREATE TABLE IF NOT EXISTS webhook_events (
    event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('github', 'stripe', 'custom')),
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,              -- raw JSON, max 10KB
    normalized_signal_id TEXT,          -- FK to signals.signal_id
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    processed_at TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'processed', 'failed')),
    error_message TEXT,
    
    FOREIGN KEY (normalized_signal_id) REFERENCES signals(signal_id)
);

CREATE INDEX idx_webhook_events_tenant ON webhook_events (tenant_id);
CREATE INDEX idx_webhook_events_status ON webhook_events (status, received_at);
CREATE INDEX idx_webhook_events_source ON webhook_events (source, event_type);
```

#### agent_messages Table

```sql
CREATE TABLE IF NOT EXISTS agent_messages (
    message_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    from_role TEXT NOT NULL,
    to_role TEXT,                       -- NULL = broadcast
    payload TEXT NOT NULL,              -- JSON message body
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    consumed_at TEXT,
    consume_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'consumed', 'failed', 'dead')),
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);

CREATE INDEX idx_messages_tenant_topic ON agent_messages (tenant_id, topic, status);
CREATE INDEX idx_messages_consumed ON agent_messages (status, created_at);
```

#### agent_roles Table

```sql
CREATE TABLE IF NOT EXISTS agent_roles (
    role_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    role_name TEXT NOT NULL CHECK(role_name IN ('detector', 'correlator', 'evolver', 'executor')),
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'paused', 'error')),
    last_heartbeat TEXT,
    config TEXT,                        -- JSON role-specific config
    messages_processed INTEGER DEFAULT 0,
    messages_failed INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    UNIQUE(tenant_id, role_name)
);

CREATE INDEX idx_roles_tenant ON agent_roles (tenant_id, status);
```

#### webhook_configs Table

```sql
CREATE TABLE IF NOT EXISTS webhook_configs (
    config_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('github', 'stripe', 'custom')),
    secret TEXT NOT NULL,               -- webhook secret (encrypted at rest)
    enabled_events TEXT,                -- JSON array of event types
    project_mapping TEXT,               -- JSON object: external_ref → tenant_ref
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    UNIQUE(tenant_id, source)
);
```

### 2.2 Schema Migrations

**Migration strategy:** `CREATE TABLE IF NOT EXISTS` on server startup.

```python
# In store.py — new method
def ensure_new_tables(self) -> None:
    """Create new tables if they don't exist."""
    self._ensure_webhook_events_table()
    self._ensure_agent_messages_table()
    self._ensure_agent_roles_table()
    self._ensure_webhook_configs_table()
```

---

## 3. Webhook Ingestion Layer

### 3.1 webhook.py — Core Module

```python
"""webhooks.py — Webhook ingestion for Agent OS.

Handles receiving, verifying, and queueing webhook events.
Processing happens asynchronously via background worker.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from typing import Any

from .store import AgentOSStore

log = logging.getLogger(__name__)


class WebhookIngester:
    """Receive and queue webhook events for async processing."""
    
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
        event_id = self._store.queue_webhook_event(
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
            # Stripe: t=timestamp,v1=signature
            sig_header = headers.get("Stripe-Signature", "")
            # Implementation: parse timestamp + signatures, verify v1
            # ... (full Stripe verification logic)
            pass
        
        elif source == "custom":
            # Custom: tenant-defined secret, simple HMAC
            sig_header = headers.get("X-Signature", "")
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
            return self._store.resolve_project_to_tenant(f"github:{repo}")
        
        elif source == "stripe":
            account = headers.get("Stripe-Account")
            return account  # Stripe account = tenant_id
        
        elif source == "custom":
            return payload.get("tenant_id")
        
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
```

### 3.2 Event Normalizers

```python
"""sources/github.py — GitHub event normalizer."""

from __future__ import annotations

from typing import Any


def normalize(event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Convert GitHub event to canonical Signal format.
    
    Returns: {metric_name, value, timestamp, metadata} or None if unsupported.
    """
    if event_type == "push":
        return {
            "metric_name": "github.push.count",
            "value": 1.0,
            "timestamp": payload.get("head_commit", {}).get("timestamp"),
            "metadata": {
                "repository": payload.get("repository", {}).get("full_name"),
                "branch": payload.get("ref", "").replace("refs/heads/", ""),
                "commit_count": len(payload.get("commits", [])),
            },
        }
    
    elif event_type == "pull_request":
        pr = payload.get("pull_request", {})
        if payload.get("action") == "opened":
            return {
                "metric_name": "github.pr.opened",
                "value": 1.0,
                "timestamp": pr.get("created_at"),
                "metadata": {
                    "repository": payload.get("repository", {}).get("full_name"),
                    "author": pr.get("user", {}).get("login"),
                },
            }
        elif payload.get("action") == "closed":
            return {
                "metric_name": "github.pr.merged",
                "value": 1.0 if pr.get("merged") else 0.0,
                "timestamp": pr.get("closed_at"),
                "metadata": {
                    "repository": payload.get("repository", {}).get("full_name"),
                    "author": pr.get("user", {}).get("login"),
                },
            }
    
    elif event_type == "issues":
        issue = payload.get("issue", {})
        return {
            "metric_name": f"github.issue.{payload.get('action')}",
            "value": 1.0,
            "timestamp": issue.get("created_at") if payload.get("action") == "opened" else issue.get("closed_at"),
            "metadata": {
                "repository": payload.get("repository", {}).get("full_name"),
                "author": issue.get("user", {}).get("login"),
                "labels": [l.get("name") for l in issue.get("labels", [])],
            },
        }
    
    return None  # Unsupported event type
```

### 3.3 Background Worker

```python
"""webhooks.py — Background worker (continued)."""

import asyncio
import json
import logging
from typing import Any

from .sources import github as github_norm
from .sources import stripe as stripe_norm
from .sources import custom as custom_norm

log = logging.getLogger(__name__)


class WebhookWorker:
    """Process queued webhook events asynchronously."""
    
    def __init__(self, store: AgentOSStore, bus: Any) -> None:
        self._store = store
        self._bus = bus
        self._normalizers = {
            "github": github_norm.normalize,
            "stripe": stripe_norm.normalize,
            "custom": custom_norm.normalize,
        }
    
    async def run(self) -> None:
        """Main worker loop."""
        while True:
            try:
                events = self._store.get_pending_webhook_events(limit=10)
                for event in events:
                    await self._process_event(event)
                await asyncio.sleep(1)  # Poll interval
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Webhook worker error")
                await asyncio.sleep(5)  # Back off on error
    
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
                signal_id = self._store.create_signal(
                    tenant_id=event["tenant_id"],
                    metric_name=normalized["metric_name"],
                    value=normalized["value"],
                    timestamp=normalized["timestamp"],
                    metadata=json.dumps(normalized["metadata"]),
                    source=f"webhook:{event['source']}",
                )
                
                # Update webhook event with signal reference
                self._store.mark_webhook_processed(
                    event["event_id"], signal_id
                )
                
                # Publish signal to message bus for role processing
                await self._bus.publish(
                    tenant_id=event["tenant_id"],
                    topic="signal",
                    from_role="webhook_worker",
                    message={
                        "signal_id": signal_id,
                        "metric_name": normalized["metric_name"],
                        "value": normalized["value"],
                        "tenant_id": event["tenant_id"],
                    },
                )
            else:
                # Unsupported event type — mark as processed, no signal
                self._store.mark_webhook_processed(
                    event["event_id"], None, status="processed"
                )
        
        except Exception as e:
            log.exception("Failed to process webhook event %s", event["event_id"])
            self._store.mark_webhook_failed(event["event_id"], str(e))
```

### 3.4 HTTP Route Registration

In `server.py`, add webhook routes:

```python
# In AgentOSHandler — add to do_POST method
WEBHOOK_PATTERN = re.compile(r'^/api/agent-os/webhooks/(?P<source>github|stripe|custom)$')

# In do_POST, before existing route matching:
def do_POST(self) -> None:
    # Check webhook path first
    match = WEBHOOK_PATTERN.match(self.path.split('?')[0])
    if match:
        source = match.group('source')
        body = self._read_body()
        raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        
        ingester = self.server.webhook_ingester
        status, response = ingester.ingest(
            source=source,
            payload=body or {},
            headers=dict(self.headers),
            raw_body=raw,
        )
        self._send_response(status, response)
        return
    
    # ... existing route handling
```

---

## 4. Role-Based Architecture

### 4.1 Base Role Class

```python
"""roles/base.py — Abstract base class for all agent roles."""

from __future__ import annotations

import abc
import asyncio
import logging
import time
from typing import Any

from .bus import MessageBus
from .store import AgentOSStore

log = logging.getLogger(__name__)


class AgentRole(abc.ABC):
    """Base class for all agent roles.
    
    Each role runs as an independent async task, consuming messages
    from the message bus and publishing results back.
    """
    
    role_name: str = ""  # Override in subclass
    
    def __init__(
        self,
        tenant_id: str,
        bus: MessageBus,
        store: AgentOSStore,
    ) -> None:
        self._tenant_id = tenant_id
        self._bus = bus
        self._store = store
        self._task: asyncio.Task | None = None
        self._last_heartbeat = time.time()
        self._messages_processed = 0
        self._messages_failed = 0
        self._running = False
    
    @abc.abstractmethod
    def subscriptions(self) -> list[str]:
        """Return list of topics this role consumes."""
        ...
    
    @abc.abstractmethod
    async def process(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """Process a message. Returns list of messages to publish.
        
        Raise exception to trigger retry/dead-letter.
        """
        ...
    
    def heartbeat(self) -> dict[str, Any]:
        """Return health status for coordinator monitoring."""
        return {
            "role_name": self.role_name,
            "status": "active" if self._running else "stopped",
            "last_heartbeat": self._last_heartbeat,
            "messages_processed": self._messages_processed,
            "messages_failed": self._messages_failed,
            "uptime_seconds": time.time() - self._start_time if hasattr(self, '_start_time') else 0,
        }
    
    async def start(self) -> None:
        """Start the role's message consumption loop."""
        self._running = True
        self._start_time = time.time()
        self._task = asyncio.create_task(self._consume_loop())
        log.info("Role %s started for tenant %s", self.role_name, self._tenant_id)
    
    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("Role %s stopped for tenant %s", self.role_name, self._tenant_id)
    
    async def _consume_loop(self) -> None:
        """Main consumption loop."""
        while self._running:
            try:
                message = await self._bus.consume(
                    tenant_id=self._tenant_id,
                    role_name=self.role_name,
                    subscriptions=self.subscriptions(),
                )
                if message:
                    self._last_heartbeat = time.time()
                    results = await self.process(message)
                    self._messages_processed += 1
                    
                    # Publish results
                    for result in results:
                        await self._bus.publish(
                            tenant_id=self._tenant_id,
                            topic=result.get("topic", "signal"),
                            from_role=self.role_name,
                            message=result,
                        )
                    
                    # Acknowledge message
                    await self._bus.acknowledge(message["message_id"])
                
                else:
                    await asyncio.sleep(0.1)  # No messages, brief pause
            
            except asyncio.CancelledError:
                break
            except Exception:
                self._messages_failed += 1
                log.exception("Role %s error processing message", self.role_name)
                await asyncio.sleep(1)  # Back off on error
```

### 4.2 Message Bus

```python
"""bus.py — SQLite-backed message bus for inter-role communication."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from .store import AgentOSStore

log = logging.getLogger(__name__)


class MessageBus:
    """SQLite-backed pub/sub message bus."""
    
    def __init__(self, store: AgentOSStore) -> None:
        self._store = store
        self._lock = asyncio.Lock()
    
    async def publish(
        self,
        tenant_id: str,
        topic: str,
        from_role: str,
        message: dict[str, Any],
        to_role: str | None = None,
    ) -> str:
        """Publish a message to a topic."""
        async with self._lock:
            message_id = str(uuid.uuid4())
            self._store.insert_message(
                message_id=message_id,
                tenant_id=tenant_id,
                topic=topic,
                from_role=from_role,
                to_role=to_role,
                payload=json.dumps(message),
            )
            return message_id
    
    async def consume(
        self,
        tenant_id: str,
        role_name: str,
        subscriptions: list[str],
    ) -> dict[str, Any] | None:
        """Consume next pending message for this role."""
        async with self._lock:
            messages = self._store.get_pending_messages(
                tenant_id=tenant_id,
                topics=subscriptions,
                to_role=role_name,
                limit=1,
            )
            
            if not messages:
                return None
            
            message = messages[0]
            self._store.mark_message_processing(message["message_id"])
            return message
    
    async def acknowledge(self, message_id: str) -> None:
        """Acknowledge message processing."""
        self._store.mark_message_consumed(message_id)
    
    async def retry_or_dead(self, message_id: str, error: str) -> None:
        """Retry message or move to dead letter queue."""
        message = self._store.get_message(message_id)
        if message and message["consume_count"] >= 3:
            self._store.mark_message_dead(message_id, error)
        else:
            self._store.mark_message_failed(message_id, error)
    
    async def get_dead_messages(
        self,
        tenant_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get messages in dead letter queue."""
        return self._store.get_dead_messages(tenant_id, limit)
```

### 4.3 Detector Role

```python
"""roles/detector.py — Anomaly detection role."""

from __future__ import annotations

import logging
from typing import Any

from ..signals import SignalDetector
from .base import AgentRole

log = logging.getLogger(__name__)


class DetectorRole(AgentRole):
    """Wraps SignalDetector as a role.
    
    Consumes: metric_value, webhook_event
    Produces: signal
    """
    
    role_name = "detector"
    
    def __init__(self, tenant_id: str, bus: Any, store: Any) -> None:
        super().__init__(tenant_id, bus, store)
        self._detector = SignalDetector(store=store, tenant_id=tenant_id)
    
    def subscriptions(self) -> list[str]:
        return ["metric_value", "webhook_event"]
    
    async def process(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        topic = message.get("topic")
        
        if topic == "metric_value":
            # Run Page-Hinkley detection
            result = self._detector.check_value(
                metric_name=message["metric_name"],
                value=message["value"],
            )
            if result.get("is_anomaly"):
                return [{
                    "topic": "signal",
                    "signal_id": result["signal_id"],
                    "metric_name": message["metric_name"],
                    "value": message["value"],
                    "baseline": result["baseline"],
                    "z_score": result["z_score"],
                }]
        
        elif topic == "webhook_event":
            # Webhook events already normalized — forward as signal
            return [{
                "topic": "signal",
                "signal_id": message["signal_id"],
                "metric_name": message["metric_name"],
                "value": message["value"],
            }]
        
        return []
```

### 4.4 Evolver Role

```python
"""roles/evolver.py — Self-improvement role.

Proposes new detection rules based on experiment history and gap analysis.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from .base import AgentRole

log = logging.getLogger(__name__)


class EvolverRole(AgentRole):
    """Proposes new rules based on experiment history.
    
    Consumes: experiment_completed
    Produces: proposal
    """
    
    role_name = "evolver"
    
    def __init__(self, tenant_id: str, bus: Any, store: Any) -> None:
        super().__init__(tenant_id, bus, store)
        self._last_analysis = 0.0
        self._analysis_interval = 86400  # Daily
    
    def subscriptions(self) -> list[str]:
        return ["experiment_completed", "timer"]
    
    async def process(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        topic = message.get("topic")
        now = time.time()
        
        if topic == "experiment_completed":
            # Check if it's time for daily analysis
            if now - self._last_analysis >= self._analysis_interval:
                proposals = await self._run_daily_analysis()
                self._last_analysis = now
                return proposals
        
        elif topic == "timer":
            # Triggered by daily cron
            if now - self._last_analysis >= self._analysis_interval:
                proposals = await self._run_daily_analysis()
                self._last_analysis = now
                return proposals
        
        return []
    
    async def _run_daily_analysis(self) -> list[dict[str, Any]]:
        """Run daily gap analysis and propose new rules."""
        proposals = []
        
        # 1. Analyze false positive rate
        fp_analysis = self._store.analyze_false_positive_rate(
            tenant_id=self._tenant_id,
            days=30,
        )
        
        for metric in fp_analysis:
            if metric["false_positive_rate"] > 0.20:
                proposals.append({
                    "topic": "proposal",
                    "proposal_id": f"evolver-{metric['metric_name']}-{int(time.time())}",
                    "rule_type": "detection",
                    "definition": {
                        "action": "tighten_threshold",
                        "metric_name": metric["metric_name"],
                        "current_threshold": metric["current_threshold"],
                        "proposed_threshold": metric["current_threshold"] * 1.2,
                    },
                    "expected_impact": f"Reduce false positives from {metric['false_positive_rate']:.0%} to <10%",
                    "confidence": 0.7,
                    "risk_level": "low",
                    "actor_role": "evolver",
                })
        
        # 2. Find stale rules (no signal for 30+ days)
        stale_rules = self._store.find_stale_rules(
            tenant_id=self._tenant_id,
            days=30,
        )
        
        for rule in stale_rules:
            proposals.append({
                "topic": "proposal",
                "proposal_id": f"evolver-stale-{rule['rule_id']}-{int(time.time())}",
                "rule_type": "detection",
                "definition": {
                    "action": "deprecate_rule",
                    "rule_id": rule["rule_id"],
                    "metric_name": rule["metric_name"],
                },
                "expected_impact": f"Remove unused rule for {rule['metric_name']}",
                "confidence": 0.9,
                "risk_level": "medium",
                "actor_role": "evolver",
            })
        
        return proposals
```

---

## 5. Coordinator

```python
"""coordinator.py — Role lifecycle manager."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .bus import MessageBus
from .roles.base import AgentRole
from .roles.detector import DetectorRole
from .roles.correlator import CorrelatorRole
from .roles.evolver import EvolverRole
from .store import AgentOSStore

log = logging.getLogger(__name__)


class Coordinator:
    """Manages role lifecycle, health monitoring, and message routing."""
    
    HEARTBEAT_TIMEOUT = 60  # seconds
    MAX_RESTARTS = 3
    
    def __init__(self, store: AgentOSStore, bus: MessageBus) -> None:
        self._store = store
        self._bus = bus
        self._roles: dict[str, AgentRole] = {}
        self._restart_counts: dict[str, int] = {}
        self._monitor_task: asyncio.Task | None = None
    
    async def start(self) -> None:
        """Start all roles and monitoring."""
        await self._load_roles()
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        log.info("Coordinator started with %d roles", len(self._roles))
    
    async def stop(self) -> None:
        """Stop all roles and monitoring."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        for role in self._roles.values():
            await role.stop()
        log.info("Coordinator stopped")
    
    async def _load_roles(self) -> None:
        """Load roles from database and start them."""
        role_configs = self._store.get_active_roles()
        
        for config in role_configs:
            role = self._create_role(
                role_name=config["role_name"],
                tenant_id=config["tenant_id"],
                config=json.loads(config.get("config", "{}")),
            )
            if role:
                await role.start()
                self._roles[f"{config['tenant_id']}:{config['role_name']}"] = role
    
    def _create_role(
        self,
        role_name: str,
        tenant_id: str,
        config: dict[str, Any],
    ) -> AgentRole | None:
        """Factory method for creating role instances."""
        if role_name == "detector":
            return DetectorRole(tenant_id, self._bus, self._store)
        elif role_name == "correlator":
            return CorrelatorRole(tenant_id, self._bus, self._store)
        elif role_name == "evolver":
            return EvolverRole(tenant_id, self._bus, self._store)
        # elif role_name == "executor":
        #     return ExecutorRole(tenant_id, self._bus, self._store)
        return None
    
    async def _monitor_loop(self) -> None:
        """Monitor role health and restart failed roles."""
        while True:
            try:
                for key, role in list(self._roles.items()):
                    hb = role.heartbeat()
                    
                    # Check heartbeat timeout
                    if time.time() - hb["last_heartbeat"] > self.HEARTBEAT_TIMEOUT:
                        log.warning(
                            "Role %s heartbeat timeout, restarting", key
                        )
                        await self._restart_role(key, role)
                    
                    # Update store with health info
                    self._store.update_role_health(
                        tenant_id=role._tenant_id,
                        role_name=role.role_name,
                        status=hb["status"],
                        messages_processed=hb["messages_processed"],
                        messages_failed=hb["messages_failed"],
                    )
                
                await asyncio.sleep(30)  # Monitor interval
            
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Coordinator monitor error")
                await asyncio.sleep(5)
    
    async def _restart_role(self, key: str, role: AgentRole) -> None:
        """Restart a failed role."""
        count = self._restart_counts.get(key, 0)
        
        if count >= self.MAX_RESTARTS:
            log.error(
                "Role %s exceeded max restarts (%d), marking as failed",
                key,
                self.MAX_RESTARTS,
            )
            self._store.update_role_status(
                tenant_id=role._tenant_id,
                role_name=role.role_name,
                status="error",
            )
            # Publish alert
            await self._bus.publish(
                tenant_id=role._tenant_id,
                topic="alert",
                from_role="coordinator",
                message={
                    "alert_type": "role_failed",
                    "role_name": role.role_name,
                    "message": f"Role {key} failed after {self.MAX_RESTARTS} restarts",
                },
            )
            return
        
        await role.stop()
        await role.start()
        self._restart_counts[key] = count + 1
        log.info("Role %s restarted (attempt %d)", key, count + 1)
    
    def get_role_health(self) -> list[dict[str, Any]]:
        """Get health status for all roles."""
        return [
            {
                "tenant_id": role._tenant_id,
                "role_name": role.role_name,
                **role.heartbeat(),
            }
            for role in self._roles.values()
        ]
```

---

## 6. Department Orchestration

### 6.1 Outreach Department

```python
"""departments/outreach.py — Outreach orchestration loop."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..bus import MessageBus
from ..store import AgentOSStore

log = logging.getLogger(__name__)


class OutreachOrchestrator:
    """Autonomous outreach optimization loop.
    
    Sub-loops:
    1. Lead scoring optimization
    2. Sequence template A/B testing
    3. Follow-up timing adjustment
    """
    
    def __init__(self, tenant_id: str, store: AgentOSStore, bus: MessageBus) -> None:
        self._tenant_id = tenant_id
        self._store = store
        self._bus = bus
        self._config = self._load_config()
    
    def _load_config(self) -> dict[str, Any]:
        """Load department config from tenant settings."""
        config = self._store.get_department_config(self._tenant_id, "outreach")
        return config or {
            "enabled": False,
            "auto_execute_max_improvement": 0.10,
            "auto_execute_max_cost": 50.0,
            "scoring_threshold": 0.6,
            "reply_rate_threshold": 0.05,
            "idle_days_threshold": 7,
        }
    
    async def evaluate(self) -> list[dict[str, Any]]:
        """Run evaluation cycle. Returns list of proposed actions."""
        if not self._config.get("enabled", False):
            return []
        
        actions = []
        
        # Sub-Loop 1: Lead Scoring
        scoring_action = await self._evaluate_scoring()
        if scoring_action:
            actions.append(scoring_action)
        
        # Sub-Loop 2: Sequence Templates
        template_action = await self._evaluate_templates()
        if template_action:
            actions.append(template_action)
        
        # Sub-Loop 3: Follow-Up Timing
        timing_action = await self._evaluate_timing()
        if timing_action:
            actions.append(timing_action)
        
        return actions
    
    async def _evaluate_scoring(self) -> dict[str, Any] | None:
        """Evaluate lead scoring health."""
        stats = self._store.get_outreach_stats(
            tenant_id=self._tenant_id,
            stat="lead_score_distribution",
            days=7,
        )
        
        if not stats:
            return None
        
        low_score_pct = stats.get("below_threshold_pct", 0)
        
        if low_score_pct > 0.10:  # >10% of leads below threshold
            return {
                "department": "outreach",
                "action_type": "propose_scoring_adjustment",
                "signal": f"lead_score below threshold for {low_score_pct:.0%} of leads",
                "proposed_action": "Adjust scoring weights",
                "metric_name": "outreach.lead_score_health",
                "metric_value": low_score_pct,
                "threshold": 0.10,
                "requires_approval": True,
                "risk_level": "medium",
            }
        
        return None
    
    async def _evaluate_templates(self) -> dict[str, Any] | None:
        """Evaluate sequence template performance."""
        stats = self._store.get_outreach_stats(
            tenant_id=self._tenant_id,
            stat="reply_rate_by_template",
            days=14,
        )
        
        for template in stats.get("templates", []):
            if template["reply_rate"] < self._config["reply_rate_threshold"]:
                return {
                    "department": "outreach",
                    "action_type": "propose_template_test",
                    "signal": f"reply_rate {template['reply_rate']:.1%} for template {template['template_id']}",
                    "proposed_action": f"A/B test new variant of template {template['template_id']}",
                    "metric_name": "outreach.reply_rate",
                    "metric_value": template["reply_rate"],
                    "threshold": self._config["reply_rate_threshold"],
                    "requires_approval": template["reply_rate"] < 0.02,  # Very low = human review
                    "risk_level": "low",
                }
        
        return None
    
    async def _evaluate_timing(self) -> dict[str, Any] | None:
        """Evaluate follow-up timing."""
        stats = self._store.get_outreach_stats(
            tenant_id=self._tenant_id,
            stat="idle_leads",
            days=1,
        )
        
        idle_count = stats.get("idle_count", 0)
        
        if idle_count > 0:
            return {
                "department": "outreach",
                "action_type": "create_followup_activity",
                "signal": f"{idle_count} leads idle for >{self._config['idle_days_threshold']} days",
                "proposed_action": "Create follow-up activities for idle leads",
                "metric_name": "outreach.idle_leads",
                "metric_value": idle_count,
                "threshold": 0,
                "requires_approval": idle_count > 20,  # Large batch = human review
                "risk_level": "low",
            }
        
        return None
```

---

## 7. Testing Requirements

### 7.1 Test File Structure

```
tests/
├── test_webhooks.py          # Webhook ingestion tests
├── test_webhook_worker.py    # Webhook processing tests
├── test_roles/
│   ├── test_detector.py
│   ├── test_correlator.py
│   ├── test_evolver.py
│   └── test_base.py
├── test_bus.py              # Message bus tests
├── test_coordinator.py      # Coordinator tests
├── test_departments/
│   ├── test_outreach.py
│   └── test_engagements.py
└── test_integration.py      # Integration tests
```

### 7.2 Test Requirements

- All new modules must have >90% code coverage
- Async tests use `pytest-asyncio`
- Mock external providers (GitHub, Stripe) with fixture payloads
- Test idempotency: same event_id → no duplicate signals
- Test role failure: coordinator restarts after crash
- Test message bus: at-least-once delivery, dead letter queue

### 7.3 Example Test

```python
"""tests/test_webhooks.py."""

import pytest
from agent_os.webhooks import WebhookIngester


@pytest.fixture
def ingester(store):
    return WebhookIngester(store)


def test_github_webhook_accepted(ingester, github_push_payload, github_headers):
    """GitHub push webhook is accepted and queued."""
    status, response = ingester.ingest(
        source="github",
        payload=github_push_payload,
        headers=github_headers,
        raw_body=json.dumps(github_push_payload).encode(),
    )
    assert status == 200
    assert response["status"] == "queued"


def test_duplicate_webhook_rejected(ingester, github_push_payload, github_headers):
    """Duplicate event_id returns 200 with duplicate status."""
    raw = json.dumps(github_push_payload).encode()
    
    # First ingestion
    ingester.ingest("github", github_push_payload, github_headers, raw)
    
    # Duplicate
    status, response = ingester.ingest("github", github_push_payload, github_headers, raw)
    assert status == 200
    assert response["status"] == "duplicate"


def test_invalid_signature_rejected(ingester, github_push_payload):
    """Invalid HMAC signature returns 400."""
    headers = {"X-Hub-Signature-256": "sha256=invalid"}
    status, response = ingester.ingest(
        source="github",
        payload=github_push_payload,
        headers=headers,
        raw_body=json.dumps(github_push_payload).encode(),
    )
    assert status == 400
```

---

## 8. Performance Targets

| Metric | Target | How Measured |
|--------|--------|-------------|
| Webhook POST response | < 500ms p99 | Server access log |
| Webhook → Signal creation | < 5s p99 | webhook_events.processed_at - received_at |
| Message bus publish | < 100ms p99 | SQLite insert time |
| Message bus consume | < 50ms p99 | SQLite query time |
| Role heartbeat interval | 30s | Coordinator config |
| Role restart time | < 10s | Coordinator restart logic |
| Webhook worker poll | 1s interval | asyncio.sleep(1) |

---

## 8. Monitoring & Observability

### 8.1 Logging Standards

All new modules use `logging.getLogger(__name__)` with structured extras:

```python
log.info(
    "Webhook processed",
    extra={
        "tenant_id": tenant_id,
        "event_id": event_id,
        "source": source,
        "processing_ms": elapsed,
    },
)
```

### 8.2 Dashboard Stats

```
GET /api/agent-os/webhooks/stats
{
  "events_received_24h": 142,
  "events_processed_24h": 140,
  "events_failed_24h": 2,
  "avg_processing_ms": 45,
  "last_event_at": "2026-08-05T12:34:56Z",
  "by_source": {
    "github": {"received": 80, "processed": 79, "failed": 1},
    "stripe": {"received": 45, "processed": 45, "failed": 0},
    "custom": {"received": 17, "processed": 16, "failed": 1}
  }
}

GET /api/agent-os/roles/health
{
  "roles": [
    {
      "role_name": "detector",
      "status": "active",
      "last_heartbeat": "2026-08-05T12:34:56Z",
      "messages_processed_24h": 1234,
      "messages_failed_24h": 2
    }
  ]
}

GET /api/agent-os/departments/outreach/stats
{
  "enabled": true,
  "actions_taken_30d": 45,
  "actions_blocked_30d": 3,
  "actions_pending": 1,
  "last_action_at": "2026-08-05T10:00:00Z",
  "metrics": {
    "reply_rate": 0.08,
    "lead_score_health": 0.85,
    "idle_leads": 12
  }
}
```

---

## 9. Deployment & Operations

### 9.1 Migration Path

1. **Phase 1:** Deploy webhook ingestion (no impact on existing features)
2. **Phase 2:** Deploy message bus + coordinator (internal refactor)
3. **Phase 3:** Wrap existing detector/correlator as roles
4. **Phase 4:** Deploy Evolver role
5. **Phase 5:** Enable department orchestration (tenant-by-tenant)

### 9.2 Rollback Plan

- All features are additive (new tables, new modules)
- Rollback = disable new routes, stop new roles
- Existing functionality (signals, experiments, promotions) untouched

### 9.3 Configuration

```python
# In server.py — startup configuration
ENABLE_ROLES = os.environ.get("ENABLE_ROLES", "false").lower() == "true"
ENABLE_WEBHOOKS = os.environ.get("ENABLE_WEBHOOKS", "false").lower() == "true"
ENABLE_DEPARTMENTS = os.environ.get("ENABLE_DEPARTMENTS", "false").lower() == "true"
```

---

## 10. Adversarial QA Checklist

| Claim | Verification Method | Status |
|-------|-------------------|--------|
| Webhook HMAC verification | Unit test with valid/invalid signatures | 🔲 TODO |
| Idempotency (no duplicate signals) | Integration test with duplicate event_id | 🔲 TODO |
| Message bus at-least-once delivery | Simulate crash mid-processing, verify redelivery | 🔲 TODO |
| Role auto-restart on crash | Kill process, verify coordinator restarts | 🔲 TODO |
| Tenant isolation (cross-tenant blocked) | Attempt cross-tenant access, verify 403 | 🔲 TODO |
| Human approval gates | Attempt rule change without approval, verify blocked | 🔲 TODO |
| Performance targets | Load test with 1000 webhook events | 🔲 TODO |

---

*TRD aligned with BRD.md and PRD.md. Technical specifications derived from architecture document.*
