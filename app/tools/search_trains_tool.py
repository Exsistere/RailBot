"""
SearchTrainsTool — concrete tool for the "search_trains" plan step.

DUAL MODE:
  1. LEGACY: Reads structured parameters from plan[current_step_index].params
  2. NEW: Reads from shared_context for collaborative workflows

The tool automatically prefers shared_context if available, falls back to params.

Registered in TOOL_REGISTRY under the key "search_trains".
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.models.state import GraphState
from app.services.train_service import TrainService
from app.tools.base_tool import BaseTool, ToolValidationError

logger = logging.getLogger(__name__)

# Valid train class codes per LLD
_VALID_CLASSES = {"SL", "3A", "2A", "1A", "CC", "EC", "2S"}
# Valid quota codes per LLD
_VALID_QUOTAS = {"GN", "TQ", "LD", "PT"}


class SearchTrainsTool(BaseTool):
    """
    Searches available trains between two stations on a given date.

    DUAL MODE (backward compatible):
      - If shared_context available: read from shared_context
      - Otherwise: read from plan[i].params (legacy)

    Dependencies injected by ToolFactory:
        train_service: TrainService
    """

    def __init__(self, train_service: TrainService) -> None:
        self._train_service = train_service

    # ------------------------------------------------------------------
    # Template method implementations
    # ------------------------------------------------------------------

    def _validate(self, state: GraphState) -> None:
        """
        Ensure required params exist (either in shared_context or plan[i].params).
        Raises ToolValidationError on any validation failure.
        """
        origin, destination, travel_date = self._get_railway_params(state)

        if not origin:
            raise ToolValidationError("origin_station is required but missing")
        if not destination:
            raise ToolValidationError("destination_station is required but missing")
        if not travel_date:
            raise ToolValidationError("travel_date is required but missing")

        train_class: Optional[str] = self._get_train_class(state)
        if train_class and train_class not in _VALID_CLASSES:
            raise ToolValidationError(
                f"Invalid train_class '{train_class}'. Valid: {_VALID_CLASSES}"
            )

        quota: Optional[str] = self._get_quota(state)
        if quota and quota not in _VALID_QUOTAS:
            raise ToolValidationError(
                f"Invalid quota '{quota}'. Valid: {_VALID_QUOTAS}"
            )

    def _fetch_data(self, state: GraphState) -> Dict[str, Any]:
        """
        Delegate to TrainService which handles cache + API call.
        Returns the raw LLD-compliant response dict.
        """
        origin, destination, travel_date = self._get_railway_params(state)
        train_class = self._get_train_class(state)
        quota = self._get_quota(state)

        params = {
            "origin_station": origin,
            "destination_station": destination,
            "travel_date": travel_date,
            "train_class": train_class,
            "quota": quota or "GN",
        }

        logger.info(
            "SearchTrainsTool fetching: %s → %s on %s (class=%s quota=%s)",
            origin,
            destination,
            travel_date,
            train_class,
            quota,
        )
        return self._train_service.search_trains(params)

    def _process(self, raw_data: Dict[str, Any], state: GraphState) -> Dict[str, Any]:
        """
        Normalise the raw API response.
        Currently returns as-is since RailwayAPIClient already conforms to LLD schema.
        This method is the extension point for future normalisation logic.
        """
        return {
            "trains": raw_data.get("trains", []),
            "total": raw_data.get("total", 0),
            "query_echoed": raw_data.get("query_echoed", {}),
        }

    def _get_memory_updates(self, result: Any, state: GraphState) -> Dict[str, Any]:
        """
        Return memory updates for SharedContext enrichment.

        For search_trains, we don't typically update shared_context memory
        since the train search doesn't enrich other tools' understanding.
        In future multi-tool workflows, this could return useful metadata.

        Returns:
            Empty dict (no memory updates) for search_trains
        """
        return {}

    # ------------------------------------------------------------------
    # Parameter extraction — dual mode support
    # ------------------------------------------------------------------

    def _get_railway_params(self, state: GraphState) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract railway parameters from shared_context (new) or plan params (legacy).

        Returns: (origin, destination, travel_date)
        """
        shared_context = state.get("shared_context")

        # NEW: Try shared_context first
        if shared_context:
            origin = shared_context.origin_station
            destination = shared_context.destination_station
            travel_date = shared_context.travel_date
            if origin and destination and travel_date:
                logger.debug("SearchTrainsTool: using shared_context for params")
                return (origin, destination, travel_date)

        # LEGACY: Fall back to plan[i].params
        params = self._get_params_from_plan(state)
        origin = params.get("origin_station", "").strip() or None
        destination = params.get("destination_station", "").strip() or None
        travel_date = params.get("travel_date", "").strip() or None

        if origin or destination or travel_date:
            logger.debug("SearchTrainsTool: using plan params (legacy mode)")

        return (origin, destination, travel_date)

    def _get_train_class(self, state: GraphState) -> Optional[str]:
        """Get train class from shared_context or plan params."""
        shared_context = state.get("shared_context")
        if shared_context and shared_context.train_class:
            return shared_context.train_class

        params = self._get_params_from_plan(state)
        return params.get("train_class")

    def _get_quota(self, state: GraphState) -> Optional[str]:
        """Get quota from shared_context or plan params."""
        shared_context = state.get("shared_context")
        if shared_context and shared_context.quota:
            return shared_context.quota

        params = self._get_params_from_plan(state)
        return params.get("quota")

    def _get_params_from_plan(self, state: GraphState) -> Dict[str, Any]:
        """
        Read params from the active PlanStep (legacy mode).

        Falls back to empty dict if plan or index is missing.
        """
        plan = state.get("plan", [])
        index = state.get("current_step_index", 0)
        if plan and 0 <= index < len(plan):
            return plan[index].get("params", {})
        return {}
