from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class ChatState:
    """Manages the chat state and history."""
    chat_history: List[Dict[str, str]] = field(default_factory=list)

    def add_message(self, role: str, content: str):
        """Adds a message to the chat history."""
        self.chat_history.append({"role": role, "content": content})