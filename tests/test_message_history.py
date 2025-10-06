import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from history_io import MessageHistory  # noqa: E402


def test_message_history_save_and_retrieve(tmp_path):
    """Test saving and retrieving messages."""
    history_dir = tmp_path / "test_history"
    history = MessageHistory(str(history_dir))

    server_id = 1

    # Save some test messages
    messages = [
        {"type": "message", "username": "alice", "text": "Hello world!"},
        {"type": "message", "username": "bob", "text": "Hi there!"},
        {"type": "system", "event": "join", "username": "charlie"},
    ]

    for msg in messages:
        history.save_message(server_id, msg)

    # Retrieve messages
    retrieved = history.get_messages(server_id)

    assert len(retrieved) == 3
    assert retrieved[0]["username"] == "alice"
    assert retrieved[1]["username"] == "bob"
    assert retrieved[2]["username"] == "charlie"

    # Check that timestamps were added
    for msg in retrieved:
        assert "timestamp" in msg


def test_message_history_limit(tmp_path):
    """Test message retrieval with limit."""
    history_dir = tmp_path / "test_history"
    history = MessageHistory(str(history_dir))

    server_id = 1

    # Save 10 messages
    for i in range(10):
        history.save_message(
            server_id, {"type": "message", "username": f"user{i}", "text": f"Message {i}"}
        )

    # Retrieve with limit
    recent_messages = history.get_messages(server_id, limit=5)

    assert len(recent_messages) == 5
    # Should get the most recent messages (5-9)
    assert recent_messages[0]["username"] == "user5"
    assert recent_messages[-1]["username"] == "user9"


def test_message_history_empty_server(tmp_path):
    """Test retrieving messages from server with no history."""
    history_dir = tmp_path / "test_history"
    history = MessageHistory(str(history_dir))

    messages = history.get_messages(999)  # Non-existent server
    assert messages == []


def test_message_history_count(tmp_path):
    """Test message count functionality."""
    history_dir = tmp_path / "test_history"
    history = MessageHistory(str(history_dir))

    server_id = 1

    # Initially no messages
    assert history.get_message_count(server_id) == 0

    # Add some messages
    for i in range(5):
        history.save_message(
            server_id, {"type": "message", "username": f"user{i}", "text": f"Message {i}"}
        )

    assert history.get_message_count(server_id) == 5


def test_message_history_clear(tmp_path):
    """Test clearing message history."""
    history_dir = tmp_path / "test_history"
    history = MessageHistory(str(history_dir))

    server_id = 1

    # Add some messages
    history.save_message(server_id, {"type": "message", "username": "test", "text": "test"})
    assert history.get_message_count(server_id) == 1

    # Clear history
    result = history.clear_history(server_id)
    assert result is True
    assert history.get_message_count(server_id) == 0

    # Clearing non-existent history should return False
    result = history.clear_history(999)
    assert result is False


def test_message_history_malformed_json(tmp_path):
    """Test handling of malformed JSON in history files."""
    history_dir = tmp_path / "test_history"
    history = MessageHistory(str(history_dir))

    server_id = 1

    # Manually create a history file with malformed JSON
    history_file = history._get_history_file(server_id)
    with open(history_file, "w", encoding="utf-8") as f:
        f.write('{"valid": "json"}\n')
        f.write("invalid json line\n")
        f.write('{"another": "valid"}\n')

    # Should skip malformed lines and return valid ones
    messages = history.get_messages(server_id)
    assert len(messages) == 2
    assert messages[0]["valid"] == "json"
    assert messages[1]["another"] == "valid"


def test_message_history_different_servers(tmp_path):
    """Test that different servers have separate message histories."""
    history_dir = tmp_path / "test_history"
    history = MessageHistory(str(history_dir))

    # Add messages to different servers
    history.save_message(1, {"username": "user1", "text": "Server 1 message"})
    history.save_message(2, {"username": "user2", "text": "Server 2 message"})

    # Check that messages are separate
    server1_messages = history.get_messages(1)
    server2_messages = history.get_messages(2)

    assert len(server1_messages) == 1
    assert len(server2_messages) == 1
    assert server1_messages[0]["text"] == "Server 1 message"
    assert server2_messages[0]["text"] == "Server 2 message"
