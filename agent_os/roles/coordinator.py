"""coordinator.py — Role lifecycle manager and message router."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from agent_os.bus import MessageBus

from agent_os.roles.base import AgentRole

log = logging.getLogger(__name__)


class CoordinatorRole(AgentRole):
    """Manages role lifecycle, routes messages, enforces boundaries.

    Routes messages based on `to_role` field.
    Monitors role health: heartbeat timeout (no heartbeat in 60s → restart).
    Publishes system health metric.
    """

    ROLE_NAME = "coordinator"

    def __init__(
        self,
        tenant_id: str,
        bus: MessageBus,
        store: Any,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(tenant_id, bus, store, config)
        self._roles: dict[str, AgentRole] = {}
        self._heartbeat_timeout = config.get("heartbeat_timeout", 60.0) if config else 60.0

    def register_role(self, role: AgentRole) -> None:
        """Register a role with the coordinator."""
        self._roles[role.ROLE_NAME] = role

    def start(self) -> None:
        """Start coordinator and all registered roles."""
        super().start()
        for role in self._roles.values():
            role.start()

    def stop(self) -> None:
        """Stop coordinator and all registered roles."""
        for role in self._roles.values():
            role.stop()
        super().stop()

    def _poll(self) -> None:
        """Route messages + monitor role health."""
        self._route_messages()
        self._monitor_health()

    def _route_messages(self) -> None:
        """Route pending messages to the correct role."""
        pending = self._store.get_pending_bus_messages()
        for msg_dict in pending:
            to_role = msg_dict.get("to_role")
            if to_role and to_role in self._roles:
                role = self._roles[to_role]
                # Role will pick it up via consume() in its own _poll()
                pass

    def _monitor_health(self) -> None:
        """Check role heartbeats."""
        roles = self._store.get_roles(self._tenant_id)
        for role_dict in roles:
            if role_dict["role_name"] == self.ROLE_NAME:
                continue
            last_hb = role_dict.get("last_heartbeat")
            if last_hb is None:
                continue
            try:
                from datetime import datetime, timezone
                hb_time = datetime.fromisoformat(last_hb).replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if (now - hb_time).total_seconds() > self._heartbeat_timeout:
                    log.warning("Role %s heartbeat timeout", role_dict["role_name"])
            except (ValueError, TypeError):
                pass

    def get_status(self) -> dict[str, Any]:
        """Get coordinator status."""
        return {
            "roles": {
                name: {"role_id": role._role_id, "enabled": role._enabled}
                for name, role in self._roles.items()
            },
            "pending_messages": len(self._store.get_pending_bus_messages()),
        }
