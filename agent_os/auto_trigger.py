"""auto_trigger.py — Auto-trigger loop for Agent OS signal → proposal → experiment.

When a signal fires and an insight is generated:
1. Auto-create a Proposal (or increment signal_count on existing open proposal)
2. When signal_count >= MIN_SIGNALS_BEFORE_AUTO_PROMOTE → auto-run experiment
3. When experiment verdict = PROMOTED → tuner incumbent updated
4. When experiment verdict = ROLLED_BACK → revert to baseline_tag

Uses the unified SQLite store for all persistence.
Pattern: fail-open everywhere, audit logging never blocks.
"""

from __future__ import annotations

import logging
from typing import Any

from .promotion import (
    MIN_SIGNALS_BEFORE_AUTO_PROMOTE,
    PromotionEngine,
    Proposal,
    TunerIncumbent,
    _tuner_incumbent_ship_callable,
)
from .signals import Signal

log = logging.getLogger(__name__)


class AutoTriggerLoop:
    """Wires signal fire → proposal creation → experiment → promotion/rollback.

    Usage:
        correlator = RootCauseCorrelator()
        detector = SignalDetector(correlator=correlator, store=store, tenant_id="default")
        loop = AutoTriggerLoop(detector, store=store, tenant_id="default")
    """

    def __init__(
        self,
        signal_detector: Any,
        store: Any = None,
        tenant_id: str = "default",
        incumbent: TunerIncumbent | None = None,
    ) -> None:
        self._detector = signal_detector
        self._store = store
        self._tenant_id = tenant_id
        self._incumbent = incumbent
        self._engine: PromotionEngine | None = None
        if incumbent is not None:
            self._engine = PromotionEngine(incumbent=incumbent, store=store, tenant_id=tenant_id)
        # Register the auto-trigger callback
        self._detector._auto_trigger = self._on_signal_insight

    def _on_signal_insight(self, signal: Signal, insight: Any) -> None:
        """Called when a signal fires and an insight is generated."""
        # Use the signal's owning tenant (threaded from the route), falling
        # back to the loop's configured tenant for CLI/direct usage.
        tenant_id = signal.tenant_id or self._tenant_id
        store = self._store
        if store is None:
            from .store import get_store

            store = get_store()

        # Atomic find-or-create (S7: prevents TOCTOU duplicate proposals).
        # Holds the store lock across the list-and-create span.
        proposal, _created = store.get_or_create_proposal(
            tenant_id=tenant_id,
            title=f"Auto: {signal.metric_name} anomaly detected",
            hypothesis=insight.hypothesis,
            baseline_tag="baseline",
            candidate_tag="candidate",
            metric_name=signal.metric_name,
            baseline_value=signal.baseline,
            candidate_value=signal.value,
            tags=[
                "auto-triggered",
                (
                    insight.cause_type.value
                    if hasattr(insight.cause_type, "value")
                    else str(insight.cause_type)
                ),
            ],
            signal_count=1,
        )

        if _created:
            signal_count = 1
            log.info(
                "Auto-created proposal %s for signal %s (insight: %s)",
                proposal["proposal_id"],
                signal.signal_id,
                insight.insight_id,
            )
        else:
            # Increment signal count on existing proposal
            proposal = store.increment_signal_count(tenant_id, proposal["proposal_id"])
            if proposal is None:
                return
            signal_count = proposal.get("signal_count", 0)
            log.info(
                "Incremented signal_count on proposal %s to %d",
                proposal["proposal_id"],
                signal_count,
            )

        # Check if we should auto-run the experiment
        if signal_count >= MIN_SIGNALS_BEFORE_AUTO_PROMOTE:
            self._auto_run_experiment(proposal)

    def _auto_run_experiment(self, proposal_dict: dict[str, Any]) -> None:
        """Run an experiment for a proposal if conditions are met."""
        store = self._store
        # Use the proposal's owning tenant (threaded through the signal),
        # falling back to the loop's configured tenant for CLI/direct paths.
        tenant_id = proposal_dict.get("tenant_id") or self._tenant_id
        metric_name = proposal_dict.get("metric_name", "unknown")
        baseline_value = proposal_dict.get("baseline_value", 0.0)
        candidate_value = proposal_dict.get("candidate_value", 0.0)
        baseline_tag = proposal_dict.get("baseline_tag", "baseline")
        candidate_tag = proposal_dict.get("candidate_tag", "candidate")

        # Create or reuse incumbent
        if self._incumbent is None or self._incumbent.metric_name != metric_name:
            self._incumbent = TunerIncumbent(
                metric_name,
                baseline_value,
                baseline_tag,
                store=store,
                tenant_id=tenant_id,
            )
            self._engine = PromotionEngine(
                incumbent=self._incumbent,
                store=store,
                tenant_id=tenant_id,
            )

        # Create Proposal object for PromotionEngine
        proposal = Proposal(
            proposal_id=proposal_dict["proposal_id"],
            title=proposal_dict.get("title", ""),
            hypothesis=proposal_dict.get("hypothesis", ""),
            baseline_tag=baseline_tag,
            candidate_tag=candidate_tag,
            metric_name=metric_name,
            baseline_value=baseline_value,
            candidate_value=candidate_value,
            status="running",
            signal_count=proposal_dict.get("signal_count", 0),
        )

        if self._engine is None:
            self._engine = PromotionEngine(
                incumbent=self._incumbent,
                proposal=proposal,
                signal_count=proposal.signal_count,
                store=store,
                tenant_id=tenant_id,
            )
        else:
            self._engine._proposal = proposal
            self._engine._signal_count = proposal.signal_count
            # Rewire ship callable now that we have a proposal — the
            # initial engine was created with proposal=None which installs
            # _noop_ship. With a real proposal the incumbent can be updated.
            self._engine._ship_callable = _tuner_incumbent_ship_callable(self._incumbent, proposal)
            self._engine._auto_promote = True

        # Mark proposal as running
        if store:
            store.update_proposal(tenant_id, proposal.proposal_id, {"status": "running"})

        # Run the experiment
        # Auto-triggered proposals assume higher is better (improvement).
        # The candidate value is expected to be >= the baseline.
        result = self._engine.run(higher_is_better=True)

        # Update proposal status/count. Note: experiment verdicts and CI are
        # persisted by the engine to the `experiments` table — there are no
        # last_verdict / last_experiment_id columns on proposals, so stamping
        # them here would be silently dropped (dead code). Remove that practice.
        if store:
            store.update_proposal(
                tenant_id,
                proposal.proposal_id,
                {
                    "status": proposal.status,
                    "signal_count": proposal.signal_count,
                },
            )

        log.info(
            "Auto-ran experiment for proposal %s: verdict=%s, delta=%.3f, incumbent=%s",
            proposal.proposal_id,
            result.verdict.value,
            result.delta,
            self._incumbent.value,
        )
