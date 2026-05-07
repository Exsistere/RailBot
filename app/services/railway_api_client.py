"""
RailwayAPIClient — mock external railway search API.

Returns realistic structured data matching the LLD output schema exactly.
Replace this class with a real HTTP client (httpx / requests) without
touching any other layer — just swap the implementation of `search_trains`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from ntes import NTESClient
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static mock data — 5 realistic trains, Surat (ST) → Mumbai CST (CSTM)
# ---------------------------------------------------------------------------

_MOCK_TRAINS: List[Dict[str, Any]] = [
    {
        "train_number": "12009",
        "train_name": "Mumbai Shatabdi",
        "departure_time": "06:05",
        "arrival_time": "10:35",
        "duration": "4h 30m",
        "days_of_run": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "availability": {"class": "CC", "status": "AVAILABLE", "fare_inr": 720},
    },
    {
        "train_number": "12010",
        "train_name": "Mumbai Shatabdi (Return)",
        "departure_time": "08:10",
        "arrival_time": "12:55",
        "duration": "4h 45m",
        "days_of_run": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "availability": {"class": "CC", "status": "WL-4", "fare_inr": 720},
    },
    {
        "train_number": "19019",
        "train_name": "Saurashtra Mail",
        "departure_time": "14:25",
        "arrival_time": "19:30",
        "duration": "5h 05m",
        "days_of_run": ["Mon", "Wed", "Fri", "Sun"],
        "availability": {"class": "SL", "status": "AVAILABLE", "fare_inr": 275},
    },
    {
        "train_number": "22955",
        "train_name": "Kutch Express",
        "departure_time": "22:00",
        "arrival_time": "04:45",
        "duration": "6h 45m",
        "days_of_run": ["Tue", "Thu", "Sat"],
        "availability": {"class": "3A", "status": "AVAILABLE", "fare_inr": 490},
    },
    {
        "train_number": "16505",
        "train_name": "Gandhidham Express",
        "departure_time": "18:50",
        "arrival_time": "00:10",
        "duration": "5h 20m",
        "days_of_run": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "availability": {"class": "2A", "status": "REGRET", "fare_inr": 950},
    },
]


class RailwayAPIClient:
    """
    Simulates an external Railway Search API.

    All method signatures are intentionally close to a real HTTP API
    so that swapping to a real client requires minimal changes.
    """
    def __init__(self) -> None:
        self.client = NTESClient()            

    def _normalize_train(self, raw: dict) -> dict:
        return {
            "train_number": raw.get("TrainNumber"),
            "train_name": raw.get("TrainName"),
            "departure_time": raw.get("DepTimeFrom"),
            "arrival_time": raw.get("ArrTimeTo"),
            "duration": raw.get("TravelTime"),
            "days_of_run": [raw.get("DayOfRun", "")],
            "availability": {
                "class": raw.get("ClassOfTravel") or "N/A",
                "status": "Available",
                "fare_inr": "N/A",
            },
        }

    def search_trains(
        self,
        origin_station: str,
        destination_station: str,
        travel_date: str,
        train_class: Optional[str] = None,
        quota: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search available trains between two stations on a given date.

        Returns a dict matching the LLD output schema:
            { trains: [...], total: int, query_echoed: {...} }
        """
        logger.info(
            "RailwayAPIClient.search_trains called: %s → %s on %s (class=%s, quota=%s)",
            origin_station,
            destination_station,
            travel_date,
            train_class,
            quota,
        )

        # Filter by class if specified
        trains = _MOCK_TRAINS
        trains = self.client.trains_between(origin_station, destination_station)
        # if train_class:
        #     trains = [
        #         t for t in trains
        #         if t["availability"]["class"] == train_class
        #     ]
        #     # If no match for requested class, return all with class overridden
        #     if not trains:
        #         trains = [
        #             {**t, "availability": {**t["availability"], "class": train_class}}
        #             for t in _MOCK_TRAINS
        #         ]
        normalized_trains = [
            self._normalize_train(t)
            for t in trains["Trains"]
        ]
        result = {
            "trains": normalized_trains,
            "total": len(normalized_trains),
            "query_echoed": {
                "origin": origin_station,
                "destination": destination_station,
                "date": travel_date,
                "class": train_class,
                "quota": quota or "GN",
            },
        }

        logger.info("RailwayAPIClient returning %d trains", result["total"])
        return result
