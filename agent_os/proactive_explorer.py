"""proactive_explorer.py — Proactive Experimentation for Agent OS.

Identifies unexplored areas and proposes experiments:

- Stale incumbent detection: tuner incumbents with no experiments in 7+ days
- Metric coverage analysis: signals tracked but never experimented on
- Adversarial probing: uses generate_adversarial_query() to find edge cases
  and proposes experiments to validate them

Runs on a schedule (daily via cron or background thread). Thread-safe.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from .adversarial import generate_adversarial_query

log = logging.getLogger(__name__)

# Thresholds
_STALE_INCUMBENT_DAYS = 7
_STALE_INCUMBENT_SEC = _STALE_INCUMBENT_DAYS * 86400


class ProactiveExplorer:
    """Identifies gaps in exploration and proposes experiments.

    Thread-safe. Designed to be called from a background thread on a
    daily schedule, or on-demand via the /engine/trigger endpoint.
    """

    def __init__(self, store: Any, tenant_id: str = "default") -> None:
        self._store = store
        self._tenant_id = tenant_id
        self._lock = threading.Lock()
        self._last_run: str | None = None
        self._proposals_made: int = 0

    def run_cycle(self) -> dict[str, Any]:
        """Run a full exploration cycle.

        Returns a summary of what was found and proposed.
        """
        with self._lock:
            self._last_run = datetime.now(timezone.utc).isoformat()

            stale = self._detect_stale_incumbents()
            gaps = self._detect_metric_gaps()
            adversarial = self._probe_edges()

            proposed = []
            proposed.extend(self._propose_stale_experiments(stale))
            proposed.extend(self._propose_gap_experiments(gaps))
            proposed.extend(self._propose_adversarial_experiments(adversarial))

            self._proposals_made += len(proposed)

            summary_parts = []
            if stale:
                summary_parts.append(f"{len(stale)} stale incumbents")
            if gaps:
                summary_parts.append(f"{len(gaps)} unexperimented metrics")
            if adversarial:
                summary_parts.append(f"{len(adversarial)} edge cases probed")
            summary_parts.append(f"{len(proposed)} experiments proposed")

            return {
                "cycle_run_at": self._last_run,
                "stale_incumbents": stale,
                "metric_gaps": gaps,
                "adversarial_probes": adversarial,
                "proposed_experiments": proposed,
                "total_proposed": len(proposed),
                "summary": "; ".join(summary_parts),
            }

    def _detect_stale_incumbents(self) -> list[dict[str, Any]]:
        """Find tuner incumbents with no experiments in 7+ days."""
        conn = self._store._get_conn()
        # Use timestamp comparison (SQLite stores ISO datetime as text)
        # Compare using strftime('%s', ...) to get Unix epoch
        rows = conn.execute(
            """SELECT ti.metric_name, ti.value, ti.tag, ti.updated_at,
                      MAX(e.created_at) as last_experiment_at
               FROM tuner_incumbents ti
               LEFT JOIN experiments e
                 ON e.tenant_id = ti.tenant_id
                 AND e.metric_name = ti.metric_name
               WHERE ti.tenant_id = ?
               GROUP BY ti.metric_name
               HAVING last_experiment_at IS NULL
                   OR (strftime('%s', 'now') - strftime('%s', last_experiment_at)) > ?""",
            (self._tenant_id, _STALE_INCUMBENT_SEC),
        ).fetchall()
        return [dict(r) for r in rows]

    def _detect_metric_gaps(self) -> list[dict[str, Any]]:
        """Find metrics that are tracked but never experimented on."""
        conn = self._store._get_conn()
        # Get all metrics from signals that have no corresponding experiment
        rows = conn.execute(
            """SELECT DISTINCT s.metric_name,
                      COUNT(*) as signal_count,
                      MAX(s.signal_ts) as last_signal_ts
               FROM signals s
               LEFT JOIN experiments e
                 ON e.tenant_id = s.tenant_id
                 AND e.metric_name = s.metric_name
               WHERE s.tenant_id = ?
                 AND e.id IS NULL
               GROUP BY s.metric_name""",
            (self._tenant_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _probe_edges(self) -> list[dict[str, Any]]:
        """Use adversarial queries to find edge cases in current tuner values."""
        conn = self._store._get_conn()
        rows = conn.execute(
            """SELECT metric_name, value, tag, history
               FROM tuner_incumbents
               WHERE tenant_id = ?""",
            (self._tenant_id,),
        ).fetchall()

        probes = []
        for row in rows:
            # Build a hypothesis about the incumbent value
            hypothesis = (
                f"Current value {row['value']} for {row['metric_name']} "
                f"is optimal (tag={row['tag']}). History: {row['history'] or ''}"
            )
            query = generate_adversarial_query(
                metric_name=row["metric_name"],
                hypothesis=hypothesis,
                cause_type="param_change",
            )
            probes.append({
                "metric_name": row["metric_name"],
                "current_value": row["value"],
                "current_tag": row["tag"],
                "adversarial_query": query,
            })

            # Store the adversarial query in the store
            self._store.insert_adversarial_query(
                tenant_id=self._tenant_id,
                record={
                    "query": query,
                    "metric_name": row["metric_name"],
                    "source_hypothesis": hypothesis,
                    "cause_type": "param_change",
                },
            )

        return probes

    def _propose_stale_experiments(
        self, stale: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Propose exploratory experiments for stale incumbents."""
        proposed = []
        for inc in stale:
            metric = inc["metric_name"]
            current_value = inc["value"]

            # Propose a small perturbation (+10% or +1, whichever is larger)
            perturbation = max(abs(current_value) * 0.1, 1.0)
            candidate_value = current_value + perturbation

            proposal = self._store.create_proposal(
                tenant_id=self._tenant_id,
                title=f"Proactive exploration: {metric} (stale {_STALE_INCUMBENT_DAYS}+ days)",
                hypothesis=(
                    f"Stale incumbent {metric}={current_value} hasn't been tested "
                    f"in over {_STALE_INCUMBENT_DAYS} days. Probing +10% perturbation "
                    f"to validate current optimum."
                ),
                baseline_tag=inc.get("tag", "baseline"),
                candidate_tag="proactive_exploration",
                metric_name=metric,
                baseline_value=current_value,
                candidate_value=candidate_value,
                tags=["proactive", "stale_incumbent"],
            )
            proposed.append(proposal)
            log.info(
                "Proposed stale-incumbent experiment for %s: %.2f → %.2f",
                metric,
                current_value,
                candidate_value,
            )

        return proposed

    def _propose_gap_experiments(self, gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Propose experiments for tracked-but-never-experimented metrics."""
        proposed = []
        for gap in gaps:
            metric = gap["metric_name"]
            # Use signal average as baseline
            conn = self._store._get_conn()
            avg_row = conn.execute(
                "SELECT AVG(value) as avg_val FROM signals WHERE tenant_id = ? AND metric_name = ?",
                (self._tenant_id, metric),
            ).fetchone()
            baseline = avg_row["avg_val"] if avg_row else 0.0

            # Propose a small improvement
            candidate = baseline * 1.05 if baseline != 0 else 1.0

            proposal = self._store.create_proposal(
                tenant_id=self._tenant_id,
                title=f"Proactive exploration: {metric} (tracked but never experimented)",
                hypothesis=(
                    f"{metric} has {gap['signal_count']} signals but no experiments. "
                    f"Proposing initial experiment to establish baseline."
                ),
                baseline_tag="signal_average",
                candidate_tag="proactive_initial",
                metric_name=metric,
                baseline_value=baseline,
                candidate_value=candidate,
                tags=["proactive", "metric_gap"],
            )
            proposed.append(proposal)
            log.info(
                "Proposed gap-fill experiment for %s: %.2f → %.2f",
                metric,
                baseline,
                candidate,
            )

        return proposed

    def _propose_adversarial_experiments(
        self, probes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Propose experiments from adversarial edge cases."""
        proposed = []
        for probe in probes:
            metric = probe["metric_name"]
            current_value = probe["current_value"]

            # Propose a value that might be a boundary case (try -10%)
            boundary_value = current_value * 0.9

            proposal = self._store.create_proposal(
                tenant_id=self._tenant_id,
                title=f"Adversarial probe: {metric} (edge case test)",
                hypothesis=(
                    f"Adversarial probe suggests {metric} may not be optimal. "
                    f"Testing -10% boundary to validate robustness."
                ),
                baseline_tag=probe.get("current_tag", "baseline"),
                candidate_tag="adversarial_boundary",
                metric_name=metric,
                baseline_value=current_value,
                candidate_value=boundary_value,
                tags=["proactive", "adversarial", "edge_case"],
            )
            proposed.append(proposal)
            log.info(
                "Proposed adversarial experiment for %s: %.2f → %.2f",
                metric,
                current_value,
                boundary_value,
            )

        return proposed

    def get_status(self) -> dict[str, Any]:
        """Get current explorer status."""
        return {
            "last_run": self._last_run,
            "total_proposals_made": self._proposals_made,
            "tenant_id": self._tenant_id,
        }
