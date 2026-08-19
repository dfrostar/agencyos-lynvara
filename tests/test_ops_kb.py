"""tests/test_ops_kb.py — Tests for the ops_kb API client."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_os.ops_kb import OpsKbClient


@pytest.fixture
def client() -> OpsKbClient:
    return OpsKbClient(base_url="https://lynvara-api.onrender.com", admin_key="test-key")


@pytest.mark.asyncio
async def test_list_contracts(client: OpsKbClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"id": "1", "title": "Test Contract"}]}
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.list_contracts()
        assert len(result) == 1
        assert result[0]["title"] == "Test Contract"


@pytest.mark.asyncio
async def test_list_infrastructure(client: OpsKbClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"id": "1", "slug": "lynvara-api"}]}
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.list_infrastructure()
        assert len(result) == 1
        assert result[0]["slug"] == "lynvara-api"


@pytest.mark.asyncio
async def test_search(client: OpsKbClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"id": "1", "title": "Cerbo Contract"}]}
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.search("cerbo")
        assert len(result) == 1


@pytest.mark.asyncio
async def test_health(client: OpsKbClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok", "vendorCount": 6}
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.health()
        assert result["status"] == "ok"
        assert result["vendorCount"] == 6
