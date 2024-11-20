import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4


class LoggerType(Enum):
    SQLITE = "sqlite"
    FILE = "file"


@dataclass
class ChatLoggerConfig:
    logger_type: LoggerType = LoggerType.SQLITE
    db_name: str = "logs.db"
    log_file: str = "runtime.log"
    log_level: int = logging.INFO


class ChatLogger:
    """Asynchronous and thread-safe chat logger supporting SQLite and file-based logging."""

    def __init__(self, config: ChatLoggerConfig):
        self.config = config
        self.session_id: Optional[str] = None
        self.is_logging = False

        # Asynchronous queue for logging events
        self._log_queue: asyncio.Queue = asyncio.Queue()

        # Configure file logger if needed
        if self.config.logger_type == LoggerType.FILE:
            self._configure_file_logger()

    def _configure_file_logger(self) -> None:
        """Configures the file logger with appropriate settings."""
        logging.basicConfig(
            filename=self.config.log_file,
            level=self.config.log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

    async def start(self) -> str:
        """Starts a new logging session."""
        self.session_id = str(uuid4())
        self.is_logging = True

        # Initialize SQLite database if necessary
        if self.config.logger_type == LoggerType.SQLITE:
            await self._init_sqlite_db()

        # Start the log processing loop
        asyncio.create_task(self._process_logs())

        return self.session_id

    async def stop(self) -> None:
        """Stops the logging session and the log processing loop."""
        self.is_logging = False
        await self._log_queue.join()  # Wait until the queue is fully processed
        self.session_id = None

    async def log_chat(
        self, sender: str, receiver: str, message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Logs a chat message asynchronously.

        Args:
            sender: Name/ID of the message sender.
            receiver: Name/ID of the message receiver.
            message: The content of the message.
            metadata: Optional metadata about the message.
        """
        if not self.is_logging:
            return

        log_entry = {
            "session_id": self.session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "sender": sender,
            "receiver": receiver,
            "message": message,
            "metadata": metadata,
        }
        await self._log_queue.put(log_entry)

    async def get_logs(
        self, session_id: Optional[str] = None, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves logs asynchronously.

        Args:
            session_id: Optional session ID to filter logs.
            start_time: Optional start time for filtering.
            end_time: Optional end time for filtering.

        Returns:
            A list of log entries.
        """
        if self.config.logger_type == LoggerType.SQLITE:
            return await self._get_sqlite_logs(session_id, start_time, end_time)

        return await self._get_file_logs(session_id, start_time, end_time)

    async def _process_logs(self) -> None:
        """Processes log entries from the queue asynchronously."""
        while self.is_logging or not self._log_queue.empty():
            log_entry = await self._log_queue.get()

            match self.config.logger_type:
                case LoggerType.SQLITE:
                    await self._log_to_sqlite(log_entry)
                case LoggerType.FILE:
                    await self._log_to_file(log_entry)

            self._log_queue.task_done()

    async def _init_sqlite_db(self) -> None:
        """Initializes the SQLite database asynchronously."""
        conn = await self._connect_sqlite()
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    timestamp TEXT,
                    sender TEXT,
                    receiver TEXT,
                    message TEXT,
                    metadata TEXT
                )
                """
            )
        await conn.commit()
        await conn.close()

    async def _log_to_sqlite(self, log_entry: Dict[str, Any]) -> None:
        """Logs a message to SQLite asynchronously."""
        conn = await self._connect_sqlite()
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO chat_logs (session_id, timestamp, sender, receiver, message, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    log_entry["session_id"],
                    log_entry["timestamp"],
                    log_entry["sender"],
                    log_entry["receiver"],
                    log_entry["message"],
                    json.dumps(log_entry.get("metadata")),
                ),
            )
        await conn.commit()
        await conn.close()

    async def _log_to_file(self, log_entry: Dict[str, Any]) -> None:
        """Logs a message to a file asynchronously."""
        if not hasattr(self, "logger"):
            raise RuntimeError("File logger not configured.")

        self.logger.info(json.dumps(log_entry))

    async def _get_sqlite_logs(
        self, session_id: Optional[str], start_time: Optional[datetime], end_time: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Retrieves logs from SQLite asynchronously."""
        conn = await self._connect_sqlite()
        async with conn.cursor() as cursor:
            query = "SELECT * FROM chat_logs WHERE 1=1"
            params = []

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())

            await cursor.execute(query, params)
            rows = await cursor.fetchall()

        await conn.close()
        return [dict(zip(["id", "session_id", "timestamp", "sender", "receiver", "message", "metadata"], row)) for row in rows]

    async def _get_file_logs(
        self, session_id: Optional[str], start_time: Optional[datetime], end_time: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Retrieves logs from a file asynchronously."""
        logs = []
        if not Path(self.config.log_file).exists():
            return logs

        async with aiofiles.open(self.config.log_file, "r") as f:
            async for line in f:
                log_entry = json.loads(line.split(" - ")[-1])

                if session_id and log_entry["session_id"] != session_id:
                    continue

                entry_time = datetime.fromisoformat(log_entry["timestamp"])
                if start_time and entry_time < start_time:
                    continue
                if end_time and entry_time > end_time:
                    continue

                logs.append(log_entry)

        return logs

    async def _connect_sqlite(self) -> sqlite3.Connection:
        """Creates an asynchronous SQLite connection."""
        return await sqlite3.connect(self.config.db_name)