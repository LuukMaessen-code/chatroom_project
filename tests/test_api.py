from fastapi.testclient import TestClient

from chatroom_prototype.app import app


def test_servers_endpoint(monkeypatch):
    # Ensure DB has default server on startup handler path
    client = TestClient(app)
    resp = client.get("/api/servers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(s.get("name") == "Main Room" for s in data)


def test_root_serves_index_html(monkeypatch):
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<!doctype html>" in resp.text.lower()
