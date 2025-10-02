import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db as db_mod


def test_ensure_default_server_creates_one(tmp_path):
    db_path = tmp_path / "chatroom.db"
    db_mod.DB_PATH = str(db_path)

    with db_mod.get_db() as conn:
        db_mod.ensure_default_server(conn)
        rows = list(conn.execute("SELECT id, name FROM servers"))
        assert len(rows) == 1
        assert rows[0][1] == "Main Room"


def test_list_servers_returns_default(tmp_path):
    db_path = tmp_path / "chatroom.db"
    db_mod.DB_PATH = str(db_path)

    with db_mod.get_db() as conn:
        db_mod.ensure_default_server(conn)
        servers = db_mod.list_servers(conn)
        assert len(servers) == 1
        assert servers[0]["name"] == "Main Room"
