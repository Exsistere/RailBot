"""
LoggingService — orchestrates interaction and tool-execution persistence.

Responsibilities:
  - log_interaction(...) → writes to interactions table
  - log_tool_execution(...) → writes to tool_executions table

This service is the single entrypoint for all observability writes.
Called by InteractionService (which is injected into Logger Node).

This service:
  - Orchestrates InteractionRepository + ToolExecutionRepository
  - MUST NOT contain FastAPI route logic
  - MUST NOT contain LangGraph orchestration
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.db.interaction_repository import InteractionRepository
from app.services.db.tool_execution_repository import ToolExecutionRepository

logger = logging.getLogger(__name__)


class LoggingService:
    """
    Persists interaction traces and per-tool execution records.

    Failures are always suppressed — logging must never affect user experience.
    (LLD constraint C5 — idempotent logger)
    """

    def __init__(
        self,
        interaction_repo: InteractionRepository,
        tool_execution_repo: ToolExecutionRepository,
    ) -> None:
        self._interaction_repo = interaction_repo
        self._tool_execution_repo = tool_execution_repo

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def log_interaction(
        self,
        conversation_id: str,
        user_id: str,
        query: str,
        final_response: Optional[str] = None,
        is_safe: Optional[bool] = None,
        top_intent: Optional[str] = None,
        tool_results: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Persist a high-level interaction record and (optionally) per-tool traces.

        Args:
            conversation_id: FK to conversations.id
            user_id:         from GraphState.user_id
            query:           raw user query
            final_response:  assistant's response text
            is_safe:         guardrail result
            top_intent:      top intent type string e.g. "SEARCH_TRAINS"
            tool_results:    raw tool_results dict from GraphState (for tool_executions)

        Returns:
            interaction_id UUID string (used as FK for tool_executions), or None.
        """
        try:
            interaction_id = self._interaction_repo.insert(
                conversation_id=conversation_id,
                user_id=user_id,
                query=query,
                final_response=final_response,
                is_safe=is_safe,
                top_intent=top_intent,
            )
            if interaction_id and tool_results:
                self._log_tool_executions(interaction_id, tool_results)
            return interaction_id
        except Exception as exc:
            logger.error("LoggingService.log_interaction failed (suppressed): %s", exc)
            return None

    def log_tool_execution(
        self,
        interaction_id: str,
        tool_name: str,
        status: str,
        error: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        input_payload: Optional[Dict[str, Any]] = None,
        output_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist a single tool execution trace. Suppresses all failures."""
        try:
            self._tool_execution_repo.insert(
                interaction_id=interaction_id,
                tool_name=tool_name,
                status=status,
                error=error,
                execution_time_ms=execution_time_ms,
                input_payload=input_payload,
                output_payload=output_payload,
            )
        except Exception as exc:
            logger.error("LoggingService.log_tool_execution failed (suppressed): %s", exc)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _log_tool_executions(
        self,
        interaction_id: str,
        tool_results: Dict[str, Any],
    ) -> None:
        """
        Derive per-tool traces from the GraphState tool_results dict.

        tool_results format:
            { "search_trains": { "status": "SUCCESS"|"FAILED", "data": ..., "error": ... } }
        """
        for tool_name, result in tool_results.items():
            if not isinstance(result, dict):
                continue
            status = result.get("status", "FAILED")
            # Normalise to SUCCESS/FAILED constraint
            db_status = "SUCCESS" if status == "SUCCESS" else "FAILED"
            self.log_tool_execution(
                interaction_id=interaction_id,
                tool_name=tool_name,
                status=db_status,
                error=result.get("error"),
                output_payload=result.get("data"),
            )
