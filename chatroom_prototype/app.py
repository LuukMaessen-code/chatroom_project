import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

try:
    # Try package-style imports (when run as module)
    from .db import ensure_default_server, get_db, get_server_by_id, list_servers
    from .history_io import message_history
except ImportError:
    # Fall back to direct imports (when run directly or in tests)
    from db import ensure_default_server, get_db, get_server_by_id, list_servers
    from history_io import message_history

try:
    import nats
except ImportError as exc:
    raise RuntimeError(
        (
            "The 'nats-py' package is required. Install dependencies with "
            "'pip install -r requirements.txt'."
        )
    ) from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure DB default server, warm NATS connection
    with get_db() as conn:
        ensure_default_server(conn)
    try:
        await get_nats()
    except Exception:
        # It's okay if NATS isn't running at startup; connections will be
        # retried on first use
        pass
    yield
    # Shutdown: close NATS if connected
    try:
        if _nats_connection is not None and _nats_connection.is_connected:
            await _nats_connection.drain()
            await _nats_connection.close()
    except Exception:
        pass


app = FastAPI(title="NATS Chatroom Prototype", lifespan=lifespan)


# Mount static files from project root ./public (one level up from package)
public_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
if not os.path.isdir(public_dir):
    os.makedirs(public_dir, exist_ok=True)
app.mount("/public", StaticFiles(directory=public_dir), name="public")


_nats_connection: Optional[nats.NATS] = None


async def get_nats() -> nats.NATS:
    global _nats_connection
    if _nats_connection is not None and _nats_connection.is_connected:
        return _nats_connection

    # Connect to local NATS by default; can override via env var NATS_URL
    nats_url = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
    _nats_connection = await nats.connect(servers=[nats_url])
    return _nats_connection


@app.get("/", response_class=HTMLResponse)
async def root_html() -> HTMLResponse:
    # Serve the index.html from /public
    index_path = os.path.join(public_dir, "index.html")
    if not os.path.isfile(index_path):
        raise HTTPException(status_code=404, detail="index.html not found")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/servers")
async def api_list_servers() -> list[dict]:
    with get_db() as conn:
        servers = list_servers(conn)
    return servers


@app.get("/api/servers/{server_id}/messages")
async def api_get_messages(server_id: int, limit: int = 100) -> list[dict]:
    """Get message history for a server."""
    with get_db() as conn:
        server = get_server_by_id(conn, server_id)
        if server is None:
            raise HTTPException(status_code=404, detail="Server not found")

    messages = message_history.get_messages(server_id, limit)
    return messages


@app.websocket("/ws/{server_id}")
async def websocket_endpoint(websocket: WebSocket, server_id: int) -> None:
    with get_db() as conn:
        server = get_server_by_id(conn, server_id)
        if server is None:
            await websocket.close(code=1008)
            return

    # Require username in query params
    username = websocket.query_params.get("username")
    if username is None or not username.strip():
        await websocket.close(code=1008)
        return

    username = username.strip()

    await websocket.accept()

    nc = await get_nats()
    subject = f"chat.{server_id}"

    send_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def nats_message_handler(msg):
        # Only forward to WebSocket; message persistence is handled by the
        # dedicated message history microservice.
        await send_queue.put(msg.data)

    sub = await nc.subscribe(subject, cb=nats_message_handler)

    async def ws_sender():
        try:
            while True:
                data = await send_queue.get()
                await websocket.send_text(data.decode("utf-8"))
        except Exception:
            pass

    sender_task = asyncio.create_task(ws_sender())

    try:
        # Send message history to the new user
        history_messages = message_history.get_messages(server_id, limit=50)
        for msg in history_messages:
            try:
                await websocket.send_text(json.dumps(msg))
            except Exception:
                # If we can't send history, continue anyway
                pass

        # Notify join
        join_payload = json.dumps(
            {
                "type": "system",
                "event": "join",
                "serverId": server_id,
                "username": username,
            }
        ).encode("utf-8")
        await nc.publish(subject, join_payload)

        while True:
            text = await websocket.receive_text()
            # Expect client to send simple text; wrap into JSON
            payload = json.dumps(
                {
                    "type": "message",
                    "serverId": server_id,
                    "text": text,
                    "username": username,
                }
            ).encode("utf-8")
            await nc.publish(subject, payload)

    except WebSocketDisconnect:
        pass
    finally:
        try:
            # Notify leave
            leave_payload = json.dumps(
                {
                    "type": "system",
                    "event": "leave",
                    "serverId": server_id,
                    "username": username,
                }
            ).encode("utf-8")
            await nc.publish(subject, leave_payload)
        except Exception:
            pass

        try:
            await nc.flush(timeout=1)
        except Exception:
            pass

        try:
            await sub.unsubscribe()
        except Exception:
            pass

        try:
            sender_task.cancel()
        except Exception:
            pass
