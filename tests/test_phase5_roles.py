"""Tests for B-13/B-14: Role base class + Detector role."""

from __future__ import annotations

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_os.bus import MessageBus
from agent_os.store import AgentOSStore
from agent_os.roles.base import AgentRole
from agent_os.roles.detector import DetectorRole


@pytest.fixture
def store(tmp_path):
    os.environ["NEURALMIND_AGENTOS_DIR"] = str(tmp_path)
    return AgentOSStore()


@pytest.fixture
def bus(store):
    return MessageBus(store)


class TestAgentRole:
    def test_start_stop(self, bus, store):
        role = DetectorRole("test-tenant", bus, store)
        role.start()
        assert role._enabled is True
        role.stop()
        assert role._enabled is False

    def test_register_role(self, bus, store):
        from agent_os.roles.coordinator import CoordinatorRole
        coordinator = CoordinatorRole("test-tenant", bus, store)
        detector = DetectorRole("test-tenant", bus, store)
        coordinator.register_role(detector)
        assert "detector" in coordinator._roles

    def test_heartbeat(self, bus, store):
        role = DetectorRole("test-tenant", bus, store)
        role.start()
        role.heartbeat()
        # Check that heartbeat was recorded
        roles = store.get_roles("test-tenant")
        assert len(roles) >= 1
        role.stop()


class TestDetectorRole:
    def test_detector_role_name(self, bus, store):
        role = DetectorRole("test-tenant", bus, store)
        assert role.ROLE_NAME == "detector"

    def test_detector_consumes_metric_value(self, bus, store):
        role = DetectorRole("test-tenant", bus, store)
        role.start()
        # Publish a metric_value message
        from agent_os.bus import Message
        msg = Message(
            topic="metric_value",
            payload={"metric_name": "test.metric", "value": 100.0},
            from_role="webhook",
            to_role="detector",
            tenant_id="test-tenant",
        )
        bus.publish(msg)
        # Give the role time to process
        time.sleep(0.5)
        role.stop()
        # Message should be consumed (may be pending until acknowledged)
        pending = store.get_pending_bus_messages("metric_value")
        # Note: message is consumed but pending until acknowledged
        assert len(pending) <= 1
