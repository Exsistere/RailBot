"""
BaseTool — Abstract base class using the Template Method pattern.

Every concrete tool MUST:
  1. Inherit from BaseTool
  2. Implement _validate, _fetch_data, _process
  3. Optionally override _persist (default: no-op)

Tools MUST NOT:
  - Raise exceptions to the graph (all caught inside execute())
  - Call other nodes
  - Contain orchestration logic
  - Re-parse user_query (use plan[i].params set by Planner)

execute() always returns the standardised tool_result envelope:
    { "status": "SUCCESS"|"FAILED", "data": any, "error": str|None }
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from app.models.state import GraphState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception for validation failures (tool-internal only)
# ---------------------------------------------------------------------------

class ToolValidationError(ValueError):
    """Raised by _validate() when required params are missing or invalid."""


# ---------------------------------------------------------------------------
# BaseTool
# ---------------------------------------------------------------------------

class BaseTool(ABC):
    """
    Abstract tool base class.

    Template Method pattern: execute() defines the fixed algorithm;
    subclasses override the hook methods.
    """

    # ------------------------------------------------------------------
    # Public entry point — called by tool_node.py
    # ------------------------------------------------------------------

    def execute(self, state: GraphState) -> Dict[str, Any]:
        """
        Execute the tool and return a standardised result envelope.

        Returns:
            {
                "status": "SUCCESS" | "FAILED",
                "data": <tool output> | None,
                "error": None | "<error message>"
            }

        Never raises — all exceptions are caught and wrapped.
        """
        try:
            self._validate(state)
            raw_data = self._fetch_data(state)
            processed = self._process(raw_data, state)
            self._persist(processed, state)
            return {
                "status": "SUCCESS",
                "data": processed,
                "error": None,
            }
        except ToolValidationError as exc:
            logger.warning("%s validation failed: %s", self.__class__.__name__, exc)
            return {
                "status": "FAILED",
                "data": None,
                "error": f"Validation error: {exc}",
            }
        except Exception as exc:
            logger.error("%s execution failed: %s", self.__class__.__name__, exc, exc_info=True)
            return {
                "status": "FAILED",
                "data": None,
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Hook methods — subclasses MUST implement these
    # ------------------------------------------------------------------

    @abstractmethod
    def _validate(self, state: GraphState) -> None:
        """
        Validate that the state contains the required parameters.
        Raise ToolValidationError on any missing/invalid input.
        """

    @abstractmethod
    def _fetch_data(self, state: GraphState) -> Any:
        """
        Fetch raw data from DB, cache, or external API.
        Return the raw response for further processing.
        """

    @abstractmethod
    def _process(self, raw_data: Any, state: GraphState) -> Any:
        """
        Normalise and transform raw_data into the canonical output schema.
        Return the processed result dict.
        """

    # ------------------------------------------------------------------
    # Optional hook — override only if tool has write side-effects
    # ------------------------------------------------------------------

    def _persist(self, result: Any, state: GraphState) -> None:
        """
        Persist result to DB / cache if needed.
        Default: no-op. Override in tools with write side-effects.
        """
