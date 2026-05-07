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
        self.client = NTESClient(timeout=15, retries=3)

    def _day_abbrev_from_travel_day(self, travel_day: Optional[str]) -> Optional[str]:
        """
        Convert full weekday ("monday") to abbreviation used by many railway APIs ("Mon").
        Returns None if travel_day is falsy or unrecognised.
        """
        if not travel_day:
            return None
        day = travel_day.strip().lower()
        mapping = {
            "monday": "Mon",
            "tuesday": "Tue",
            "wednesday": "Wed",
            "thursday": "Thu",
            "friday": "Fri",
            "saturday": "Sat",
            "sunday": "Sun",
        }
        return mapping.get(day)

    def _matches_day_of_run(self, day_of_run: Any, travel_day: Optional[str]) -> bool:
        """
        Determine whether a train runs on the given travel_day based on a raw DayOfRun field.
        Handles:
          - "Daily"
          - "Mon" / "Tue" etc
          - "Mon,Wed,Fri" (comma/space separated)
          - lists/tuples of day strings
        """
        if day_of_run is None:
            return False

        # Daily always matches
        if isinstance(day_of_run, str) and day_of_run.strip().lower() == "daily":
            return True

        wanted = self._day_abbrev_from_travel_day(travel_day)
        if not wanted:
            # If caller didn't provide travel_day, don't filter by day.
            return True

        # Normalise day_of_run into a list of tokens like ["Mon", "Wed"]
        tokens: List[str] = []
        if isinstance(day_of_run, (list, tuple, set)):
            tokens = [str(x).strip() for x in day_of_run if str(x).strip()]
        else:
            s = str(day_of_run).strip()
            if s:
                # split on commas first; fallback to whitespace
                parts = [p.strip() for p in s.split(",")]
                if len(parts) == 1:
                    parts = [p.strip() for p in s.split()]
                tokens = [p for p in parts if p]

        wanted_lower = wanted.lower()
        return any(tok.lower() == wanted_lower for tok in tokens)

    def _normalize_train(self, raw: dict) -> dict:
        day_of_run = raw.get("DayOfRun", "")
        days_of_run = [str(day_of_run).strip()] if day_of_run is not None else []
        return {
            "train_number": raw.get("TrainNumber"),
            "train_name": raw.get("TrainName"),
            "departure_time": raw.get("DepTimeFrom"),
            "arrival_time": raw.get("ArrTimeTo"),
            "duration": raw.get("TravelTime"),
            "days_of_run": days_of_run,
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
        travel_day: str,
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
            if self._matches_day_of_run(t.get("DayOfRun"), travel_day)
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

    def check_pnr_status(self, pnr_number: str) -> Dict[str, Any]:
        """
        Fetch PNR status from external NTES API.
        """
        logger.info("RailwayAPIClient.check_pnr_status called for pnr=%s", pnr_number)
        return self.client.pnr_status(pnr_number)
