import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402


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


def test_get_messages_endpoint(tmp_path):
    """Test the message history API endpoint."""
    # Set up temporary message history directory
    from history_io import message_history

    original_dir = message_history.history_dir
    message_history.history_dir = tmp_path / "test_history"
    message_history.history_dir.mkdir(exist_ok=True)

    try:
        client = TestClient(app)

        # Test getting messages for non-existent server
        resp = client.get("/api/servers/999/messages")
        assert resp.status_code == 404

        # Add some test messages to server 1
        test_messages = [
            {"type": "message", "username": "alice", "text": "Hello!"},
            {"type": "message", "username": "bob", "text": "Hi there!"},
        ]

        for msg in test_messages:
            message_history.save_message(1, msg)

        # Test getting messages for existing server
        resp = client.get("/api/servers/1/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["username"] == "alice"
        assert data[1]["username"] == "bob"

        # Test with limit parameter
        resp = client.get("/api/servers/1/messages?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["username"] == "bob"  # Most recent message

    finally:
        # Restore original directory
        message_history.history_dir = original_dir
