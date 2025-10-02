#!/usr/bin/env python3
"""
Example usage of the message history functionality.

This script demonstrates how messages are saved and retrieved.
"""

from message_history import MessageHistory

# Create a message history instance
history = MessageHistory("example_history")

# Example: Save some messages to server 1
server_id = 1

messages = [
    {"type": "system", "event": "join", "username": "alice"},
    {"type": "message", "username": "alice", "text": "Hello everyone!"},
    {"type": "system", "event": "join", "username": "bob"},
    {"type": "message", "username": "bob", "text": "Hi Alice!"},
    {"type": "message", "username": "alice", "text": "How are you doing?"},
    {"type": "message", "username": "bob", "text": "I'm doing great, thanks!"},
    {"type": "system", "event": "leave", "username": "alice"},
]

print("Saving messages to server 1...")
for msg in messages:
    history.save_message(server_id, msg)
    print(f"Saved: {msg}")

print(f"\nTotal messages in server {server_id}: {history.get_message_count(server_id)}")

print("\nRetrieving all messages:")
all_messages = history.get_messages(server_id)
for i, msg in enumerate(all_messages, 1):
    print(f"{i}. [{msg.get('timestamp', 'N/A')}] {msg}")

print("\nRetrieving last 3 messages:")
recent_messages = history.get_messages(server_id, limit=3)
for i, msg in enumerate(recent_messages, 1):
    print(f"{i}. [{msg.get('timestamp', 'N/A')}] {msg}")

print("\nMessage history files are stored in the 'message_history' directory.")
print("Each server has its own file: server_{id}_history.jsonl")
print(f"Full path: {history.history_dir}")
