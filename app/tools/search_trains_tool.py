"""
SearchTrainsTool — concrete tool for the "search_trains" plan step.

Reads structured parameters from plan[current_step_index].params
(populated by Planner). Does NOT re-parse user_query.

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
        Ensure required params exist in the active plan step.
        Raises ToolValidationError on any validation failure.
        """
        params = self._get_params(state)

        origin = params.get("origin_station", "").strip()
        destination = params.get("destination_station", "").strip()
        travel_date = params.get("travel_date", "").strip()

        if not origin:
            raise ToolValidationError("origin_station is required but missing")
        if not destination:
            raise ToolValidationError("destination_station is required but missing")
        if not travel_date:
            raise ToolValidationError("travel_date is required but missing")

        train_class: Optional[str] = params.get("train_class")
        if train_class and train_class not in _VALID_CLASSES:
            raise ToolValidationError(
                f"Invalid train_class '{train_class}'. Valid: {_VALID_CLASSES}"
            )

        quota: Optional[str] = params.get("quota")
        if quota and quota not in _VALID_QUOTAS:
            raise ToolValidationError(
                f"Invalid quota '{quota}'. Valid: {_VALID_QUOTAS}"
            )

    def _fetch_data(self, state: GraphState) -> Dict[str, Any]:
        """
        Delegate to TrainService which handles cache + API call.
        Returns the raw LLD-compliant response dict.
        """
        params = self._get_params(state)
        logger.info(
            "SearchTrainsTool fetching: %s → %s on %s",
            params.get("origin_station"),
            params.get("destination_station"),
            params.get("travel_date"),
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

    # _persist is inherited as no-op — search is idempotent/read-only.
    # Caching is handled inside TrainService, not here.

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _get_params(self, state: GraphState) -> Dict[str, Any]:
        """
        Read params from the active PlanStep.

        Falls back to empty dict if plan or index is missing —
        _validate will then raise ToolValidationError cleanly.
        """
        plan = state.get("plan", [])
        index = state.get("current_step_index", 0)
        if plan and 0 <= index < len(plan):
            return plan[index].get("params", {})
        return {}
