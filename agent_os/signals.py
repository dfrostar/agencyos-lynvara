"""signals.py — Page-Hinkley anomaly detection for Agent OS metrics streams.

Detects small persistent shifts in metrics without fixed thresholds.
Emits Signal records when anomalies are detected.

Design:
    - Page-Hinkley test: tracks cumulative sum of deviations from a FIXED
      reference mean (set after initial burn-in period of MIN_SAMPLES_BEFORE_ALERT
      samples). The reference mean is reset after each signal fires.
    - When cumulative deviation exceeds a threshold (lambda) times the
      standard deviation, a signal fires.
    - Lambda scales with data volatility — fixed thresholds miss
      small persistent shifts and fire on seasonal variance.
    - Signals have severity based on deviation magnitude.
    - Per-metric state is persisted to SQLite (crash-safe, thread-safe).
    - push() is the primary entry point: it auto-generates a correlator
      insight when a signal fires, enabling the signal → diagnose →
      experiment → promote/rollback loop.
"""

from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .correlator import Insight, RootCauseCorrelator

log = logging.getLogger(__name__)

# Minimum samples required before Page-Hinkley can fire.
MIN_SAMPLES_BEFORE_ALERT = 10


class SeverityLevel(str, Enum):
    """Signal severity levels."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_SEVERITY_THRESHOLDS = {
    0.5: SeverityLevel.INFO,
    1.0: SeverityLevel.LOW,
    2.0: SeverityLevel.MEDIUM,
    4.0: SeverityLevel.HIGH,
    8.0: SeverityLevel.CRITICAL,
}


@dataclass
class Signal:
    """An anomaly signal detected in a metric stream."""

    signal_id: str
    timestamp: float
    metric_name: str
    value: float
    baseline: float
    delta: float
    severity: float
    level: SeverityLevel = SeverityLevel.INFO
    acknowledged: bool = False
    tenant_id: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp,
            "metric_name": self.metric_name,
            "value": round(self.value, 6),
            "baseline": round(self.baseline, 6),
            "delta": round(self.delta, 6),
            "severity": round(self.severity, 3),
            "level": self.level.value,
            "acknowledged": self.acknowledged,
        }


@dataclass
class _PageHinkleyState:
    """Internal state for a single metric's Page-Hinkley test."""

    metric_name: str
    count: int = 0
    running_sum: float = 0.0
    m2: float = 0.0
    min_cum_dev: float = 0.0
    max_cum_dev: float = 0.0
    lambda_threshold: float = 4.0
    last_signal_at: float = 0.0
    cooldown_seconds: float = 60.0
    _reference_mean: float = 0.0

    @property
    def running_mean(self) -> float:
        return self.running_sum / max(self.count, 1)

    @property
    def running_std(self) -> float:
        if self.count < 2:
            return 0.0
        variance = self.m2 / self.count
        return math.sqrt(max(variance, 0.0))

    @property
    def cumulative_deviation(self) -> float:
        return self.max_cum_dev - self.min_cum_dev

    def _severity_level(self) -> SeverityLevel:
        ratio = self.severity_ratio
        assigned = SeverityLevel.INFO
        for threshold, level in sorted(_SEVERITY_THRESHOLDS.items()):
            if ratio >= threshold:
                assigned = level
        return assigned

    @property
    def severity_ratio(self) -> float:
        std = self.running_std
        if std < 1e-9:
            return 0.0
        return self.cumulative_deviation / std

    def update(self, value: float) -> Signal | None:
        """Update state with a new metric value.

        Page-Hinkley tracks cumulative deviation from a FIXED reference
        mean (set after MIN_SAMPLES_BEFORE_ALERT), not a running mean.
        Using a running mean would cause the detector to track the data
        and never accumulate enough deviation to fire.
        """
        self.count += 1

        # Welford's online algorithm for mean/variance using PRE-update mean
        delta = value - self.running_mean
        self.running_sum += value
        delta2 = value - self.running_mean
        self.m2 += delta * delta2

        # Reference mean: frozen after initial burn-in period.
        # Capture it on the last burn-in sample so it represents the
        # pre-shift baseline, not a value already influenced by the shift.
        if self.count == MIN_SAMPLES_BEFORE_ALERT:
            self._reference_mean = self.running_mean
            self.max_cum_dev = 0.0
            self.min_cum_dev = 0.0
            return None

        if self.count < MIN_SAMPLES_BEFORE_ALERT:
            # Still accumulating burn-in samples
            self.max_cum_dev = 0.0
            self.min_cum_dev = 0.0
            return None

        # If reference mean still 0.0 (e.g., all values were 0), use running_mean
        reference = self._reference_mean if self._reference_mean != 0.0 else self.running_mean
        deviation = value - reference
        self.max_cum_dev = max(self.max_cum_dev + deviation, 0.0)
        self.min_cum_dev = min(self.min_cum_dev + deviation, 0.0)

        std = self.running_std
        severity = self.severity_ratio
        now = time.time()

        if (
            severity >= self.lambda_threshold
            and std > 1e-9
            and self.count >= MIN_SAMPLES_BEFORE_ALERT
        ):
            if now - self.last_signal_at < self.cooldown_seconds:
                return None
            self.last_signal_at = now
            level = self._severity_level()
            signal = Signal(
                signal_id=f"sig_{self.metric_name}_{int(now * 1000)}_{uuid.uuid4().hex[:6]}",
                timestamp=now,
                metric_name=self.metric_name,
                value=value,
                baseline=self._reference_mean,
                delta=deviation,
                severity=severity,
                level=level,
            )
            self.max_cum_dev = 0.0
            self.min_cum_dev = 0.0
            # Reset reference mean after signal so next window starts fresh
            self._reference_mean = self.running_mean
            return signal

        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "count": self.count,
            "running_sum": self.running_sum,
            "m2": self.m2,
            "min_cum_dev": self.min_cum_dev,
            "max_cum_dev": self.max_cum_dev,
            "lambda_threshold": self.lambda_threshold,
            "last_signal_at": self.last_signal_at,
            "cooldown_seconds": self.cooldown_seconds,
            "reference_mean": self._reference_mean,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> _PageHinkleyState:
        return cls(
            metric_name=data["metric_name"],
            count=data.get("count", 0),
            running_sum=data.get("running_sum", 0.0),
            m2=data.get("m2", 0.0),
            min_cum_dev=data.get("min_cum_dev", 0.0),
            max_cum_dev=data.get("max_cum_dev", 0.0),
            lambda_threshold=data.get("lambda_threshold", 4.0),
            last_signal_at=data.get("last_signal_at", 0.0),
            cooldown_seconds=data.get("cooldown_seconds", 60.0),
            _reference_mean=data.get("reference_mean", 0.0),
        )


