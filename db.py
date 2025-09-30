import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional


DB_PATH = os.path.join(os.path.dirname(__file__), "chatroom.db")


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        """
    )
    conn.commit()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        _init_schema(conn)
        yield conn
    finally:
        conn.close()


def ensure_default_server(conn: sqlite3.Connection) -> None:
    # Ensure a single default server exists
    cur = conn.execute(
        "SELECT id FROM servers WHERE name = ?",
        ("Main Room",),
    )
    row = cur.fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO servers(name) VALUES(?)",
            ("Main Room",),
        )
        conn.commit()


def list_servers(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT id, name FROM servers ORDER BY id ASC")
    return [
        {"id": row["id"], "name": row["name"]}
        for row in cur.fetchall()
    ]


def get_server_by_id(conn: sqlite3.Connection, server_id: int) -> Optional[dict]:
    cur = conn.execute(
        "SELECT id, name FROM servers WHERE id = ?",
        (server_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {"id": row["id"], "name": row["name"]}
