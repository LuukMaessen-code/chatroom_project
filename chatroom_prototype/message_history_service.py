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
    # Initialize DB pool with simple retry to handle cold starts
    attempt = 0
    while True:
        try:
            await message_history.init()
            print("[history] DB pool initialized")
            break
        except Exception as exc:
            attempt += 1
            print(f"[history] DB init failed (attempt {attempt}): {exc}")
            await asyncio.sleep(min(5 * attempt, 30))

    nc = await get_nats()
    print("[history] Connected to NATS")

    async def handler(msg: "nats.aio.msg.Msg") -> None:  # type: ignore[name-defined]
        try:
            payload = msg.data.decode("utf-8")
            data = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"[history] skip non-json on {msg.subject}: {exc}")
            return

        server_id = data.get("serverId")
        if not isinstance(server_id, int):
            print(f"[history] skip message without numeric serverId on {msg.subject}: {data}")
            return

        try:
            await message_history.save_message(server_id, data)
            # Lightweight success indicator (can be noisy; keep minimal)
            print(
                f"[history] saved server={server_id} type={data.get('type')} "
                f"user={data.get('username')}"
            )
        except Exception as exc:
            print(f"[history] save failed server={server_id}: {exc}")

    # Dynamic room subscriptions: subscribe when a client joins
    active_room_subs: dict[int, nats.aio.subscription.Subscription] = {}

    async def watch_handler(msg: "nats.aio.msg.Msg") -> None:  # type: ignore[name-defined]
        subject = msg.subject  # chat.history.watch.{server_id}
        try:
            server_id = int(subject.rsplit(".", 1)[-1])
        except Exception:
            print(f"[history] invalid watch subject: {subject}")
            return
        if server_id in active_room_subs:
            return
        room_subject = f"chat.{server_id}"
        active_room_subs[server_id] = await nc.subscribe(room_subject, cb=handler)
        print(f"[history] now watching {room_subject}")

    await nc.subscribe("chat.history.watch.*", cb=watch_handler)
    print("[history] Subscribed to chat.history.watch.* (room discovery)")

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
        # Unsubscribe dynamic room subscriptions
        try:
            for _sid, _sub in list(active_room_subs.items()):
                try:
                    await _sub.unsubscribe()
                except Exception:
                    pass
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
    