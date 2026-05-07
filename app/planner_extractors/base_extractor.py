"""
BaseParamExtractor — abstract base for all intent-specific extractors.

Each extractor is responsible for deterministically mapping semantic context
to structured parameters needed to execute a specific tool.

CONTRACT — NO LLM CALLS:
  - extract(semantic_context) receives immutable SemanticContext
  - returns dict of tool parameters
  - must NEVER call LLM
  - must NEVER parse raw query text
  - must NEVER call services, repositories, or external APIs
  - must NEVER access the database
  - must be deterministic (same input → same output always)
  
RESPONSIBILITIES:
  - Extract relevant fields from semantic context
  - Derive deterministic fields (e.g., travel_day from travel_date)
  - Map semantic values to tool-specific parameter names
  - Handle None/missing values gracefully
  - Return {} on any failure (never raise)

FUTURE:
  - Adding CHECK_PNR_STATUS: create new extractor, no changes needed here
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.nlp.semantic_schema import SemanticContext


class BaseParamExtractor(ABC):
    """Abstract base class for all deterministic intent-specific parameter extractors."""

    @abstractmethod
    def extract(self, semantic_context: "SemanticContext") -> dict:
        """
        Map immutable semantic context to tool-specific parameters.
        
        Deterministic mapping only. NO LLM calls. NO query parsing.

        Args:
            semantic_context: Immutable SemanticContext with extracted entities
                            (app.nlp.semantic_schema.SemanticContext)

        Returns:
            Dict of tool-specific parameters, ready for PlanStep.params.
            Returns {} if extraction fails or if context is None/empty.
        
        Examples:
            For SEARCH_TRAINS intent:
            - Input: SemanticContext(origin_station=ConfidenceValue("NDLS"), ...)
            - Output: {"origin_station": "NDLS", "travel_day": "monday", ...}
        """
        ...
