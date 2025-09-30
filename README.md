# chatroom_prototype

Minimal FastAPI + WebSocket chat bridged via NATS with SQLite rooms.

Run locally:

1) Create and activate a venv (optional) and install deps

```
pip install -r requirements.txt
```

2) Start a local NATS server

```
nats-server -p 4222
```

3) Run the app

```
uvicorn chatroom_prototype.app:app --reload --host 0.0.0.0 --port 8000
```

4) Open the UI at http://localhost:8000/

