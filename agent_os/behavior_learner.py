"""behavior_learner.py — Behavior Modification Engine for Agent OS.

Analyzes improvement_outcomes and adjusts system parameters:

- Lambda threshold: rollback_rate > 80% → increase lambda (less sensitive);
  promotion_rate > 80% with few signals → decrease lambda (more sensitive)
- Cooldown: burst signals (>5 in 60s) → increase cooldown;
  sparse (<1/day) → decrease cooldown
- Auto-promote threshold per category: success_rate > 75% → lower bar;
  success_rate < 25% → raise bar

All adjusted parameters are persisted to the signal_states table so they
survive restarts and are picked up by the Page-Hinkley detector.

Pattern: fail-open, log everything, never crash the calling loop.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from .experiment import ExperimentStatus

log = logging.getLogger(__name__)

# Tuning constants
_ROLLBACK_SENSITIVITY_THRESHOLD = 0.80  # 80% rollback → desensitize
_PROMOTION_SENSITIVITY_THRESHOLD = 0.80  # 80% promote → sensitize
_MIN_OUTCOMES_FOR_ADJUSTMENT = 5  # need at least N outcomes to learn
_LAMBDA_ADJUSTMENT_STEP = 0.5  # amount to add/subtract from lambda
_LAMBDA_MIN = 1.0  # floor — never go below this
_LAMBDA_MAX = 20.0  # ceiling — never go above this
_COOLDOWN_BURST_WINDOW_SEC = 60.0
_COOLDOWN_BURST_THRESHOLD = 5  # >5 signals in 60s → burst
_COOLDOWN_SPARSE_THRESHOLD_SEC = 86400.0  # <1/day → sparse
_COOLDOWN_ADJUSTMENT_FACTOR = 1.5  # multiply/divide cooldown by this
_COOLDOWN_MIN = 10.0  # floor
_COOLDOWN_MAX = 3600.0  # ceiling


class BehaviorLearner:
    """Learns from outcomes and adjusts system parameters.

    Thread-safe. Designed to be called from multiple contexts:
    - After every promotion/rollback verdict (sync callback)
    - Periodically from a background thread for cooldown tuning
    """

    def __init__(self, store: Any, tenant_id: str = "default") -> None:
        self._store = store
        self._tenant_id = tenant_id
        self._lock = threading.Lock()
        # Per-metric auto-promote signal count overrides (B-09.2)
        # category -> adjusted signal_count
        self._category_auto_promote: dict[str, int] = {}

    def on_outcome(
        self,
        metric_name: str,
        verdict: ExperimentStatus,
        delta: float,
        baseline_value: float,
        candidate_value: float,
        proposal_id: str,
        experiment_id: str,
    ) -> dict[str, Any]:
        """Record an outcome and adjust parameters for the metric.

        Returns a dict describing what was adjusted (for observability).
        """
        with self._lock:
            adjustments: dict[str, Any] = {
                "metric_name": metric_name,
                "verdict": verdict.value,
                "adjustments": [],
            }

            # 1. Record the outcome
            self._store.record_outcome(
                tenant_id=self._tenant_id,
                proposal_id=proposal_id,
                experiment_id=experiment_id,
                metric_name=metric_name,
                verdict=verdict.value,
                delta=delta,
                baseline_value=baseline_value,
                candidate_value=candidate_value,
            )

            # 2. Adjust lambda threshold based on rollback/promotion rate
            lambda_adj = self._adjust_lambda(metric_name)
            if lambda_adj is not None:
                adjustments["adjustments"].append(lambda_adj)

            # 3. Adjust auto-promote threshold based on category success rate
            cat_adj = self._adjust_auto_promote(metric_name, verdict)
            if cat_adj is not None:
                adjustments["adjustments"].append(cat_adj)

            return adjustments

    def adjust_cooldowns(self) -> list[dict[str, Any]]:
        """Periodic cooldown adjustment based on signal frequency.

        Called from the background thread. Queries signals table for
        recent burst/sparse patterns and adjusts cooldowns.
        """
        with self._lock:
            adjustments = []
            conn = self._store._get_conn()
            rows = conn.execute(
                """SELECT metric_name, COUNT(*) as cnt,
                          MAX(signal_ts) as last_ts,
                          MIN(signal_ts) as first_ts
                   FROM signals
                   WHERE tenant_id = ?
                     AND signal_ts > ?
                   GROUP BY metric_name""",
                (
                    self._tenant_id,
                    datetime.now(timezone.utc).timestamp() - 86400,  # last 24h
                ),
            ).fetchall()

            for row in rows:
                metric_name = row["metric_name"]
                count = row["cnt"]
                state = self._store.get_signal_state(self._tenant_id, metric_name)
                if state is None:
                    continue

                current_cooldown = state.get("cooldown_seconds", 60.0)
                window = row["last_ts"] - row["first_ts"] if row["last_ts"] and row["first_ts"] else 0
                rate = 0.0
                new_cooldown = current_cooldown

                if window > 0:
                    rate = count / window  # signals per second
                    if rate > (_COOLDOWN_BURST_THRESHOLD / _COOLDOWN_BURST_WINDOW_SEC):
                        # Burst detected — increase cooldown
                        new_cooldown = max(min(
                            current_cooldown * _COOLDOWN_ADJUSTMENT_FACTOR,
                            _COOLDOWN_MAX,
                        ), _COOLDOWN_MIN)
                    elif rate < (1.0 / _COOLDOWN_SPARSE_THRESHOLD_SEC):
                        # Sparse — decrease cooldown
                        new_cooldown = max(min(
                            current_cooldown / _COOLDOWN_ADJUSTMENT_FACTOR,
                            _COOLDOWN_MAX,
                        ), _COOLDOWN_MIN)

                if abs(new_cooldown - current_cooldown) > 0.01:
                    state["cooldown_seconds"] = round(new_cooldown, 2)
                    self._store.persist_signal_state(self._tenant_id, metric_name, state)
                    adjustments.append({
                        "metric_name": metric_name,
                        "parameter": "cooldown_seconds",
                        "old_value": current_cooldown,
                        "new_value": round(new_cooldown, 2),
                        "reason": f"signal_rate={rate:.4f}/sec over {window:.0f}s",
                    })
                    log.info(
                        "Cooldown adjusted for %s: %.1f → %.1f (%s)",
                        metric_name,
                        current_cooldown,
                        new_cooldown,
                        adjustments[-1]["reason"],
                    )

            return adjustments

    def _adjust_lambda(self, metric_name: str) -> dict[str, Any] | None:
        """Adjust lambda threshold for a metric based on rollback/promotion rates."""
        outcomes = self._store.get_outcomes(self._tenant_id, metric_name, limit=100)
        if len(outcomes) < _MIN_OUTCOMES_FOR_ADJUSTMENT:
            return None

        total = len(outcomes)
        promoted = sum(1 for o in outcomes if o["verdict"] == "promoted")
        rolled_back = sum(1 for o in outcomes if o["verdict"] == "rolled_back")

        rollback_rate = rolled_back / total
        promotion_rate = promoted / total

        state = self._store.get_signal_state(self._tenant_id, metric_name)
        if state is None:
            return None

        current_lambda = state.get("lambda_threshold", 4.0)
        new_lambda = current_lambda

        if rollback_rate >= _ROLLBACK_SENSITIVITY_THRESHOLD:
            # Too many rollbacks — make detector less sensitive
            new_lambda = max(min(current_lambda + _LAMBDA_ADJUSTMENT_STEP, _LAMBDA_MAX), _LAMBDA_MIN)
            reason = f"rollback_rate_{int(rollback_rate * 100)}_percent"
        elif promotion_rate >= _PROMOTION_SENSITIVITY_THRESHOLD:
            # Many promotions and few signals — make detector more sensitive
            new_lambda = max(min(current_lambda - _LAMBDA_ADJUSTMENT_STEP, _LAMBDA_MAX), _LAMBDA_MIN)
            reason = f"promotion_rate_{int(promotion_rate * 100)}_percent"
        else:
            return None  # no adjustment needed

        if abs(new_lambda - current_lambda) > 0.01:
            state["lambda_threshold"] = round(new_lambda, 2)
            self._store.persist_signal_state(self._tenant_id, metric_name, state)
            adjustment = {
                "metric_name": metric_name,
                "parameter": "lambda_threshold",
                "old_value": current_lambda,
                "new_value": round(new_lambda, 2),
                "reason": reason,
            }
            log.info(
                "Lambda adjusted for %s: %.2f → %.2f (%s)",
                metric_name,
                current_lambda,
                new_lambda,
                reason,
            )
            return adjustment
        return None

    def _adjust_auto_promote(
        self, metric_name: str, verdict: ExperimentStatus
    ) -> dict[str, Any] | None:
        """Adjust auto-promote threshold per metric category."""
        # Determine category from metric name prefix
        category = metric_name.split(".")[0] if "." in metric_name else "uncategorized"

        outcomes = self._store.get_outcomes(self._tenant_id, None, limit=500)
        if len(outcomes) < _MIN_OUTCOMES_FOR_ADJUSTMENT:
            return None

        # Filter by category prefix
        cat_outcomes = [o for o in outcomes if o["metric_name"].startswith(category + ".")]
        if len(cat_outcomes) < _MIN_OUTCOMES_FOR_ADJUSTMENT:
            return None

        total = len(cat_outcomes)
        promoted = sum(1 for o in cat_outcomes if o["verdict"] == "promoted")
        success_rate = promoted / total

        current_threshold = self._category_auto_promote.get(category, 5)  # default from promotion.py

        if success_rate >= _PROMOTION_SENSITIVITY_THRESHOLD:
            # High success rate — lower the bar (min 2)
            new_threshold = max(current_threshold - 1, 2)
            reason = f"success_rate_{int(success_rate * 100)}_percent"
        elif success_rate <= (1 - _PROMOTION_SENSITIVITY_THRESHOLD):
            # Low success rate — raise the bar (max 10)
            new_threshold = min(current_threshold + 1, 10)
            reason = f"success_rate_{int(success_rate * 100)}_percent"
        else:
            return None

        if new_threshold != current_threshold:
            self._category_auto_promote[category] = new_threshold
            adjustment = {
                "metric_name": metric_name,
                "parameter": "auto_promote_signals",
                "category": category,
                "old_value": current_threshold,
                "new_value": new_threshold,
                "reason": reason,
            }
            log.info(
                "Auto-promote threshold for category %s: %d → %d (%s)",
                category,
                current_threshold,
                new_threshold,
                reason,
            )
            return adjustment
        return None

    def get_category_auto_promote(self, metric_name: str) -> int:
        """Get the auto-promote signal count threshold for a metric's category."""
        category = metric_name.split(".")[0] if "." in metric_name else "uncategorized"
        return self._category_auto_promote.get(category, 5)
