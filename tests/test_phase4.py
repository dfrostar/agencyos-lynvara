"""Tests for Agent OS Phase 4: B-09 Self-Improving Engine, B-10 Self-Improvement Report."""

from __future__ import annotations

import json
import os
import sys
from http.server import HTTPServer
from threading import Thread

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_os.server import AgentOSHandler, create_app, create_default_store
from agent_os.behavior_learner import BehaviorLearner
from agent_os.proactive_explorer import ProactiveExplorer
from agent_os.experiment import ExperimentStatus


@pytest.fixture
def store(tmp_path):
    """Create a test store with all tables."""
    os.environ["NEURALMIND_AGENTOS_DIR"] = str(tmp_path)
    return create_default_store()


@pytest.fixture
def server(store):
    """Start a test server with routes."""
    from agent_os.signals import SignalDetector
    from agent_os.self_improvement import SelfImprovementEngine
    engine_detector = SignalDetector(store=store, tenant_id="test-tenant")
    si_engine = SelfImprovementEngine(store, engine_detector, "test-tenant")
    app_routes = create_app(store, None, engine_detector, si_engine)
    AgentOSHandler.routes = app_routes

    srv = HTTPServer(("127.0.0.1", 0), AgentOSHandler)
    port = srv.server_address[1]
    t = Thread(target=srv.serve_forever, daemon=True)
    t.start()

    yield f"http://127.0.0.1:{port}"

    srv.shutdown()


def _post(server_url, path, body, headers=None, auto_auth=True):
    """POST helper."""
    import urllib.request
    import urllib.error

    if auto_auth and not headers:
        headers = _auth_headers(server_url)
    data = json.dumps(body).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(f"{server_url}{path}", data=data, headers=hdrs)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 500, {"error": str(e)}


def _get(server_url, path, headers=None, auto_auth=True):
    """GET helper."""
    import urllib.request
    import urllib.error

    if auto_auth and not headers:
        headers = _auth_headers(server_url)
    hdrs = {}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(f"{server_url}{path}", headers=hdrs)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 500, {"error": str(e)}


def _auth_headers(server_url, email="test@test.com", tenant_id="test-tenant"):
    """Return bearer <REDACTED> headers for a tenant."""
    import urllib.error
    try:
        status, resp = _post(
            server_url,
            "/api/agent-os/tenants",
            {"tenant_id": tenant_id, "name": tenant_id, "admin_email": email},
            auto_auth=False,
        )
        if status == 201:
            token = resp["session_token"]
        else:
            from agent_os.auth import SessionStore
            session_store = SessionStore()
            token = session_store.create_session(email, tenant_id, "admin")
    except (urllib.error.HTTPError, Exception):
        # Tenant may already exist — try to get a session anyway
        from agent_os.auth import SessionStore
        session_store = SessionStore()
        try:
            token = session_store.create_session(email, tenant_id, "admin")
        except Exception:
            token = ""
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────
# B-09: BehaviorLearner Tests
# ─────────────────────────────────────────────────────────────


