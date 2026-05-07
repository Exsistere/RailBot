"""
TrainService — Facade over RailwayAPIClient.

External railway APIs are the source of truth for train data.
No local caching of train search results — per architectural decision:
train schedules change frequently and railway data is externally managed.

Reusable by:
  - SearchTrainsTool (via ToolFactory injection)
  - Future GET /trains API endpoint

Contains NO LangGraph logic. Never imports from app.graph or app.tools.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.services.railway_api_client import RailwayAPIClient

logger = logging.getLogger(__name__)


class TrainService:
    """
    Orchestrates train search via the external Railway API.

    External API is always the source of truth — results are not cached locally.
    All dependencies are injected — no module-level singletons.
    """

    def __init__(self, api_client: RailwayAPIClient) -> None:
        self._api = api_client

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search_trains(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search trains with the given parameters via the external Railway API.

        Args:
            params: Dict with keys matching the tool input schema:
                    origin_station, destination_station, travel_date,
                    train_class (optional), quota (optional)

        Returns:
            Dict matching LLD output schema: { trains, total, query_echoed }
        """
        origin: str = params.get("origin_station", "")
        destination: str = params.get("destination_station", "")
        travel_date: str = params.get("travel_date", "")
        train_class: Optional[str] = params.get("train_class")
        quota: Optional[str] = params.get("quota")

        if not all([origin, destination, travel_date]):
            raise ValueError(
                f"Missing required params: origin={origin!r}, "
                f"destination={destination!r}, travel_date={travel_date!r}"
            )

        logger.info(
            "TrainService: calling Railway API [%s → %s on %s]",
            origin, destination, travel_date,
        )
        return self._api.search_trains(
            origin_station=origin,
            destination_station=destination,
            travel_date=travel_date,
            train_class=train_class,
            quota=quota,
        )
