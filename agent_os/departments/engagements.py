"""engagements.py — Autonomous engagement health department."""

from __future__ import annotations

import logging
from typing import Any

from .base import Department

log = logging.getLogger(__name__)


class EngagementDepartment(Department):
    """Autonomously detect and respond to engagement health degradation.

    Signal: engagement_velocity drops → trigger investigation
    Signal: days_since_last_activity exceeds threshold → create check-in
    Signal: assessment_completion_rate drops → propose simplification
    """

    NAME = "engagements"

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

                if "engagement_velocity" in metric:
                    self._handle_velocity_drop(payload)
                elif "days_since_last_activity" in metric:
                    self._handle_idle_engagement(payload)
                elif "assessment_completion" in metric:
                    self._handle_completion_drop(payload)

                self._bus.acknowledge(msg.message_id)
            except Exception:
                log.exception("Engagement dept failed on message %s", msg.message_id)

    def _handle_velocity_drop(self, payload: dict[str, Any]) -> None:
        """Handle engagement_velocity drop."""
        value = payload.get("value", 0.0)
        baseline = payload.get("baseline", 0.0)
        if value < baseline:
            log.info("Engagement: velocity drop detected, triggering investigation")

    def _handle_idle_engagement(self, payload: dict[str, Any]) -> None:
        """Handle idle engagement."""
        value = payload.get("value", 0)
        if value > 7:
            log.info("Engagement: %d days idle, creating check-in activity", value)

    def _handle_completion_drop(self, payload: dict[str, Any]) -> None:
        """Handle assessment completion rate drop."""
        value = payload.get("value", 0.0)
        baseline = payload.get("baseline", 0.0)
        if value < baseline:
            improvement = baseline - value
            if self.can_auto_execute(improvement, 0):
                log.info("Engagement: proposing simplification for completion drop")
