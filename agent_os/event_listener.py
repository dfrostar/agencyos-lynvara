"""event_listener.py — Webhook listener for telehealth event bus.

AgencyOS subscribes to the telehealth event bus via webhook.
When events fire (vendor.created, contract.signed, etc.),
AgencyOS auto-updates ops_kb and triggers its own workflows.

Usage:
    from agent_os.event_listener import EventListener
    listener = EventListener(base_url="https://lynvara-api.onrender.com", admin_key="...")
    await listener.start()
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine, Optional

import httpx

log = logging.getLogger(__name__)

# Event types we care about
SUPPORTED_EVENTS = [
    "vendor.created",
    "vendor.updated",
    "contract.signed",
    "infrastructure.deployed",
    "decision.made",
    "meeting.held",
    "credential.created",
]


class EventListener:
    """Listens for telehealth events via webhook polling."""

    def __init__(
        self,
        base_url: str,
        admin_key: str,
        poll_interval: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.admin_key = admin_key
        self.poll_interval = poll_interval
        self.client = httpx.AsyncClient(
            base_url=f"{self.base_url}/api",
            headers={
                "x-admin-key": self.admin_key,
                "Content-Type": "application/json",
            },
        )
        self._handlers: dict[str, Callable[[dict[str, Any]], Coroutine[Any, Any, None]]] = {}

    def on(self, event_type: str, handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None]]) -> None:
        """Register an event handler."""
        self._handlers[event_type] = handler
        log.info(f"[event-listener] registered handler for: {event_type}")

    async def start(self) -> None:
        """Start listening for events (runs forever)."""
        log.info(f"[event-listener] starting, polling every {self.poll_interval}s")
        while True:
            try:
                await self._poll_events()
            except Exception as e:
                log.error(f"[event-listener] poll error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _poll_events(self) -> None:
        """Poll for new events."""
        resp = await self.client.get("/events/pending")
        if resp.status_code != 200:
            return
        events = resp.json().get("data", [])
        for event in events:
            event_type = event.get("type", "")
            handler = self._handlers.get(event_type)
            if handler:
                try:
                    await handler(event.get("payload", {}))
                    # Acknowledge event
                    await self.client.post(f"/events/{event.get('id')}/ack")
                except Exception as e:
                    log.error(f"[event-listener] handler error for {event_type}: {e}")

    async def close(self) -> None:
        await self.client.aclose()


import asyncio  # noqa: E402
