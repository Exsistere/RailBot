"""
ConversationService — orchestrates conversation and message persistence.

Responsibilities:
  - get_or_create_conversation(user_id)  → conversation_id
  - load_recent_messages(conversation_id) → message_history for GraphState
  - save_turn(conversation_id, user_query, assistant_response)

This service is called exclusively from the API layer (routes.py),
BEFORE and AFTER graph invocation.

The graph itself MUST remain stateless regarding DB access.
Nodes read message_history from GraphState but never write to DB directly.

This service:
  - Orchestrates ConversationRepository + MessageRepository
  - MUST NOT contain FastAPI route logic
  - MUST NOT contain LangGraph orchestration
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.db.conversation_repository import ConversationRepository
from app.services.db.message_repository import MessageRepository

logger = logging.getLogger(__name__)

# Maximum number of recent messages injected into GraphState per turn.
_MESSAGE_HISTORY_LIMIT = 10


class ConversationService:
    """Facade over ConversationRepository and MessageRepository."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
    ) -> None:
        self._conv_repo = conversation_repo
        self._msg_repo = message_repo

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_or_create_conversation(self, user_id: str) -> str:
        """
        Return the latest conversation id for a user, creating one if none exists.

        Returns a UUID string. Falls back to a transient (non-persisted) UUID
        if DB is unavailable, so the graph can still run.
        """
        existing = self._conv_repo.get_latest_for_user(user_id)
        if existing:
            conversation_id = str(existing["id"])
            logger.debug("ConversationService: reusing conversation %s", conversation_id)
            return conversation_id

        created = self._conv_repo.create(user_id)
        if created:
            conversation_id = str(created["id"])
            logger.info("ConversationService: created conversation %s", conversation_id)
            return conversation_id

        # DB unavailable — generate a transient ID so the graph can run
        import uuid
        fallback_id = str(uuid.uuid4())
        logger.warning(
            "ConversationService: DB unavailable — using transient conversation_id %s",
            fallback_id,
        )
        return fallback_id

    def load_recent_messages(
        self,
        conversation_id: str,
        limit: int = _MESSAGE_HISTORY_LIMIT,
    ) -> List[Dict[str, Any]]:
        """
        Load the most recent `limit` messages for injection into GraphState.

        Returns a list of {"role": ..., "content": ..., "created_at": ...} dicts,
        ordered oldest-first (chronological for LLM context).
        Returns [] if DB unavailable or no history exists.
        """
        messages = self._msg_repo.get_recent(conversation_id, limit=limit)
        logger.debug(
            "ConversationService: loaded %d messages for conversation %s",
            len(messages), conversation_id,
        )
        return messages

    def save_turn(
        self,
        conversation_id: str,
        user_content: str,
        assistant_content: str,
    ) -> None:
        """
        Persist one complete conversational turn (user + assistant message).

        Called AFTER the graph returns, from the API route.
        Failures are logged and suppressed — must never affect user experience.
        """
        try:
            self._msg_repo.insert(conversation_id, "user", user_content)
            self._msg_repo.insert(conversation_id, "assistant", assistant_content)
            logger.debug(
                "ConversationService: saved turn for conversation %s", conversation_id
            )
        except Exception as exc:
            logger.error("ConversationService.save_turn failed (suppressed): %s", exc)
