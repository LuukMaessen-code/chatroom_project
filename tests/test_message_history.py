from chatroom_prototype.history_io import message_history


def test_message_history_roundtrip(tmp_path, monkeypatch):
    # Redirect history directory to a temp path
    monkeypatch.setattr(message_history, "history_dir", tmp_path)

    server_id = 999
    message_history.clear_history(server_id)

    message_history.save_message(server_id, {"serverId": server_id, "text": "hello"})
    message_history.save_message(server_id, {"serverId": server_id, "text": "world"})

    msgs = message_history.get_messages(server_id, limit=10)
    assert len(msgs) == 2
    assert msgs[0]["text"] == "hello"
    assert msgs[1]["text"] == "world"

    assert message_history.clear_history(server_id) is True
