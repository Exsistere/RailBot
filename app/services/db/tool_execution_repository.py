"""
ToolExecutionRepository — DB access for the tool_executions table.

Records each tool invocation within a LangGraph execution.
This is the observability/debugging layer — per-tool traces.

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


class ToolExecutionRepository(BaseRepository):
    """Handles tool_executions table operations."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def insert(
        self,
        interaction_id: str,
        tool_name: str,
        status: str,
        error: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        input_payload: Optional[Dict[str, Any]] = None,
        output_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Persist a tool execution record.

        Args:
            interaction_id: FK to interactions.id (UUID)
            tool_name:       e.g. "search_trains"
            status:          "SUCCESS" or "FAILED"
            error:           error message if FAILED
            execution_time_ms: wall-clock duration
            input_payload:   optional JSONB — tool input params
            output_payload:  optional JSONB — tool result data

        Returns the new record id (UUID str), or None on failure.
        """
        if not self._db.is_available():
            logger.debug("ToolExecutionRepository: DB unavailable — skipping")
            return None

        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        try:
            conn = self._db.get_connection()
            self._execute(
                conn,
                """
                INSERT INTO tool_executions
                    (id, interaction_id, tool_name, status, error,
                     execution_time_ms, input_payload, output_payload, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                """,
                (
                    record_id,
                    interaction_id,
                    tool_name,
                    status,
                    error,
                    execution_time_ms,
                    self._to_json(input_payload) if input_payload is not None else None,
                    self._to_json(output_payload) if output_payload is not None else None,
                    now,
                ),
            )
            logger.debug(
                "ToolExecutionRepository: logged %s [%s] for interaction %s",
                tool_name, status, interaction_id,
            )
            return record_id
        except Exception as exc:
            logger.error("ToolExecutionRepository.insert failed: %s", exc)
            return None

    def get_for_interaction(self, interaction_id: str) -> List[Dict[str, Any]]:
        """Fetch all tool executions for a given interaction, ordered by created_at."""
        if not self._db.is_available():
            return []
        try:
            conn = self._db.get_connection()
            return self._fetch_all(
                conn,
                """
                SELECT id, interaction_id, tool_name, status, error,
                       execution_time_ms, created_at
                FROM tool_executions
                WHERE interaction_id = %s
                ORDER BY created_at ASC
                """,
                (interaction_id,),
            )
        except Exception as exc:
            logger.error("ToolExecutionRepository.get_for_interaction failed: %s", exc)
            return []
