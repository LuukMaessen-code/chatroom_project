import os
import json
from typing import Dict, List, Optional
import asyncpg
from datetime import datetime, timezone


class MessageHistory:
    """Handles saving and retrieving message history from Postgres."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        if not self.database_url:
            # Defer raising until first use to allow app startup without DB
            self.database_url = None  # type: ignore[assignment]
        self.pool: Optional[asyncpg.pool.Pool] = None
        # Back-compat for tests that monkeypatch history_dir
        self.history_dir = None

    async def init(self):
        if self.pool is not None:
            return
        if not self.database_url:
            raise ValueError("DATABASE_URL must be set for Postgres connection")
        self.pool = await asyncpg.create_pool(dsn=self.database_url)
        # Ensure required schema exists
        await self._ensure_schema()

    async def _ensure_pool(self):
        if self.pool is None:
            await self.init()

    async def _ensure_schema(self) -> None:
        if self.pool is None:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    server_id INTEGER NOT NULL,
                    type TEXT,
                    event TEXT,
                    username TEXT,
                    text TEXT,
                    timestamp TIMESTAMPTZ,
                    raw_data JSONB
                );
                CREATE INDEX IF NOT EXISTS idx_messages_server_id_timestamp
                    ON messages(server_id, timestamp);
                """
            )

    async def save_message(self, server_id: int, message_data: Dict) -> None:
        # Normalize timestamp to a datetime object for timestamptz column
        ts = message_data.get("timestamp")
        if ts is None:
            ts_dt = datetime.now(timezone.utc)
        elif isinstance(ts, str):
            try:
                ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                ts_dt = datetime.now(timezone.utc)
        elif isinstance(ts, datetime):
            ts_dt = ts
        else:
            ts_dt = datetime.now(timezone.utc)

        await self._ensure_pool()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO messages (server_id, type, event, username, text, timestamp, raw_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                server_id,
                message_data.get("type"),
                message_data.get("event"),
                message_data.get("username"),
                message_data.get("text"),
                ts_dt,
                json.dumps(message_data),
            )

    async def get_messages(self, server_id: int, limit: Optional[int] = 100) -> List[Dict]:
        await self._ensure_pool()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT raw_data
                FROM messages
                WHERE server_id = $1
                ORDER BY timestamp ASC
                LIMIT $2
                """,
                server_id,
                limit,
            )
        return [json.loads(row["raw_data"]) for row in rows]

    async def clear_history(self, server_id: int) -> None:
        await self._ensure_pool()
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM messages WHERE server_id = $1", server_id)

    async def get_message_count(self, server_id: int) -> int:
        await self._ensure_pool()
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM messages WHERE server_id = $1", server_id
            )
        return count


message_history = MessageHistory()
