"""
MessageRepository — DB access for the messages table.

Stores pure conversational turns (user/assistant). Used to reconstruct
message_history in GraphState for context-aware LLM responses.

NO graph execution metadata belongs here.
Repositories contain ONLY DB logic. No service/tool/graph calls.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.db.base_repository import BaseRepository
from app.services.db.connection import DatabaseManager

logger = logging.getLogger(__name__)


class MessageRepository(BaseRepository):
    """Handles messages table operations."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def insert(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Persist a single message turn.

        Args:
            conversation_id: FK to conversations.id
            role: "user" or "assistant"
            content: message text

        Returns the created row dict, or None if DB unavailable.
        """
        if not self._db.is_available():
            logger.warning("MessageRepository: DB unavailable — skipping message persist")
            return None

        message_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        try:
            conn = self._db.get_connection()
            self._execute(
                conn,
                """
                INSERT INTO messages (id, conversation_id, role, content, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (message_id, conversation_id, role, content, now),
            )
            return {
                "id": message_id,
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "created_at": now.isoformat(),
            }
        except Exception as exc:
            logger.error("MessageRepository.insert failed: %s", exc)
            return None

    def get_recent(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Fetch the most recent messages for a conversation, oldest-first.

        Returns a list of dicts suitable for injection into GraphState
        as message_history.
        """
        if not self._db.is_available():
            return []
        try:
            conn = self._db.get_connection()
            # Fetch newest `limit` rows, then reverse to chronological order
            rows = self._fetch_all(
                conn,
                """
                SELECT id, conversation_id, role, content, created_at
                FROM (
                    SELECT id, conversation_id, role, content, created_at
                    FROM messages
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                ) sub
                ORDER BY created_at ASC
                """,
                (conversation_id, limit),
            )
            # Normalise timestamps to ISO strings for GraphState
            return [
                {
                    "role": r["role"],
                    "content": r["content"],
                    "created_at": (
                        r["created_at"].isoformat()
                        if hasattr(r["created_at"], "isoformat")
                        else str(r["created_at"])
                    ),
                }
                for r in rows
            ]
        except Exception as exc:
            logger.error("MessageRepository.get_recent failed: %s", exc)
            return []
