"""
SearchTrainsParamExtractor — deterministic parameter mapper for SEARCH_TRAINS intent.

REFACTORED: No longer calls LLM. Instead:
1. Receives immutable SemanticContext from Planner
2. Extracts SEARCH_TRAINS-specific fields from semantic context
3. Derives deterministic fields (travel_day from travel_date)
4. Returns tool-specific parameters

RESPONSIBILITIES:
- Extract: origin_station, destination_station, travel_date from semantic context
- Derive: travel_day (deterministically from travel_date)
- Handle: None/empty values gracefully
- NO LLM calls, NO query parsing, NO normalization (already done)

Adding new intent extractor:
  1. Create: app/planner_extractors/<intent>_extractor.py
  2. Implement: extract(semantic_context) → dict
  3. Register in registry.py
  
Zero changes to planner.py required.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.planner_extractors.base_extractor import BaseParamExtractor
from app.nlp.date_utils import derive_weekday, is_valid_iso_date

if TYPE_CHECKING:
    from app.nlp.semantic_schema import SemanticContext

logger = logging.getLogger(__name__)


class SearchTrainsParamExtractor(BaseParamExtractor):
    """
    Deterministically maps SemanticContext to SEARCH_TRAINS tool parameters.

    Extracts: origin_station, destination_station, travel_date, travel_day,
              train_class, quota
    
    NO LLM calls. Pure deterministic mapping from semantic context.
    """

    def extract(self, semantic_context: "SemanticContext") -> dict:
        """
        Extract SEARCH_TRAINS parameters from semantic context.
        
        Deterministic mapping: same semantic context → same params always.
        
        Args:
            semantic_context: Immutable SemanticContext (from Planner)
        
        Returns:
            Dict with keys: origin_station, destination_station, travel_date,
                           travel_day, train_class, quota
            Returns empty dict if semantic_context is None or empty.
        """
        try:
            if not semantic_context:
                logger.warning("SearchTrainsParamExtractor: null semantic_context")
                return {}
            
            # Extract origin station (ConfidenceValue.value or None)
            origin = (
                semantic_context.origin_station.value
                if semantic_context.origin_station
                else None
            )
            
            # Extract destination station
            dest = (
                semantic_context.destination_station.value
                if semantic_context.destination_station
                else None
            )
            
            # Extract travel date (ISO format)
            date_str = (
                semantic_context.travel_date.value
                if semantic_context.travel_date
                else None
            )
            
            # Derive travel_day deterministically from date
            travel_day = None
            if date_str and is_valid_iso_date(date_str):
                # First: check if already pre-computed in semantic context
                if semantic_context.weekday_from_date:
                    travel_day = semantic_context.weekday_from_date
                else:
                    # Derive it now
                    try:
                        travel_day = derive_weekday(date_str)
                    except ValueError:
                        travel_day = None
            
            # Extract train class
            train_class = (
                semantic_context.train_class.value
                if semantic_context.train_class
                else None
            )
            
            # Extract quota (default to GN if not specified)
            quota = (
                semantic_context.quota.value
                if semantic_context.quota
                else "GN"
            )
            
            result = {
                "origin_station": origin or "",
                "destination_station": dest or "",
                "travel_date": date_str or "",
                "travel_day": travel_day,
                "train_class": train_class,
                "quota": quota,
            }
            
            logger.debug(f"SearchTrainsParamExtractor: extracted params={result}")
            return result
        
        except Exception as exc:
            logger.error(
                f"SearchTrainsParamExtractor: extraction failed — returning empty dict: {exc}"
            )
            return {}

