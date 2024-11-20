import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
import aioredis
from redis.commands.json.path import Path
from redis.commands.search.field import TextField, NumericField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

class ChatMemory:
    """A Redis-based chat memory for short-term context management using Redis Stack features."""

    def __init__(self, redis_url: str = "redis://localhost", max_messages: int = 100, ttl: int = 3600):
        """
        Initialize the ChatMemory with Redis Stack support.

        Args:
            redis_url: The Redis server URL.
            max_messages: The maximum number of messages to retain per session.
            ttl: Time-to-live for session keys, in seconds.
        """
        self.redis_url = redis_url
        self.max_messages = max_messages
        self.ttl = ttl
        self.redis = None

    async def connect(self) -> None:
        """Establish a connection to the Redis server and set up search indices."""
        self.redis = await aioredis.from_url(self.redis_url, decode_responses=True)
        
        # Create search index for chat sessions
        try:
            await self.redis.ft("chat-idx").info()
        except:
            # Define the index for chat sessions
            schema = (
                TextField("$.topic", as_name="topic"),
                TextField("$.messages[*].content", as_name="content"),
                NumericField("$.timestamp", as_name="timestamp")
            )
            
            await self.redis.ft("chat-idx").create_index(
                schema,
                definition=IndexDefinition(
                    prefix=["chat:"],
                    index_type=IndexType.JSON
                )
            )

    async def start_session(self, session_id: str, topic: str) -> None:
        """
        Start a new chat session using RedisJSON.

        Args:
            session_id: A unique identifier for the session.
            topic: The initial topic or focus of the session.
        """
        session_key = f"chat:{session_id}"
        
        # Initialize session using RedisJSON
        session_data = {
            "topic": topic,
            "start_time": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
            "messages": [],
            "timestamp": datetime.utcnow().timestamp()
        }
        
        await self.redis.json().set(session_key, Path.root_path(), session_data)
        await self.redis.expire(session_key, self.ttl)

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        """
        Add a message to the session using RedisJSON.

        Args:
            session_id: The session identifier.
            role: The role of the message sender (e.g., 'user', 'assistant').
            content: The message content.
        """
        session_key = f"chat:{session_id}"
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Append message using RedisJSON
        await self.redis.json().arrappend(session_key, "$.messages", message)
        
        # Update last_updated timestamp
        await self.redis.json().set(session_key, "$.last_updated", datetime.utcnow().isoformat())
        
        # Trim messages if exceeding max_messages
        messages_len = await self.redis.json().arrlen(session_key, "$.messages")
        if messages_len > self.max_messages:
            await self.redis.json().arrpop(session_key, "$.messages", 0)  # Remove oldest message

    async def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all messages for a session using RedisJSON.

        Args:
            session_id: The session identifier.

        Returns:
            List of message dictionaries.
        """
        session_key = f"chat:{session_id}"
        messages = await self.redis.json().get(session_key, "$.messages")
        return messages or []

    async def search_sessions(self, query: str) -> List[Dict[str, Any]]:
        """
        Search through chat sessions using RediSearch.

        Args:
            query: The search query string.

        Returns:
            List of matching session data.
        """
        # Use RediSearch to find matching sessions
        results = await self.redis.ft("chat-idx").search(
            f"@content:'{query}' | @topic:'{query}'"
        )
        
        return [doc.json for doc in results.docs]