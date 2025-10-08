import asyncio
import json
import os
import signal
from typing import Optional

# Load environment variables from .env
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

import nats
try:
    # Prefer package-relative import when executed as a module
    from .history_io import message_history
except ImportError:
    # Fallback for direct script execution
    from history_io import message_history


_nats_connection: Optional[nats.NATS] = None


async def get_nats() -> nats.NATS:
    global _nats_connection
    if _nats_connection is not None and _nats_connection.is_connected:
        return _nats_connection

    nats_url = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
    _nats_connection = await nats.connect(servers=[nats_url])
    return _nats_connection


async def run_service() -> None:
    """Run the message history microservice using Supabase/Postgres."""
    await message_history.init()
    nc = await get_nats()

    async def handler(msg: "nats.aio.msg.Msg") -> None:  # type: ignore[name-defined]
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return

        server_id = data.get("serverId")
        if isinstance(server_id, int):
            try:
                await message_history.save_message(server_id, data)
            except Exception:
                # Swallow errors to keep the subscriber healthy
                pass

    # Subscribe to all chat messages for all servers
    sub = await nc.subscribe("chat.>", cb=handler)

    # Wait until cancelled
    stop_event: asyncio.Event = asyncio.Event()

    def _signal_handler(*_args):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            import signal as sigmod

            sigmod.signal(sig, lambda *_a, **_k: _signal_handler())  # type: ignore

    try:
        await stop_event.wait()
    finally:
        try:
            await sub.unsubscribe()
        except Exception:
            pass
        try:
            if _nats_connection is not None and _nats_connection.is_connected:
                await _nats_connection.drain()
                await _nats_connection.close()
        finally:
            pass


def main() -> None:
    asyncio.run(run_service())


if __name__ == "__main__":
    main()