"""ops_kb.py — Ops Knowledge Base API Client for AgencyOS Lynvara.

Reads/writes ops_kb tables via the telehealth REST API.
Replaces the SQLite store.py for Lynvara-specific deployments.

Usage:
    from agent_os.ops_kb import OpsKbClient
    client = OpsKbClient(base_url="https://lynvara-api.onrender.com", admin_key="...")
    vendors = await client.list_vendors()
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)


class OpsKbClient:
    """Client for the ops_kb REST API at /api/ops-kb/*."""

    def __init__(self, base_url: str, admin_key: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.admin_key = admin_key
        self.client = httpx.AsyncClient(
            base_url=f"{self.base_url}/api/ops-kb",
            headers={
                "x-admin-key": self.admin_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def close(self) -> None:
        await self.client.aclose()

    # -------------------------------------------------------------------
    # Health
    # -------------------------------------------------------------------
    async def health(self) -> dict[str, Any]:
        resp = await self.client.get("/health")
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------
    # Contracts
    # -------------------------------------------------------------------
    async def list_contracts(
        self,
        vendor_id: Optional[str] = None,
        status: Optional[str] = None,
        type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if vendor_id:
            params["vendor_id"] = vendor_id
        if status:
            params["status"] = status
        if type:
            params["type"] = type
        resp = await self.client.get("/contracts", params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def get_contract(self, contract_id: str) -> dict[str, Any]:
        resp = await self.client.get(f"/contracts/{contract_id}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def create_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.post("/contracts", json=contract)
        resp.raise_for_status()
        return resp.json()

    async def update_contract(self, contract_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.patch(f"/contracts/{contract_id}", json=updates)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------
    # Infrastructure
    # -------------------------------------------------------------------
    async def list_infrastructure(
        self,
        status: Optional[str] = None,
        component_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if component_type:
            params["component_type"] = component_type
        resp = await self.client.get("/infrastructure", params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def get_infrastructure(self, infra_id: str) -> dict[str, Any]:
        resp = await self.client.get(f"/infrastructure/{infra_id}")
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def create_infrastructure(self, infra: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.post("/infrastructure", json=infra)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------
    # Integrations
    # -------------------------------------------------------------------
    async def list_integrations(
        self,
        vendor_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if vendor_id:
            params["vendor_id"] = vendor_id
        if status:
            params["status"] = status
        resp = await self.client.get("/integrations", params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def create_integration(self, integration: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.post("/integrations", json=integration)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------
    # Decisions
    # -------------------------------------------------------------------
    async def list_decisions(self, tag: Optional[str] = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if tag:
            params["tag"] = tag
        resp = await self.client.get("/decisions", params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def create_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.post("/decisions", json=decision)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------
    # Meetings
    # -------------------------------------------------------------------
    async def list_meetings(self) -> list[dict[str, Any]]:
        resp = await self.client.get("/meetings")
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def create_meeting(self, meeting: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.post("/meetings", json=meeting)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------
    # Credentials
    # -------------------------------------------------------------------
    async def list_credentials(self) -> list[dict[str, Any]]:
        resp = await self.client.get("/credentials")
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def create_credential(self, credential: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.post("/credentials", json=credential)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------
    # Tags
    # -------------------------------------------------------------------
    async def list_tags(self) -> list[dict[str, Any]]:
        resp = await self.client.get("/tags")
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def create_tag(self, tag: dict[str, Any]) -> dict[str, Any]:
        resp = await self.client.post("/tags", json=tag)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------
    async def search(self, q: str, entity_type: Optional[str] = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {"q": q}
        if entity_type:
            params["entity_type"] = entity_type
        resp = await self.client.get("/search", params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

    # -------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------
    async def export_markdown(self) -> str:
        resp = await self.client.get("/export")
        resp.raise_for_status()
        return resp.text
