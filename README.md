# chatroom_prototype

Minimal FastAPI + WebSocket chat bridged via NATS with SQLite rooms and persistent message history.

## Features

- **Real-time messaging** via WebSocket and NATS
- **Persistent message history** saved to files
- **Multiple chat rooms** with SQLite database
- **Message replay** for new users joining rooms
- **REST API** for message history retrieval
- **Comprehensive test suite** with CI/CD

## Quick Start

1) **Install dependencies**

```bash
pip install -r requirements.txt
```

2) **Start a NATS server using Docker**

```bash
docker run -d --name nats-server -p 4222:4222 nats

# To stop: docker stop nats-server
# To remove: docker rm nats-server
```

3) **Run the application**

You can run the server in multiple ways:

```bash
# As a package (recommended)
uvicorn chatroom_prototype.app:app --reload --host 0.0.0.0 --port 8000

# Or directly from the project directory
cd chatroom_prototype
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

4) **Open the UI**

Navigate to http://localhost:8000/

## API Endpoints

- `GET /api/servers` - List all chat rooms
- `GET /api/servers/{server_id}/messages?limit=100` - Get message history for a room
- `WebSocket /ws/{server_id}?username=your_name` - Connect to real-time chat

## Message History

Messages are automatically saved to `chatroom_prototype/message_history/server_{id}_history.jsonl` files by a dedicated microservice that listens to NATS subjects.

### Run the Message History Microservice

In a separate terminal, start the history service so it can persist all chat messages:

```bash
# From the project root
python -m chatroom_prototype.message_history_service

# Or when inside the package directory
python message_history_service.py
```

The service connects to NATS at `NATS_URL` (default `nats://127.0.0.1:4222`) and subscribes to `chat.>`.

New users joining a room will see the last 50 messages for context.

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

## Development

The project includes:
- **Linting**: flake8
- **Formatting**: black, isort  
- **CI/CD**: GitHub Actions workflow
- **Package configuration**: pyproject.toml

