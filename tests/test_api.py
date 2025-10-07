import pytest
import httpx

from chatroom_prototype.app import app


@pytest.mark.asyncio
async def test_list_servers_returns_at_least_one_room():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/servers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "id" in data[0] and "name" in data[0]


@pytest.mark.asyncio
async def test_get_messages_for_first_server():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        servers = (await client.get("/api/servers")).json()
        assert servers, "Expected at least one server"
        server_id = servers[0]["id"]

        resp = await client.get(f"/api/servers/{server_id}/messages?limit=5")
        assert resp.status_code == 200
        msgs = resp.json()
        assert isinstance(msgs, list)