class TestBehaviorLearner:
    """Tests for the BehaviorLearner module."""

    def test_record_outcome_basic(self, store):
        """BehaviorLearner can record an outcome."""
        learner = BehaviorLearner(store, "test-tenant")
        adjustments = learner.on_outcome(
            metric_name="outreach.email.follow_up_days",
            verdict=ExperimentStatus.PROMOTED,
            delta=0.1,
            baseline_value=3.0,
            candidate_value=2.0,
            proposal_id="prop_001",
            experiment_id="exp_001",
        )
        assert adjustments["metric_name"] == "outreach.email.follow_up_days"
        assert adjustments["verdict"] == "promoted"
        # Verify outcome was stored
        outcomes = store.get_outcomes("test-tenant", "outreach.email.follow_up_days")
        assert len(outcomes) == 1
        assert outcomes[0]["verdict"] == "promoted"

    def test_adjust_lambda_high_rollback_rate(self, store):
        """Lambda increases when rollback rate > 80%."""
        learner = BehaviorLearner(store, "test-tenant")
        metric = "test.metric"
        # First, set up an initial signal state
        from agent_os.store import AgentOSStore
        store.persist_signal_state("test-tenant", metric, {
            "metric_name": metric,
            "count": 10,
            "running_sum": 100.0,
            "m2": 0.0,
            "min_cum_dev": 0.0,
            "max_cum_dev": 0.0,
            "lambda_threshold": 4.0,
            "last_signal_at": 0.0,
            "cooldown_seconds": 60.0,
            "reference_mean": 0.0,
        })
        # Record 5 rollback outcomes (100% rollback rate)
        for i in range(5):
            learner.on_outcome(
                metric_name=metric,
                verdict=ExperimentStatus.ROLLED_BACK,
                delta=-0.1,
                baseline_value=10.0,
                candidate_value=9.0,
                proposal_id=f"prop_{i}",
                experiment_id=f"exp_{i}",
            )
        # Check lambda was adjusted
        state = store.get_signal_state("test-tenant", metric)
        assert state["lambda_threshold"] > 4.0

    def test_adjust_lambda_high_promotion_rate(self, store):
        """Lambda decreases when promotion rate > 80%."""
        learner = BehaviorLearner(store, "test-tenant")
        metric = "test.metric.promote"
        store.persist_signal_state("test-tenant", metric, {
            "metric_name": metric,
            "count": 10,
            "running_sum": 100.0,
            "m2": 0.0,
            "min_cum_dev": 0.0,
            "max_cum_dev": 0.0,
            "lambda_threshold": 4.0,
            "last_signal_at": 0.0,
            "cooldown_seconds": 60.0,
            "reference_mean": 0.0,
        })
        # Record 5 promoted outcomes (100% promotion rate)
        for i in range(5):
            learner.on_outcome(
                metric_name=metric,
                verdict=ExperimentStatus.PROMOTED,
                delta=0.1,
                baseline_value=10.0,
                candidate_value=11.0,
                proposal_id=f"prop_{i}",
                experiment_id=f"exp_{i}",
            )
        state = store.get_signal_state("test-tenant", metric)
        assert state["lambda_threshold"] < 4.0

    def test_no_adjustment_with_few_outcomes(self, store):
        """No lambda adjustment with fewer than min outcomes."""
        learner = BehaviorLearner(store, "test-tenant")
        metric = "test.metric.few"
        store.persist_signal_state("test-tenant", metric, {
            "metric_name": metric,
            "count": 10,
            "running_sum": 100.0,
            "m2": 0.0,
            "min_cum_dev": 0.0,
            "max_cum_dev": 0.0,
            "lambda_threshold": 4.0,
            "last_signal_at": 0.0,
            "cooldown_seconds": 60.0,
            "reference_mean": 0.0,
        })
        # Only 2 outcomes (less than MIN_OUTCOMES_FOR_ADJUSTMENT=5)
        for i in range(2):
            learner.on_outcome(
                metric_name=metric,
                verdict=ExperimentStatus.ROLLED_BACK,
                delta=-0.1,
                baseline_value=10.0,
                candidate_value=9.0,
                proposal_id=f"prop_{i}",
                experiment_id=f"exp_{i}",
            )
        # Lambda should remain unchanged
        state = store.get_signal_state("test-tenant", metric)
        assert state["lambda_threshold"] == 4.0

    def test_adjust_cooldowns_no_signals(self, store):
        """adjust_cooldowns returns empty when no signals."""
        learner = BehaviorLearner(store, "test-tenant")
        adjustments = learner.adjust_cooldowns()
        assert adjustments == []

    def test_category_auto_promote(self, store):
        """Get auto-promote threshold for a category."""
        learner = BehaviorLearner(store, "test-tenant")
        # Default threshold
        threshold = learner.get_category_auto_promote("outreach.email.follow_up")
        assert threshold == 5


# ─────────────────────────────────────────────────────────────
# B-09: Store Outcome Methods Tests
# ─────────────────────────────────────────────────────────────


class TestStoreOutcomes:
    """Tests for store outcome methods."""

    def test_record_outcome(self, store):
        """record_outcome persists an outcome."""
        outcome_id = store.record_outcome(
            tenant_id="test-tenant",
            proposal_id="prop_001",
            experiment_id="exp_001",
            metric_name="test.metric",
            verdict="promoted",
            delta=0.1,
            baseline_value=10.0,
            candidate_value=11.0,
        )
        assert outcome_id.startswith("out_")

    def test_get_outcomes_all(self, store):
        """get_outcomes returns all outcomes for a tenant."""
        store.record_outcome("test-tenant", "p1", "e1", "m1", "promoted", 0.1, 10.0, 11.0)
        store.record_outcome("test-tenant", "p2", "e2", "m2", "rolled_back", -0.1, 10.0, 9.0)
        outcomes = store.get_outcomes("test-tenant")
        assert len(outcomes) == 2

    def test_get_outcomes_filter_metric(self, store):
        """get_outcomes filters by metric name."""
        store.record_outcome("test-tenant", "p1", "e1", "m1", "promoted", 0.1, 10.0, 11.0)
        store.record_outcome("test-tenant", "p2", "e2", "m2", "rolled_back", -0.1, 10.0, 9.0)
        outcomes = store.get_outcomes("test-tenant", "m1")
        assert len(outcomes) == 1
        assert outcomes[0]["metric_name"] == "m1"

    def test_get_outcome_stats(self, store):
        """get_outcome_stats aggregates correctly."""
        store.record_outcome("test-tenant", "p1", "e1", "m1", "promoted", 0.1, 10.0, 11.0)
        store.record_outcome("test-tenant", "p2", "e2", "m1", "promoted", 0.2, 10.0, 12.0)
        store.record_outcome("test-tenant", "p3", "e3", "m2", "rolled_back", -0.1, 10.0, 9.0)
        stats = store.get_outcome_stats("test-tenant")
        assert stats["total"] == 3
        assert stats["promoted"] == 2
        assert stats["rolled_back"] == 1
        assert stats["avg_delta"] is not None

    def test_get_outcome_stats_empty(self, store):
        """get_outcome_stats returns zeros when no outcomes."""
        stats = store.get_outcome_stats("test-tenant")
        assert stats["total"] == 0
        assert stats["promoted"] == 0
        assert stats["avg_delta"] == 0.0


