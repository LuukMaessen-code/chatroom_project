import asyncio
import json
import os
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


try:
    import nats
except ImportError as exc:
    raise RuntimeError(
        (
            "The 'nats-py' package is required. Install dependencies with "
            "'pip install -r requirements.txt'."
        )
    ) from exc


_nats_connection: Optional[nats.NATS] = None


async def get_nats() -> nats.NATS:
    global _nats_connection
    if _nats_connection is not None and _nats_connection.is_connected:
        return _nats_connection

    nats_url = os.environ.get("NATS_URL", "nats://127.0.0.1:4222")
    _nats_connection = await nats.connect(servers=[nats_url])
    return _nats_connection


async def run_service() -> None:
    """Run the message history microservice.

    Subscribes to all chat subjects (chat.>) and persists any received
    JSON messages that include a numeric serverId field.
    """

    nc = await get_nats()

    # History directory (shared volume). Defaults to ./message_history
    module_dir = Path(__file__).parent
    history_dir = Path(os.environ.get("HISTORY_DIR", str(module_dir / "message_history")))
    history_dir.mkdir(exist_ok=True, parents=True)

    def _history_file(server_id: int) -> Path:
        return history_dir / f"server_{server_id}_history.jsonl"

    def _append_message(server_id: int, message_data: dict) -> None:
        if "timestamp" not in message_data:
            message_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        file_path = _history_file(server_id)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message_data) + "\n")

    async def handler(msg: "nats.aio.msg.Msg") -> None:  # type: ignore[name-defined]
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return

        server_id = data.get("serverId")
        if isinstance(server_id, int):
            try:
                _append_message(server_id, data)
            except Exception:
                # Swallow errors to keep the subscriber healthy
                pass

    # Subscribe to all chat messages for all servers
    sub = await nc.subscribe("chat.>", cb=handler)

    # Wait until cancelled
    stop_event: asyncio.Event = asyncio.Event()

    def _signal_handler(*_args):  # noqa: ANN001
        try:
            stop_event.set()
        except Exception:
            pass

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows may not support all signals in asyncio
            signal.signal(sig, lambda *_a, **_k: _signal_handler())  # type: ignore[misc]

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


