"""self_improvement.py — Self-improvement engine server wiring and endpoints.

B-09: Wires AutoTriggerLoop + BehaviorLearner + ProactiveExplorer
into the server. Adds 4 new endpoints:
- GET /api/agent-os/engine/status
- POST /api/agent-os/engine/trigger
- GET /api/agent-os/engine/outcomes
- GET /api/agent-os/engine/parameters
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from .auth import AuthContext, SessionStore, extract_bearer_token
from .auto_trigger import AutoTriggerLoop
from .behavior_learner import BehaviorLearner
from .proactive_explorer import ProactiveExplorer
from .signals import SignalDetector

log = logging.getLogger(__name__)


class SelfImprovementEngine:
    """Orchestrates the self-improving engine components.

    Wires together:
    - AutoTriggerLoop (signal → proposal → experiment)
    - BehaviorLearner (outcome → parameter adjustment)
    - ProactiveExplorer (gap detection → experiment proposal)

    Runs BehaviorLearner and ProactiveExplorer as background threads.
    AutoTriggerLoop is event-driven (triggered by signal fires on the detector).
    """

    def __init__(
        self,
        store: Any,
        signal_detector: SignalDetector,
        tenant_id: str = "default",
    ) -> None:
        self._store = store
        self._tenant_id = tenant_id
        self._signal_detector = signal_detector
        self._behavior_learner = BehaviorLearner(store, tenant_id)
        self._proactive_explorer = ProactiveExplorer(store, tenant_id)
        self._auto_trigger: AutoTriggerLoop | None = None
        self._enabled = False
        self._last_behavior_run: str | None = None
        self._last_explorer_run: str | None = None
        self._behavior_interval = 3600  # run behavior learner every hour
        self._explorer_interval = 86400  # run explorer daily

        self._wire_auto_trigger()

    def _wire_auto_trigger(self) -> None:
        """Wire AutoTriggerLoop to the signal detector with outcome recording."""
        # Adapter: OutcomeCallback(tenant_id, ExperimentResult) → BehaviorLearner.on_outcome(...)
        def _on_outcome(tenant_id: str, result: Any) -> None:
            self._behavior_learner.on_outcome(
                metric_name=result.metric_name,
                verdict=result.verdict,
                delta=result.delta,
                baseline_value=result.baseline_value,
                candidate_value=result.candidate_value,
                proposal_id=result.proposal_id,
                experiment_id=result.experiment_id,
            )

        self._auto_trigger = AutoTriggerLoop(
            signal_detector=self._signal_detector,
            store=self._store,
            tenant_id=self._tenant_id,
            outcome_recorder=_on_outcome,
        )

    def start(self) -> None:
        """Start background threads."""
        if self._enabled:
            return
        self._enabled = True

        # Start behavior learner background thread
        self._behavior_thread = threading.Thread(
            target=self._behavior_loop,
            daemon=True,
            name="behavior-learner",
        )
        self._behavior_thread.start()

        # Start proactive explorer background thread
        self._explorer_thread = threading.Thread(
            target=self._explorer_loop,
            daemon=True,
            name="proactive-explorer",
        )
        self._explorer_thread.start()

        log.info("Self-improvement engine started")

    def stop(self) -> None:
        """Stop background threads."""
        self._enabled = False

    def get_status(self) -> dict[str, Any]:
        """Get current engine status."""
        return {
            "enabled": self._enabled,
            "tenant_id": self._tenant_id,
            "last_behavior_run": self._last_behavior_run,
            "last_explorer_run": self._last_explorer_run,
            "behavior_interval": self._behavior_interval,
            "explorer_interval": self._explorer_interval,
            "explorer_status": self._proactive_explorer.get_status(),
        }

    def trigger_explorer(self) -> dict[str, Any]:
        """Manually trigger a proactive exploration cycle."""
        return self._proactive_explorer.run_cycle()

    def _behavior_loop(self) -> None:
        """Background loop for behavior learning (cooldown adjustments)."""
        import time
        while self._enabled:
            try:
                adjustments = self._behavior_learner.adjust_cooldowns()
                self._last_behavior_run = datetime.now(timezone.utc).isoformat()
                if adjustments:
                    log.info("Behavior learner made %d cooldown adjustments", len(adjustments))
            except Exception:
                log.exception("Behavior learner error")
            time.sleep(self._behavior_interval)

    def _explorer_loop(self) -> None:
        """Background loop for proactive exploration."""
        import time
        while self._enabled:
            try:
                result = self._proactive_explorer.run_cycle()
                self._last_explorer_run = datetime.now(timezone.utc).isoformat()
                log.info("Proactive explorer: %s", result.get("summary", ""))
            except Exception:
                log.exception("Proactive explorer error")
            time.sleep(self._explorer_interval)


def create_self_improvement_routes(
    store: Any,
    engine: SelfImprovementEngine,
    session_store: SessionStore | None = None,
    get_auth: Callable[[dict[str, Any] | None], AuthContext] | None = None,
) -> dict[tuple[str, str], Callable]:
    """Create self-improvement engine routes."""
    _session_store = session_store or SessionStore()

    def _resolve_auth(body: Any, headers: dict[str, str] | None) -> AuthContext:
        if headers:
            token = extract_bearer_token(headers.get("Authorization"))
            if token:
                session = _session_store.get_session(token)
                if session:
                    return session
        return get_auth(body) if get_auth else AuthContext(email="", tenant_id=None)

    def _resolve_tenant_id(
        body: dict[str, Any] | None, headers: dict[str, str] | None
    ) -> tuple[AuthContext, str | None]:
        auth = _resolve_auth(body, headers)
        if not auth.is_authenticated:
            return auth, None
        if auth.tenant_id is None:
            return AuthContext(email="", tenant_id=None), None  # treat as unauthenticated
        return auth, auth.tenant_id

    def get_engine_status(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/engine/status"""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return 401, {"error": "authentication required"}
            return 200, engine.get_status()
        except Exception as e:
            log.exception("Failed to get engine status")
            return 500, {"error": str(e)}

    def trigger_engine(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """POST /api/agent-os/engine/trigger — manually trigger explorer."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return 401, {"error": "authentication required"}
            result = engine.trigger_explorer()
            return 200, result
        except Exception as e:
            log.exception("Failed to trigger engine")
            return 500, {"error": str(e)}

    def get_outcomes(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/engine/outcomes — recent outcomes."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return 401, {"error": "authentication required"}
            metric_name = (body or {}).get("metric_name") or None
            limit = int((body or {}).get("limit", 100))
            outcomes = store.get_outcomes(tenant_id, metric_name, limit)
            stats = store.get_outcome_stats(tenant_id)
            return 200, {"outcomes": outcomes, "stats": stats, "count": len(outcomes)}
        except Exception as e:
            log.exception("Failed to get outcomes")
            return 500, {"error": str(e)}

    def get_parameters(
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
        **path_params: str,
    ) -> tuple[int, dict[str, Any]]:
        """GET /api/agent-os/engine/parameters — current per-metric thresholds."""
        try:
            auth, tenant_id = _resolve_tenant_id(body, headers)
            if not auth.is_authenticated:
                return 401, {"error": "authentication required"}
            states = store.get_all_signal_states(tenant_id)
            return 200, {
                "parameters": states,
                "count": len(states),
                "auto_promote_overrides": engine._behavior_learner._category_auto_promote,
            }
        except Exception as e:
            log.exception("Failed to get parameters")
            return 500, {"error": str(e)}

    return {
        ("GET", "/api/agent-os/engine/status"): get_engine_status,
        ("POST", "/api/agent-os/engine/trigger"): trigger_engine,
        ("GET", "/api/agent-os/engine/outcomes"): get_outcomes,
        ("GET", "/api/agent-os/engine/parameters"): get_parameters,
    }
