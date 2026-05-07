"""
InteractionRepository — DB access for the interactions table.

Records one LangGraph execution trace per user query.
High-level observability: query, final_response, is_safe, top_intent.
NO plan/tool_results JSONB blobs — those live in tool_executions.

Falls back to file logging if DB is unavailable.
Failures are NEVER surfaced to the caller (fire-and-forget — LLD C5).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.db.base_repository import BaseRepository
from app.services.db.connection import DatabaseManager

logger = logging.getLogger(__name__)

_FALLBACK_LOG_PATH = os.getenv("INTERACTION_LOG_FILE", "logs/interactions.jsonl")


class InteractionRepository(BaseRepository):
    """Handles interactions table writes with file-log fallback."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def insert(
        self,
        conversation_id: str,
        user_id: str,
        query: str,
        final_response: Optional[str] = None,
        is_safe: Optional[bool] = None,
        top_intent: Optional[str] = None,
    ) -> Optional[str]:
        """
        Persist an interaction record.

        Returns the new interaction id (UUID str) for use as FK in
        tool_executions, or None on failure. Silently falls back to
        file log if DB is unavailable — never raises.
        """
        interaction_id = str(uuid.uuid4())
        record = {
            "id": interaction_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "query": query,
            "final_response": final_response,
            "is_safe": is_safe,
            "top_intent": top_intent,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            if self._db.is_available():
                self._write_to_db(record)
            else:
                self._write_to_file(record)
            return interaction_id
        except Exception as exc:
            logger.error("InteractionRepository: all logging paths failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal — DB path
    # ------------------------------------------------------------------

    def _write_to_db(self, record: Dict[str, Any]) -> None:
        conn = self._db.get_connection()
        self._execute(
            conn,
            """
            INSERT INTO interactions
                (id, conversation_id, user_id, query, final_response,
                 is_safe, top_intent, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record["id"],
                record["conversation_id"],
                record["user_id"],
                record["query"],
                record.get("final_response"),
                record.get("is_safe"),
                record.get("top_intent"),
                datetime.now(timezone.utc),
            ),
        )
        logger.debug(
            "Interaction %s logged to PostgreSQL for user %s",
            record["id"], record.get("user_id"),
        )

    # ------------------------------------------------------------------
    # Internal — file fallback path
    # ------------------------------------------------------------------

    def _write_to_file(self, record: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(_FALLBACK_LOG_PATH), exist_ok=True)
        entry = {**record, "log_path": "file_fallback"}
        with open(_FALLBACK_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        logger.debug(
            "Interaction logged to file fallback for user %s", record.get("user_id")
        )
