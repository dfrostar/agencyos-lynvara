"""outreach.py — Autonomous outreach department."""

from __future__ import annotations

import logging
from typing import Any

from .base import Department

log = logging.getLogger(__name__)


class OutreachDepartment(Department):
    """Autonomously optimize outreach sequences.

    Signal: lead_score drops → propose scoring weight adjustment
    Signal: reply_rate drops → propose A/B test
    Signal: idle leads → create follow-up activity
    """

    NAME = "outreach"

    def __init__(
        self,
        tenant_id: str,
        bus: Any,
        store: Any,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(tenant_id, bus, store, config)
        self._auto_execute_max_improvement = config.get("max_improvement", 0.10) if config else 0.10
        self._auto_execute_max_cost = config.get("max_cost", 50.0) if config else 50.0

    def _poll(self) -> None:
        """Consume signals and take action."""
        messages = self._bus.consume("signal", f"dept_{self.NAME}")
        for msg in messages:
            try:
                payload = msg.payload
                metric = payload.get("metric_name", "")

                if "lead_score" in metric:
                    self._handle_lead_score(payload)
                elif "reply_rate" in metric:
                    self._handle_reply_rate(payload)
                elif "idle_leads" in metric:
                    self._handle_idle_leads(payload)

                self._bus.acknowledge(msg.message_id)
            except Exception:
                log.exception("Outreach failed on message %s", msg.message_id)

    def _handle_lead_score(self, payload: dict[str, Any]) -> None:
        """Handle lead_score drop signal."""
        value = payload.get("value", 0.0)
        baseline = payload.get("baseline", 0.0)
        if value < baseline:
            improvement = baseline - value
            if self.can_auto_execute(improvement, 0):
                log.info("Outreach: auto-adjusting scoring weights for lead_score drop")

    def _handle_reply_rate(self, payload: dict[str, Any]) -> None:
        """Handle reply_rate drop signal."""
        value = payload.get("value", 0.0)
        baseline = payload.get("baseline", 0.0)
        if value < baseline:
            improvement = baseline - value
            if self.can_auto_execute(improvement, 0):
                log.info("Outreach: auto-proposing A/B test for reply_rate drop")

    def _handle_idle_leads(self, payload: dict[str, Any]) -> None:
        """Handle idle leads signal."""
        value = payload.get("value", 0)
        if value > 7:
            log.info("Outreach: creating follow-up for %d idle leads", value)
