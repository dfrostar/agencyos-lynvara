"""correlator.py — Correlator role wrapping RootCauseCorrelator."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agent_os.correlator import RootCauseCorrelator

from .base import AgentRole

log = logging.getLogger(__name__)


class CorrelatorRole(AgentRole):
    """Wraps RootCauseCorrelator as a role.

    Consumes: signal messages (from detector)
    Publishes: insight messages (to auto-trigger/proposal)
    """

    ROLE_NAME = "correlator"

    def __init__(
        self,
        tenant_id: str,
        bus: Any,
        store: Any,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(tenant_id, bus, store, config)
        self._correlator = RootCauseCorrelator(
            git_timeout=config.get("git_timeout", 5.0) if config else 5.0,
            lookback_seconds=config.get("lookback_seconds", 3600.0) if config else 3600.0,
        )

    def _poll(self) -> None:
        """Consume signal messages and correlate."""
        messages = self._bus.consume("signal", self.ROLE_NAME, tenant_id=self._tenant_id)
        for msg in messages:
            try:
                payload = msg["payload"]
                signal_type = payload.get("type", "unknown")

                # Only process anomaly signals
                if signal_type != "anomaly":
                    self._bus.acknowledge(msg["message_id"])
                    continue

                from agent_os.signals import Signal
                signal = Signal(
                    signal_id=payload["signal_id"],
                    timestamp=payload["timestamp"],
                    metric_name=payload["metric_name"],
                    value=payload["value"],
                    baseline=payload["baseline"],
                    delta=payload["delta"],
                    severity=payload["severity"],
                )

                insight = self._correlator.correlate(signal, Path("/tmp"))
                if insight:
                    self._bus.publish(
                        topic="insight",
                        payload=insight.to_dict(),
                        to_role="evolver",
                        tenant_id=self._tenant_id,
                    )
                self._bus.acknowledge(msg["message_id"])
            except Exception:
                log.exception("Correlator failed on message %s", msg.get("message_id"))
                self._store.update_role_counters(self._role_id, messages_failed=1)
