"""detector.py — Detector role wrapping SignalDetector."""

from __future__ import annotations

import logging
from typing import Any

from agent_os.signals import Signal, SignalDetector

from .base import AgentRole

log = logging.getLogger(__name__)


class DetectorRole(AgentRole):
    """Wraps SignalDetector as a role.

    Consumes: metric_value messages (from webhook ingestion)
    Publishes: signal messages
    """

    ROLE_NAME = "detector"

    def __init__(
        self,
        tenant_id: str,
        bus: Any,
        store: Any,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(tenant_id, bus, store, config)
        self._detector = SignalDetector(
            lambda_threshold=config.get("lambda_threshold", 4.0) if config else 4.0,
            cooldown_seconds=config.get("cooldown_seconds", 60.0) if config else 60.0,
            store=store,
            tenant_id=tenant_id,
        )

    def _poll(self) -> None:
        """Consume metric_value messages and push to detector."""
        messages = self._bus.consume("metric_value", self.ROLE_NAME, tenant_id=self._tenant_id)
        for msg in messages:
            try:
                payload = msg["payload"]
                signal = self._detector.push(
                    metric_name=payload["metric_name"],
                    value=float(payload["value"]),
                    tenant_id=self._tenant_id,
                )
                if signal is not None:
                    self._bus.publish(
                        topic="signal",
                        payload=signal.to_dict(),
                        to_role="correlator",
                        tenant_id=self._tenant_id,
                    )
                self._bus.acknowledge(msg["message_id"])
            except Exception:
                log.exception("Detector failed on message %s", msg.get("message_id"))
                self._store.update_role_counters(self._role_id, messages_failed=1)