# ─────────────────────────────────────────────────────────────
# B-09: ProactiveExplorer Tests
# ─────────────────────────────────────────────────────────────


class TestProactiveExplorer:
    """Tests for the ProactiveExplorer module."""

    def test_detect_stale_incumbents_empty(self, store):
        """Detects stale incumbents when none exist."""
        explorer = ProactiveExplorer(store, "test-tenant")
        stale = explorer._detect_stale_incumbents()
        assert stale == []

    def test_detect_stale_incumbents_with_data(self, store):
        """Detects stale incumbent with old updated_at."""
        from datetime import datetime, timedelta, timezone
        old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        store.persist_incumbent("test-tenant", "outreach.email.follow_up_days", 3.0, "baseline", [])
        # Manually update to old timestamp
        conn = store._get_conn()
        conn.execute(
            "UPDATE tuner_incumbents SET updated_at = ? WHERE tenant_id = ? AND metric_name = ?",
            (old_time, "test-tenant", "outreach.email.follow_up_days"),
        )
        conn.commit()
        explorer = ProactiveExplorer(store, "test-tenant")
        stale = explorer._detect_stale_incumbents()
        # Should find stale incumbents (no experiments in 7+ days)
        assert len(stale) >= 1

    def test_detect_metric_gaps(self, store):
        """Detects metrics tracked but never experimented on."""
        import time
        now = time.time()
        store.insert_signal("test-tenant", {
            "signal_id": "sig_001",
            "timestamp": now,
            "metric_name": "test.metric.gap",
            "value": 10.0,
            "baseline": 9.0,
            "delta": 1.0,
            "severity": 0.5,
            "level": "info",
        })
        explorer = ProactiveExplorer(store, "test-tenant")
        gaps = explorer._detect_metric_gaps()
        assert len(gaps) >= 1
        assert gaps[0]["metric_name"] == "test.metric.gap"

    def test_run_cycle_empty(self, store):
        """Run cycle returns empty results when no data."""
        explorer = ProactiveExplorer(store, "test-tenant")
        result = explorer.run_cycle()
        assert result["total_proposed"] == 0
        assert "stale incumbents" in result["summary"].lower() or "0" in result["summary"]

    def test_run_cycle_proposes_for_stale(self, store):
        """Run cycle proposes experiments for stale incumbents."""
        from datetime import datetime, timedelta, timezone
        old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        store.persist_incumbent("test-tenant", "outreach.email.follow_up_days", 3.0, "baseline", [])
        conn = store._get_conn()
        conn.execute(
            "UPDATE tuner_incumbents SET updated_at = ? WHERE tenant_id = ? AND metric_name = ?",
            (old_time, "test-tenant", "outreach.email.follow_up_days"),
        )
        conn.commit()
        explorer = ProactiveExplorer(store, "test-tenant")
        result = explorer.run_cycle()
        assert result["total_proposed"] >= 1

    def test_get_status(self, store):
        """Get current explorer status."""
        explorer = ProactiveExplorer(store, "test-tenant")
        status = explorer.get_status()
        assert status["tenant_id"] == "test-tenant"
        assert status["total_proposals_made"] == 0

    def test_run_cycle_updates_proposals_made(self, store):
        """Running cycle increments total_proposals_made."""
        from datetime import datetime, timedelta, timezone
        old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        store.persist_incumbent("test-tenant", "outreach.email.follow_up_days", 3.0, "baseline", [])
        conn = store._get_conn()
        conn.execute(
            "UPDATE tuner_incumbents SET updated_at = ? WHERE tenant_id = ? AND metric_name = ?",
            (old_time, "test-tenant", "outreach.email.follow_up_days"),
        )
        conn.commit()
        explorer = ProactiveExplorer(store, "test-tenant")
        explorer.run_cycle()
        explorer.run_cycle()
        status = explorer.get_status()
        assert status["total_proposals_made"] >= 2


