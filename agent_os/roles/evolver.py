"""evolver.py — Evolver role that proposes new detection rules."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .base import AgentRole

log = logging.getLogger(__name__)


class EvolverRole(AgentRole):
    """Proposes new detection rules based on gap analysis.

    Consumes: insight messages (from correlator)
    Publishes: proposal messages (to promotion engine)
    Runs: daily gap analysis + weekly pattern mining
    """

    ROLE_NAME = "evolver"

    def __init__(
        self,
        tenant_id: str,
        bus: Any,
        store: Any,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(tenant_id, bus, store, config)
        self._last_gap_analysis = 0.0

    def _poll(self) -> None:
        """Run gap analysis on schedule."""
        import time
        now = time.time()
        interval = self._config.get("gap_interval", 86400.0)  # daily

        if now - self._last_gap_analysis < interval:
            return

        self._last_gap_analysis = now
        self._run_gap_analysis()

    def _run_gap_analysis(self) -> None:
        """Identify gaps and propose new rules."""
        try:
            outcomes = self._store.get_outcomes(self._tenant_id, limit=500)
            if len(outcomes) < 5:
                return

            # Find metrics with high rollback rate
            metrics = {}
            for o in outcomes:
                m = o["metric_name"]
                if m not in metrics:
                    metrics[m] = {"promoted": 0, "rolled_back": 0}
                if o["verdict"] == "promoted":
                    metrics[m]["promoted"] += 1
                elif o["verdict"] == "rolled_back":
                    metrics[m]["rolled_back"] += 1

            for m, counts in metrics.items():
                total = counts["promoted"] + counts["rolled_back"]
                if total < 5:
                    continue
                rollback_rate = counts["rolled_back"] / total
                if rollback_rate > 0.8:
                    # Propose new detection rule for this metric
                    self._bus.publish(
                        topic="proposal",
                        payload={
                            "proposal_id": f"prop_{uuid.uuid4().hex[:8]}",
                            "metric_name": m,
                            "rule_type": "adjust_lambda",
                            "rule_definition": f"High rollback rate ({rollback_rate:.0%}) for {m}",
                            "expected_impact": "reduce_false_positives",
                            "confidence": min(rollback_rate, 0.95),
                            "requires_approval": True,
                        },
                        to_role="coordinator",
                    )
        except Exception:
            log.exception("Evolver gap analysis failed")
