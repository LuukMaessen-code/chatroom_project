import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Load environment variables from .env early, before importing modules that read env
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

try:
    # Try package-style imports (when run as module)
    from .db import ensure_default_server, get_db, get_server_by_id, list_servers
    from .history_io import message_history
    from .models import ChatMessage, Server
except ImportError:
    # Fall back to direct imports (when run directly or in tests)
    from db import ensure_default_server, get_db, get_server_by_id, list_servers
    from history_io import message_history
    from models import ChatMessage, Server

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
    # Initialize message history backend (e.g., Postgres pool)
    try:
        await message_history.init()
    except Exception:
        # Allow app to start; endpoints using history will error if misconfigured
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
_js: Optional["nats.js.JetStreamContext"] = None  # type: ignore[valid-type]


async def get_nats() -> nats.NATS:
    global _nats_connection
    if _nats_connection is not None and _nats_connection.is_connected:
        return _nats_connection

    # Connect to local NATS by default; can override via env var NATS_URL
    nats_url = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
    _nats_connection = await nats.connect(servers=[nats_url])
    return _nats_connection


async def get_jetstream():
    global _js
    nc = await get_nats()
    if _js is not None:
        return _js
    js = nc.jetstream()
    # Ensure stream exists for chat subjects
    try:
        await js.add_stream({
            "name": "CHAT",
            "subjects": ["chat.*"],
            "retention": "limits",
        })
    except Exception:
        # Stream likely exists
        pass
    _js = js
    return _js


@app.get("/", response_class=HTMLResponse)
async def root_html() -> HTMLResponse:
    # Serve the index.html from /public
    index_path = os.path.join(public_dir, "index.html")
    if not os.path.isfile(index_path):
        raise HTTPException(status_code=404, detail="index.html not found")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/servers", response_model=List[Server])
async def api_list_servers() -> list[Server]:
    with get_db() as conn:
        servers = list_servers(conn)
    return [Server(**srv) for srv in servers]


@app.get("/api/servers/{server_id}/messages", response_model=List[ChatMessage])
async def api_get_messages(server_id: int, limit: int = 100) -> list[ChatMessage]:
    """Get message history for a server."""
    with get_db() as conn:
        server = get_server_by_id(conn, server_id)
        if server is None:
            raise HTTPException(status_code=404, detail="Server not found")

    messages = await message_history.get_messages(server_id, limit)
    # Coerce to models (accept dicts from storage)
    return [ChatMessage(**m) if not isinstance(m, ChatMessage) else m for m in messages]


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

    # Ensure NATS is available; if not, signal the client to retry later.
    try:
        nc = await get_nats()
        js = await get_jetstream()
    except Exception:
        try:
            await websocket.close(code=1013)  # Try Again Later
        finally:
            return
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
        # Send message history to the new user (best-effort)
        try:
            history_messages = await message_history.get_messages(server_id, limit=50)
        except Exception:
            history_messages = []
        for msg in history_messages:
            try:
                if isinstance(msg, ChatMessage):
                    await websocket.send_text(msg.model_dump_json(by_alias=True))
                else:
                    await websocket.send_text(json.dumps(msg))
            except Exception:
                # If we can't send history, continue anyway
                pass

        # Notify history service to watch this room
        try:
            await nc.publish(f"chat.history.watch.{server_id}", b"{}")
        except Exception:
            pass

        # Notify join
        join_msg = ChatMessage(type="system", event="join", server_id=server_id, username=username)
        await js.publish(subject, join_msg.model_dump_json(by_alias=True).encode("utf-8"))

        while True:
            text = await websocket.receive_text()
            # Expect client to send simple text; wrap into model
            chat_msg = ChatMessage(
                type="message",
                server_id=server_id,
                text=text,
                username=username,
            )
            await js.publish(subject, chat_msg.model_dump_json(by_alias=True).encode("utf-8"))

    except WebSocketDisconnect:
        pass
    finally:
        try:
            # Notify leave
            leave_msg = ChatMessage(type="system", event="leave", server_id=server_id, username=username)
            js = await get_jetstream()
            await js.publish(subject, leave_msg.model_dump_json(by_alias=True).encode("utf-8"))
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