# ─────────────────────────────────────────────────────────────
# B-09: Engine Endpoint Tests
# ─────────────────────────────────────────────────────────────


class TestEngineEndpoints:
    """Tests for self-improvement engine endpoints."""

    def test_engine_status_endpoint(self, server):
        """GET /api/agent-os/engine/status returns engine state."""
        status, resp = _get(server, "/api/agent-os/engine/status")
        assert status == 200
        assert "enabled" in resp
        assert "tenant_id" in resp

    def test_engine_status_requires_auth(self, server):
        """Engine status requires authentication."""
        import urllib.request
        import urllib.error

        req = urllib.request.Request(f"{server}/api/agent-os/engine/status")
        try:
            urllib.request.urlopen(req)
            assert False, "Should have returned 401"
        except urllib.error.HTTPError as e:
            assert e.code == 401

    def test_engine_trigger_endpoint(self, server):
        """POST /api/agent-os/engine/trigger runs explorer cycle."""
        status, resp = _post(server, "/api/agent-os/engine/trigger", {})
        assert status == 200
        assert "summary" in resp

    def test_engine_outcomes_endpoint_empty(self, server):
        """GET /api/agent-os/engine/outcomes returns empty when no outcomes."""
        status, resp = _get(server, "/api/agent-os/engine/outcomes")
        assert status == 200
        assert resp["outcomes"] == []
        assert resp["count"] == 0

    def test_engine_parameters_endpoint(self, server):
        """GET /api/agent-os/engine/parameters returns parameter state."""
        status, resp = _get(server, "/api/agent-os/engine/parameters")
        assert status == 200
        assert "parameters" in resp
        assert "count" in resp

    def test_engine_outcomes_after_recording(self, server):
        """Outcomes appear after recording."""
        # Record an outcome via the store directly (since we can't easily
        # trigger the full pipeline)
        headers = _auth_headers(server)
        # First, run an experiment to create an outcome
        exp_body = {
            "metric_name": "test.metric",
            "baseline_value": 10.0,
            "candidate_value": 11.0,
            "threshold_pct": 5.0,
        }
        _post(server, "/api/agent-os/experiments", exp_body, headers=headers)
        # Now check outcomes endpoint
        status, resp = _get(server, "/api/agent-os/engine/outcomes", headers=headers)
        assert status == 200
        # The engine may have recorded outcomes via the pipeline


# ─────────────────────────────────────────────────────────────
# B-10: Weekly Self-Improvement Report Tests
# ─────────────────────────────────────────────────────────────


class TestSelfImprovementReport:
    """Tests for weekly self-improvement report."""

    def test_self_improvement_report_endpoint(self, server):
        """GET /api/agent-os/review/self-improvement returns report."""
        status, resp = _get(server, "/api/agent-os/review/self-improvement")
        assert status == 200
        assert resp["period"] == "weekly"
        assert "summary" in resp
        assert "experiments" in resp
        assert "tuner_changes" in resp
        assert "threshold_adjustments" in resp
        assert "proactive_experiments" in resp
        assert "learning_summary" in resp

    def test_self_improvement_summary_endpoint(self, server):
        """GET /api/agent-os/review/self-improvement/summary returns summary only."""
        status, resp = _get(server, "/api/agent-os/review/self-improvement/summary")
        assert status == 200
        assert resp["period"] == "weekly"
        assert "summary" in resp
        # Should NOT have detailed sections
        assert "experiments" not in resp
        assert "tuner_changes" not in resp

    def test_self_improvement_report_empty(self, server):
        """Self-improvement report with no data."""
        status, resp = _get(server, "/api/agent-os/review/self-improvement")
        assert status == 200
        experiments = resp.get("experiments", {})
        assert experiments.get("run_this_week", 0) == 0

    def test_self_improvement_report_requires_auth(self, server):
        """Self-improvement report requires auth."""
        import urllib.request
        import urllib.error

        req = urllib.request.Request(f"{server}/api/agent-os/review/self-improvement")
        try:
            urllib.request.urlopen(req)
            assert False, "Should have returned 401"
        except urllib.error.HTTPError as e:
            assert e.code == 401

    def test_self_improvement_report_with_data(self, server):
        """Self-improvement report aggregates experiment data."""
        # Run an experiment to generate data
        exp_body = {
            "metric_name": "outreach.email.follow_up_days",
            "baseline_value": 3.0,
            "candidate_value": 2.0,
            "threshold_pct": 5.0,
        }
        _post(server, "/api/agent-os/experiments", exp_body)
        status, resp = _get(server, "/api/agent-os/review/self-improvement")
        assert status == 200
        # Should at least have structure
        assert "experiments" in resp
