from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

log = logging.getLogger(__name__)

TOPICS = ("signal", "insight", "proposal", "experiment", "promotion", "alert", "command")
MAX_DELIVERY_ATTEMPTS = 3
RETENTION_DAYS = 7


class Message:
    """A message on the bus."""

    def __init__(
        self,
        topic: str,
        payload: dict[str, Any],
        from_role: str,
        to_role: str | None = None,
        tenant_id: str = "default",
        message_id: str | None = None,
        created_at: str | None = None,
    ) -> None:
        self.message_id = message_id or f"msg_{uuid.uuid4().hex[:12]}"
        self.topic = topic
        self.payload = payload
        self.from_role = from_role
        self.to_role = to_role  # None = broadcast
        self.tenant_id = tenant_id
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.status = "pending"
        self.consume_count = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "topic": self.topic,
            "payload": json.dumps(self.payload),
            "from_role": self.from_role,
            "to_role": self.to_role,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at,
            "status": self.status,
            "consume_count": self.consume_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        msg = cls(
            topic=data["topic"],
            payload=json.loads(data["payload"]),
            from_role=data["from_role"],
            to_role=data.get("to_role"),
            tenant_id=data.get("tenant_id", "default"),
            message_id=data["message_id"],
            created_at=data.get("created_at"),
        )
        msg.status = data.get("status", "pending")
        msg.consume_count = data.get("consume_count", 0)
        return msg


def _parse_payload(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse JSON payload strings in message dicts."""
    for m in messages:
        if isinstance(m.get("payload"), str):
            m["payload"] = json.loads(m["payload"])
    return messages


class MessageBus:
    """SQLite-backed pub/sub message bus.

    At-least-once delivery: messages remain in queue until explicitly
    acknowledged (status='consumed'). Dead letter queue after MAX_DELIVERY_ATTEMPTS.
    """

    def __init__(self, store: Any) -> None:
        self._store = store
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[Callable[[Message], None]]] = {}

    def publish(self, message: Message) -> None:
        """Publish a message to the bus."""
        with self._lock:
            self._store.insert_bus_message(message.to_dict())
            topic_subs = list(self._subscribers.get(message.topic, []))
            broadcast_subs = list(self._subscribers.get("*", []))
        # Notify outside the lock to prevent deadlock
        for cb in topic_subs + broadcast_subs:
            try:
                cb(message)
            except Exception:
                log.exception("Subscriber callback failed for topic %s", message.topic)

    def subscribe(self, topic: str, callback: Callable[[Message], None]) -> None:
        """Subscribe to a topic. Use '*' for all topics."""
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)

    def consume(
        self, topic: str, role: str, tenant_id: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Consume pending messages for a topic + role + tenant (or broadcast)."""
        messages = self._store.consume_bus_messages(topic, role, tenant_id, limit)
        return _parse_payload(messages)

    def acknowledge(self, message_id: str) -> None:
        """Mark a message as consumed."""
        self._store.acknowledge_bus_message(message_id)

    def get_pending(self, topic: str | None = None) -> list[dict[str, Any]]:
        """Get pending messages (for monitoring)."""
        messages = self._store.get_pending_bus_messages(topic)
        return _parse_payload(messages)

    def cleanup_expired(self, days: int = RETENTION_DAYS) -> int:
        """Remove consumed messages older than `days`. Returns count removed."""
        return self._store.cleanup_expired_bus_messages(days)
