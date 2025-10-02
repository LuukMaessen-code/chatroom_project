import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class MessageHistory:
    """Handles saving and retrieving message history for chat rooms."""

    def __init__(self, history_dir: str = "message_history"):
        # Create path relative to this module's directory
        module_dir = Path(__file__).parent
        self.history_dir = module_dir / history_dir
        self.history_dir.mkdir(exist_ok=True)

    def _get_history_file(self, server_id: int) -> Path:
        """Get the history file path for a specific server."""
        return self.history_dir / f"server_{server_id}_history.jsonl"

    def save_message(self, server_id: int, message_data: Dict) -> None:
        """Save a message to the history file.

        Args:
            server_id: The server/room ID
            message_data: Dictionary containing message information
        """
        # Add timestamp if not present
        if "timestamp" not in message_data:
            message_data["timestamp"] = datetime.now(timezone.utc).isoformat()

        history_file = self._get_history_file(server_id)

        # Append message to JSONL file (one JSON object per line)
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(message_data) + "\n")

    def get_messages(self, server_id: int, limit: Optional[int] = 100) -> List[Dict]:
        """Retrieve message history for a server.

        Args:
            server_id: The server/room ID
            limit: Maximum number of messages to return (most recent first)

        Returns:
            List of message dictionaries, ordered from oldest to newest
        """
        history_file = self._get_history_file(server_id)

        if not history_file.exists():
            return []

        messages = []
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            message = json.loads(line)
                            messages.append(message)
                        except json.JSONDecodeError:
                            # Skip malformed lines
                            continue
        except IOError:
            return []

        # Return the most recent messages if limit is specified
        if limit and len(messages) > limit:
            messages = messages[-limit:]

        return messages

    def clear_history(self, server_id: int) -> bool:
        """Clear message history for a server.

        Args:
            server_id: The server/room ID

        Returns:
            True if history was cleared, False if no history existed
        """
        history_file = self._get_history_file(server_id)

        if history_file.exists():
            history_file.unlink()
            return True
        return False

    def get_message_count(self, server_id: int) -> int:
        """Get the total number of messages for a server.

        Args:
            server_id: The server/room ID

        Returns:
            Number of messages in history
        """
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


# Global instance
message_history = MessageHistory()
