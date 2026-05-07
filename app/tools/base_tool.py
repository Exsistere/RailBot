"""
BaseTool — Abstract base class using the Template Method pattern.

Every concrete tool MUST:
  1. Inherit from BaseTool
  2. Implement _validate, _fetch_data, _process
  3. Optionally override _persist (default: no-op)
  4. Optionally override _get_memory_updates (default: {})

Tools MUST NOT:
  - Raise exceptions to the graph (all caught inside execute())
  - Call other nodes
  - Contain orchestration logic
  - Re-parse user_query (use SharedContext or plan[i].params)

SHARED CONTEXT INTEGRATION:
  - Tools should read from state.shared_context when available
  - Tools should return memory_updates for tool_node to merge
  - Memory updates enable multi-tool workflows and context enrichment

execute() always returns the standardised tool_result envelope:
    {
        "status": "SUCCESS"|"FAILED",
        "data": <output>,
        "memory_updates": <dict>,
        "error": str|None,
        "metadata": <dict>
    }
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
                "memory_updates": {} | <dict>,
                "error": None | "<error message>",
                "metadata": {}
            }

        Never raises — all exceptions are caught and wrapped.
        """
        try:
            self._validate(state)
            raw_data = self._fetch_data(state)
            processed = self._process(raw_data, state)
            self._persist(processed, state)
            memory_updates = self._get_memory_updates(processed, state)
            return {
                "status": "SUCCESS",
                "data": processed,
                "memory_updates": memory_updates,
                "error": None,
                "metadata": {"tool": self.__class__.__name__},
            }
        except ToolValidationError as exc:
            logger.warning("%s validation failed: %s", self.__class__.__name__, exc)
            return {
                "status": "FAILED",
                "data": None,
                "memory_updates": {},
                "error": f"Validation error: {exc}",
                "metadata": {"tool": self.__class__.__name__},
            }
        except Exception as exc:
            logger.error("%s execution failed: %s", self.__class__.__name__, exc, exc_info=True)
            return {
                "status": "FAILED",
                "data": None,
                "memory_updates": {},
                "error": str(exc),
                "metadata": {"tool": self.__class__.__name__},
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
    # Optional hooks — override only when needed
    # ------------------------------------------------------------------

    def _persist(self, result: Any, state: GraphState) -> None:
        """
        Persist result to DB / cache if needed.
        Default: no-op. Override in tools with write side-effects.
        """

    def _get_memory_updates(self, result: Any, state: GraphState) -> Dict[str, Any]:
        """
        Return memory updates for SharedContext merging.

        Default: empty dict (no memory updates).
        Override in tools that enrich SharedContext.

        Returns:
            Dict matching MemoryUpdate fields (all fields optional)
            Example: {"train_number": "12345", "waitlist_detected": True}
        """
        return {}
