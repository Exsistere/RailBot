"""
ConversationRepository — DB access for the conversations table.

Manages chat session grouping. Provides get_or_create semantics used
by the API layer before each graph invocation.

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


class ConversationRepository(BaseRepository):
    """Handles conversations table operations."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Create a new conversation for a user.
        Returns the created row dict, or None if DB unavailable.
        """
        if not self._db.is_available():
            logger.warning("ConversationRepository: DB unavailable — cannot create conversation")
            return None

        conversation_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        try:
            conn = self._db.get_connection()
            self._execute(
                conn,
                "INSERT INTO conversations (id, user_id, created_at) VALUES (%s, %s, %s)",
                (conversation_id, user_id, now),
            )
            return {"id": conversation_id, "user_id": user_id, "created_at": now.isoformat()}
        except Exception as exc:
            logger.error("ConversationRepository.create failed: %s", exc)
            return None

    def get_latest_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the most recent conversation for a user.
        Returns None if no conversation exists or DB is unavailable.
        """
        if not self._db.is_available():
            return None
        try:
            conn = self._db.get_connection()
            return self._fetch_one(
                conn,
                """
                SELECT id, user_id, created_at
                FROM conversations
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
        except Exception as exc:
            logger.error("ConversationRepository.get_latest_for_user failed: %s", exc)
            return None

    def get_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a conversation by its primary key."""
        if not self._db.is_available():
            return None
        try:
            conn = self._db.get_connection()
            return self._fetch_one(
                conn,
                "SELECT id, user_id, created_at FROM conversations WHERE id = %s",
                (conversation_id,),
            )
        except Exception as exc:
            logger.error("ConversationRepository.get_by_id failed: %s", exc)
            return None

    def list_for_user(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent conversations for a user, newest first."""
        if not self._db.is_available():
            return []
        try:
            conn = self._db.get_connection()
            return self._fetch_all(
                conn,
                """
                SELECT id, user_id, created_at
                FROM conversations
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
        except Exception as exc:
            logger.error("ConversationRepository.list_for_user failed: %s", exc)
            return []
