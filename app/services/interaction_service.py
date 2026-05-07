"""
InteractionService — thin facade for Logger Node compatibility.

Delegates all persistence logic to LoggingService.

Maintains the same public interface (log_interaction) that Logger Node
expects — zero changes required in logger_node.py or workflow.py.

Contains NO LangGraph logic. Never imports from app.graph or app.tools.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.services.logging_service import LoggingService

logger = logging.getLogger(__name__)


class InteractionService:
    """
    Thin wrapper over LoggingService, preserving the Logger Node contract.

    Logger Node calls self._interaction_service.log_interaction(state_dict).
    This service extracts the relevant fields and delegates to LoggingService.
    """

    def __init__(self, logging_service: LoggingService) -> None:
        self._logging_service = logging_service

    # ------------------------------------------------------------------
    # Public interface — unchanged contract for Logger Node
    # ------------------------------------------------------------------

    def log_interaction(self, state: Dict[str, Any]) -> None:
        """
        Persist the full interaction record from a completed GraphState.

        Extracts fields from state and delegates to LoggingService.
        Failures are suppressed — logging must never affect user experience.
        """
        intents = state.get("intents", [])
        top_intent = intents[0]["type"] if intents else None

        try:
            self._logging_service.log_interaction(
                conversation_id=state.get("conversation_id", ""),
                user_id=state.get("user_id", ""),
                query=state.get("user_query", ""),
                final_response=state.get("final_response"),
                is_safe=state.get("is_safe"),
                top_intent=top_intent,
                tool_results=state.get("tool_results", {}),
            )
        except Exception as exc:
            logger.error("InteractionService.log_interaction failed silently: %s", exc)
