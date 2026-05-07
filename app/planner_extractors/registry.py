"""
PARAM_EXTRACTOR_REGISTRY — maps intent types to extractor classes.

Adding a new intent extractor requires ONLY:
  1. Implement the extractor in a new file (subclass BaseParamExtractor)
  2. Import it here and add one entry to PARAM_EXTRACTOR_REGISTRY

Zero changes to planner.py are required.

Registry invariant:
  Only intents that require parameter extraction need an entry here.
  SMALL_TALK and other no-op intents do NOT need an extractor —
  they produce empty plans and are handled directly by the Responder.
"""

from __future__ import annotations

from typing import Dict, Type

from app.planner_extractors.base_extractor import BaseParamExtractor
from app.planner_extractors.check_pnr_extractor import CheckPNRParamExtractor
from app.planner_extractors.search_trains_extractor import SearchTrainsParamExtractor

# Future extractors imported here:
# from app.planner_extractors.check_pnr_extractor import CheckPNRParamExtractor

PARAM_EXTRACTOR_REGISTRY: Dict[str, Type[BaseParamExtractor]] = {
    "SEARCH_TRAINS": SearchTrainsParamExtractor,
    "CHECK_PNR_STATUS": CheckPNRParamExtractor,
    # "SEAT_AVAILABILITY": SeatAvailabilityParamExtractor,
}
