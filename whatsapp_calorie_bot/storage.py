"""SQLite storage and caching for messages and inference results."""

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("Storage initialized at %s", db_path)

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                msg_id TEXT PRIMARY KEY,
                timestamp TEXT,
                sender TEXT,
                text TEXT,
                has_media INTEGER,
                media_paths TEXT,
                media_missing INTEGER,
                raw_line TEXT
            );
            CREATE TABLE IF NOT EXISTS inference (
                msg_id TEXT PRIMARY KEY,
                classification_json TEXT,
                estimation_json TEXT,
                model_text TEXT,
                model_vision TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (msg_id) REFERENCES messages(msg_id)
            );
        """)
        self.conn.commit()

    def store_messages(self, messages: list[dict]) -> None:
        """Insert or update parsed messages."""
        for msg in messages:
            self.conn.execute(
                """INSERT OR REPLACE INTO messages
                   (msg_id, timestamp, sender, text, has_media, media_paths, media_missing, raw_line)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg["msg_id"],
                    msg["timestamp"],
                    msg["sender"],
                    msg["text"],
                    int(msg.get("has_media", False)),
                    json.dumps(msg.get("media_paths", [])),
                    int(msg.get("media_missing", False)),
                    msg.get("raw_line", ""),
                ),
            )
        self.conn.commit()
        logger.info("Stored %d messages in DB.", len(messages))

    def store_inference(self, msg_id: str, result: dict) -> None:
        """Store inference result for a message."""
        self.conn.execute(
            """INSERT OR REPLACE INTO inference
               (msg_id, classification_json, estimation_json, model_text, model_vision)
               VALUES (?, ?, ?, ?, ?)""",
            (
                msg_id,
                json.dumps(result.get("classification")),
                json.dumps(result.get("estimation")),
                result.get("model_text", ""),
                result.get("model_vision", ""),
            ),
        )
        self.conn.commit()

    def get_inference(self, msg_id: str) -> dict | None:
        """Get cached inference result for a message, or None."""
        row = self.conn.execute(
            "SELECT * FROM inference WHERE msg_id = ?", (msg_id,)
        ).fetchone()
        if not row:
            return None
        result = {}
        if row["classification_json"]:
            result["classification"] = json.loads(row["classification_json"])
        if row["estimation_json"]:
            result["estimation"] = json.loads(row["estimation_json"])
        return result

    def close(self) -> None:
        self.conn.close()
