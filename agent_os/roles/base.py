"""base.py — Abstract base class for all Agent OS roles."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from agent_os.bus import Message, MessageBus

log = logging.getLogger(__name__)


class AgentRole:
    """Abstract base class for specialized agent roles.

    Lifecycle: start() → consume messages → process → publish → heartbeat
    Thread-safe. Designed to run as a background daemon thread.
    """

    ROLE_NAME: str = "role"

    def __init__(
        self,
        tenant_id: str,
        bus: MessageBus,
        store: Any,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._bus = bus
        self._store = store
        self._config = config or {}
        self._role_id = f"{self.ROLE_NAME}_{uuid.uuid4().hex[:8]}"
        self._enabled = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the role's background thread."""
        with self._lock:
            if self._enabled:
                return
            self._enabled = True
            self._store.register_role({
                "role_id": self._role_id,
                "tenant_id": self._tenant_id,
                "role_name": self.ROLE_NAME,
                "status": "active",
                "config": str(self._config) if self._config else None,
            })
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name=f"{self.ROLE_NAME}-role",
            )
            self._thread.start()
            log.info("Role %s started for tenant %s", self.ROLE_NAME, self._tenant_id)

    def stop(self) -> None:
        """Stop the role's background thread."""
        with self._lock:
            self._enabled = False
        if self._thread:
            self._thread.join(timeout=5.0)

    def heartbeat(self) -> None:
        """Update role heartbeat in the registry."""
        self._store.update_role_heartbeat(self._role_id, "active")

    def _run_loop(self) -> None:
        """Main loop: consume messages, process, publish results."""
        import time
        while self._enabled:
            try:
                self._poll()
                self.heartbeat()
            except Exception:
                log.exception("Role %s error", self.ROLE_NAME)
                self._store.update_role_heartbeat(self._role_id, "error")
            time.sleep(self._config.get("poll_interval", 1.0))

    def _poll(self) -> None:
        """Override in subclasses to implement role-specific logic."""
        raise NotImplementedError

    def publish(self, topic: str, payload: dict[str, Any], to_role: str | None = None) -> None:
        """Publish a message to the bus."""
        msg = Message(
            topic=topic,
            payload=payload,
            from_role=self.ROLE_NAME,
            to_role=to_role,
        )
        self._bus.publish(msg)
        self._store.update_role_counters(self._role_id, messages_processed=1)
