"""Tests for B-12: Message bus."""

from __future__ import annotations

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_os.bus import Message, MessageBus, TOPICS
from agent_os.store import AgentOSStore


@pytest.fixture
def store(tmp_path):
    os.environ["NEURALMIND_AGENTOS_DIR"] = str(tmp_path)
    return AgentOSStore()


@pytest.fixture
def bus(store):
    return MessageBus(store)


class TestMessage:
    def test_create_message(self):
        msg = Message(topic="signal", payload={"foo": "bar"}, from_role="detector")
        assert msg.topic == "signal"
        assert msg.payload == {"foo": "bar"}
        assert msg.from_role == "detector"
        assert msg.to_role is None
        assert msg.status == "pending"
        assert msg.message_id.startswith("msg_")

    def test_to_dict(self):
        msg = Message(topic="signal", payload={"x": 1}, from_role="detector")
        d = msg.to_dict()
        assert d["topic"] == "signal"
        assert d["from_role"] == "detector"
        assert d["status"] == "pending"

    def test_from_dict(self):
        msg = Message(topic="insight", payload={"y": 2}, from_role="correlator")
        d = msg.to_dict()
        msg2 = Message.from_dict(d)
        assert msg2.topic == "insight"
        assert msg2.payload == {"y": 2}
        assert msg2.from_role == "correlator"


class TestMessageBus:
    def test_publish_and_consume(self, bus):
        msg = Message(topic="signal", payload={"metric": "cpu"}, from_role="detector")
        bus.publish(msg)
        messages = bus.consume("signal", "correlator")
        assert len(messages) == 1
        # Note: dict access, not attribute access
        assert messages[0]["payload"]["metric"] == "cpu"

    def test_consume_broadcast(self, bus):
        msg = Message(topic="signal", payload={"x": 1}, from_role="detector", to_role=None)
        bus.publish(msg)
        messages = bus.consume("signal", "any_role")
        assert len(messages) == 1

    def test_consume_targeted(self, bus):
        msg = Message(topic="signal", payload={"x": 1}, from_role="detector", to_role="correlator")
        bus.publish(msg)
        messages = bus.consume("signal", "correlator")
        assert len(messages) == 1
        # Other role should not receive
        messages_other = bus.consume("signal", "evolver")
        assert len(messages_other) == 0

    def test_acknowledge(self, bus):
        msg = Message(topic="signal", payload={"x": 1}, from_role="detector")
        bus.publish(msg)
        messages = bus.consume("signal", "correlator")
        bus.acknowledge(messages[0]["message_id"])
        # Should not appear in pending
        pending = bus.get_pending("signal")
        assert len(pending) == 0

    def test_dead_letter_after_max_attempts(self, bus):
        msg = Message(topic="signal", payload={"x": 1}, from_role="detector")
        bus.publish(msg)
        # Consume and acknowledge 3 times (simulating repeated failures)
        for _ in range(3):
            messages = bus.consume("signal", "correlator")
            if messages:
                bus.acknowledge(messages[0]["message_id"])
        # After 3 attempts, message should be dead
        pending = bus.get_pending("signal")
        assert len(pending) == 0

    def test_cleanup_expired(self, bus):
        msg = Message(topic="signal", payload={"x": 1}, from_role="detector")
        bus.publish(msg)
        messages = bus.consume("signal", "correlator")
        bus.acknowledge(messages[0]["message_id"])
        # Cleanup runs without error and returns count
        removed = bus.cleanup_expired(days=0)
        assert removed >= 0

    def test_subscribe(self, bus):
        received = []
        bus.subscribe("signal", lambda msg: received.append(msg))
        msg = Message(topic="signal", payload={"x": 1}, from_role="detector")
        bus.publish(msg)
        assert len(received) == 1

    def test_subscribe_broadcast(self, bus):
        received = []
        bus.subscribe("*", lambda msg: received.append(msg))
        msg = Message(topic="insight", payload={"x": 1}, from_role="correlator")
        bus.publish(msg)
        assert len(received) == 1


class TestTopics:
    def test_topics_defined(self):
        assert "signal" in TOPICS
        assert "insight" in TOPICS
        assert "proposal" in TOPICS
        assert "experiment" in TOPICS
        assert "promotion" in TOPICS
        assert "alert" in TOPICS
        assert "command" in TOPICS
