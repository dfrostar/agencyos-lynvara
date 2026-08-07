"""base.py — Abstract base class for department orchestration."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from agent_os.bus import MessageBus

log = logging.getLogger(__name__)


class Department:
    """Autonomous business function orchestrator.

    Departments consume signals from the bus and take actions
    within human-defined safety bounds.
    """

    NAME: str = "department"
    AUTO_EXECUTE_MAX_IMPROVEMENT = 0.10  # 10%
    AUTO_EXECUTE_MAX_COST = 50.0  # $50

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
        self._enabled = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._dept_id = f"{self.NAME}_{uuid.uuid4().hex[:8]}"

    def start(self) -> None:
        """Start the department's background thread."""
        with self._lock:
            if self._enabled:
                return
            self._enabled = True
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name=f"{self.NAME}-dept",
            )
            self._thread.start()
            log.info("Department %s started for tenant %s", self.NAME, self._tenant_id)

    def stop(self) -> None:
        """Stop the department's background thread."""
        with self._lock:
            self._enabled = False
        if self._thread:
            self._thread.join(timeout=5.0)

    def _run_loop(self) -> None:
        """Main loop: consume messages, evaluate, act."""
        import time
        while self._enabled:
            try:
                self._poll()
            except Exception:
                log.exception("Department %s error", self.NAME)
            time.sleep(self._config.get("poll_interval", 60.0))

    def _poll(self) -> None:
        """Override in subclasses."""
        raise NotImplementedError

    def can_auto_execute(self, improvement: float, cost: float) -> bool:
        """Check if action is within auto-execute bounds."""
        max_imp = getattr(self, "_auto_execute_max_improvement", self.AUTO_EXECUTE_MAX_IMPROVEMENT)
        max_cost = getattr(self, "_auto_execute_max_cost", self.AUTO_EXECUTE_MAX_COST)
        return improvement < max_imp and cost < max_cost

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish a message to the bus."""
        from agent_os.bus import Message
        msg = Message(
            topic=topic,
            payload=payload,
            from_role=f"dept_{self.NAME}",
        )
        self._bus.publish(msg)