class SignalDetector:
    """Multi-metric Page-Hinkley anomaly detector with persistent state.

    Thread-safe: all public methods acquire a reentrant lock.
    State is persisted to SQLite after every push().
    """

    @dataclass
    class PushResult:
        signal: Signal | None
        insight: Insight | None

        def to_dict(self) -> dict[str, Any]:
            return {
                "signal": self.signal.to_dict() if self.signal else None,
                "insight": self.insight.to_dict() if self.insight else None,
            }

    def __init__(
        self,
        lambda_threshold: float = 4.0,
        cooldown_seconds: float = 60.0,
        correlator: RootCauseCorrelator | None = None,
        auto_trigger: Callable[[Signal, Insight], None] | None = None,
        store: Any = None,
        tenant_id: str = "default",
    ) -> None:
        self._lambda_threshold = lambda_threshold
        self._cooldown_seconds = cooldown_seconds
        self._state: dict[str, _PageHinkleyState] = {}
        self._correlator = correlator
        self._auto_trigger = auto_trigger
        self._store = store
        self._tenant_id = tenant_id
        self._lock = threading.RLock()
        self._last_persist_ts: dict[str, float] = {}

        # Load persisted state from store
        if store is not None:
            self._load_state()

    PERSIST_DEBOUNCE_SECONDS: float = 1.0

    def _load_state(self) -> None:
        """Load persisted signal states from store."""
        if self._store is None:
            return
        states = self._store.get_all_signal_states(self._tenant_id)
        for metric_name, state_dict in states.items():
            self._state[metric_name] = _PageHinkleyState.from_dict(state_dict)

    def _get_state(self, metric_name: str) -> _PageHinkleyState:
        if metric_name not in self._state:
            self._state[metric_name] = _PageHinkleyState(
                metric_name=metric_name,
                lambda_threshold=self._lambda_threshold,
                cooldown_seconds=self._cooldown_seconds,
            )
        return self._state[metric_name]

    def _persist_state(self, metric_name: str, force: bool = False) -> None:
        """Persist a metric's Page-Hinkley state to the store.

        When force=False (default), only persists if the last persistence
        was more than PERSIST_DEBOUNCE_SECONDS ago. This avoids SQLite
        write amplification on high-frequency metric streams.
        """
        if self._store is None:
            return
        now = time.time()
        if not force:
            last = self._last_persist_ts.get(metric_name, 0.0)
            if now - last < self.PERSIST_DEBOUNCE_SECONDS:
                return
        self._last_persist_ts[metric_name] = now
        state = self._state.get(metric_name)
        if state is not None:
            self._store.persist_signal_state(self._tenant_id, metric_name, state.to_dict())

    def update(self, metric_name: str, value: float) -> Signal | None:
        """Update a metric value. Returns Signal if anomaly detected."""
        with self._lock:
            state = self._get_state(metric_name)
            signal = state.update(float(value))
            # Persist state (debounced — see _persist_state)
            self._persist_state(metric_name, force=signal is not None)
            return signal

    def push(
        self,
        metric_name: str,
        value: float,
        project_path: str | Path | None = None,
        tenant_id: str | None = None,
    ) -> PushResult:
        """Push a metric value and auto-correlate if a signal fires.

        `tenant_id` overrides the detector's default tenant so a shared
        detector can route signals/proposals to the correct tenant.
        """
        tenant = tenant_id or self._tenant_id
        with self._lock:
            signal = self.update(metric_name, value)

            if signal is None:
                return self.PushResult(signal=None, insight=None)

            # Tag the signal with the owning tenant
            signal.tenant_id = tenant

            # Persist the signal record
            if self._store is not None:
                self._store.insert_signal(tenant, signal.to_dict())

            # Auto-generate insight if correlator is configured
            insight = None
            if self._correlator is not None and project_path is not None:
                try:
                    insight = self._correlator.correlate(signal, project_path)
                    if self._store is not None and insight is not None:
                        self._store.insert_insight(tenant, insight.to_dict())
                except Exception as exc:
                    log.warning(
                        "Correlator failed for signal %s: %s",
                        signal.signal_id,
                        exc,
                    )

            # Fire auto-trigger callback if configured
            if insight is not None and self._auto_trigger is not None:
                try:
                    self._auto_trigger(signal, insight)
                except Exception as exc:
                    log.warning(
                        "Auto-trigger callback failed for signal %s: %s",
                        signal.signal_id,
                        exc,
                    )

            return self.PushResult(signal=signal, insight=insight)

    def update_batch(self, metrics: dict[str, float]) -> list[Signal]:
        """Update multiple metrics. Returns list of new signals."""
        signals = []
        with self._lock:
            for name, value in metrics.items():
                signal = self.update(name, value)
                if signal:
                    signals.append(signal)
        return signals

    def get_stats(self, metric_name: str) -> dict[str, float] | None:
        with self._lock:
            state = self._state.get(metric_name)
            if state is None:
                return None
            return {
                "count": state.count,
                "running_mean": state.running_mean,
                "running_std": state.running_std,
                "cumulative_deviation": state.cumulative_deviation,
                "severity_ratio": state.severity_ratio,
            }

    def list_metrics(self) -> list[str]:
        with self._lock:
            return list(self._state.keys())

    def reset(self, metric_name: str | None = None) -> None:
        with self._lock:
            if metric_name:
                self._state.pop(metric_name, None)
            else:
                self._state.clear()
