import os
import json
import asyncio
from typing import Dict, List, Optional
import asyncpg
from datetime import datetime, timezone


class MessageHistory:
    """Handles saving and retrieving message history from Postgres."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL must be set for Postgres connection")
        self.pool: Optional[asyncpg.pool.Pool] = None

    async def init(self):
        self.pool = await asyncpg.create_pool(dsn=self.database_url)

    async def save_message(self, server_id: int, message_data: Dict) -> None:
        if "timestamp" not in message_data:
            message_data["timestamp"] = datetime.now(timezone.utc).isoformat()

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
                message_data.get("timestamp"),
                json.dumps(message_data),
            )

    async def get_messages(self, server_id: int, limit: Optional[int] = 100) -> List[Dict]:
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
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM messages WHERE server_id = $1", server_id)

    async def get_message_count(self, server_id: int) -> int:
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM messages WHERE server_id = $1", server_id
            )
        return count


message_history = MessageHistory()