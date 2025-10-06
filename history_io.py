import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class MessageHistory:
    """Handles saving and retrieving message history for chat rooms."""

    def __init__(self, history_dir: str = "message_history"):
        module_dir = Path(__file__).parent
        self.history_dir = module_dir / history_dir
        self.history_dir.mkdir(exist_ok=True)

    def _get_history_file(self, server_id: int) -> Path:
        return self.history_dir / f"server_{server_id}_history.jsonl"

    def save_message(self, server_id: int, message_data: Dict) -> None:
        if "timestamp" not in message_data:
            message_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        history_file = self._get_history_file(server_id)
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(message_data) + "\n")

    def get_messages(self, server_id: int, limit: Optional[int] = 100) -> List[Dict]:
        history_file = self._get_history_file(server_id)
        if not history_file.exists():
            return []
        messages: List[Dict] = []
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            message = json.loads(line)
                            messages.append(message)
                        except json.JSONDecodeError:
                            continue
        except IOError:
            return []
        if limit and len(messages) > limit:
            messages = messages[-limit:]
        return messages

    def clear_history(self, server_id: int) -> bool:
        history_file = self._get_history_file(server_id)
        if history_file.exists():
            history_file.unlink()
            return True
        return False

    def get_message_count(self, server_id: int) -> int:
        history_file = self._get_history_file(server_id)
        if not history_file.exists():
            return 0
        count = 0
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        count += 1
        except IOError:
            return 0
        return count


message_history = MessageHistory()


