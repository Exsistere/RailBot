"""
Semantic context schema with immutable frozen dataclasses.

SemanticContext represents the canonical, normalized set of railway entities
extracted from a user query. It is immutable after creation to prevent
accidental mutations downstream.

OWNERSHIP CONTRACT:
- SemanticContext is WRITE-ONCE and READ-MANY.
- Only Planner may create/populate semantic_context.
- All downstream consumers (extractors, tools, services) treat it as read-only.
- Attempting to mutate semantic_context after creation will raise FrozenInstanceError.

VERSIONING:
- schema_version field enables future evolution (v1 → v2 → v3) without silent breaking changes.
- Current version: "v1"

CONFIDENCE METADATA:
- Optional confidence scores wrap extracted values in ConfidenceValue.
- confidence = 1.0 means full certainty (default for non-LLM-sourced values).
- confidence < 1.0 means LLM uncertainty; downstream can optionally handle it.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ConfidenceValue:
    """
    Value wrapper with optional LLM confidence score.
    
    Immutable. Confidence defaults to 1.0 (full certainty).
    """
    value: Optional[str]
    confidence: float = 1.0


@dataclass(frozen=True)
class SemanticContext:
    """
    Immutable canonical semantic context extracted from user query.
    
    All fields are optional (can be None). Values are normalized and canonical.
    Confidence metadata is optional (wrapped in ConfidenceValue if LLM provided it).
    
    INVARIANTS:
    - Immutable after creation (frozen dataclass).
    - Never mutated by downstream consumers.
    - Values are canonical (e.g., station codes are uppercase, dates are ISO).
    - Schema version included for future evolution.
    
    DERIVED FIELDS:
    - weekday_from_date: Deterministically derived from travel_date, not from LLM.
      Set by Planner after semantic extraction.
    """
    
    schema_version: str = "v1"
    
    # Origin/destination stations
    origin_station: Optional[ConfidenceValue] = None
    destination_station: Optional[ConfidenceValue] = None
    
    # Travel date (ISO format: YYYY-MM-DD)
    travel_date: Optional[ConfidenceValue] = None
    
    # Day mentioned explicitly by user (e.g., "next Monday" → "monday")
    day_mentioned: Optional[str] = None
    
    # PNR booking reference
    pnr_number: Optional[ConfidenceValue] = None
    
    # Specific train number
    train_number: Optional[ConfidenceValue] = None
    
    # Train class (SL, 3A, 2A, 1A, CC, EC, 2S)
    train_class: Optional[ConfidenceValue] = None
    
    # Reservation quota (GN, TQ, PT, LD)
    quota: Optional[ConfidenceValue] = None
    
    # Number of passengers (if mentioned)
    passenger_count: Optional[ConfidenceValue] = None
    
    # Weekday derived deterministically from travel_date
    # NOT extracted by LLM. Computed in Planner after semantic extraction.
    weekday_from_date: Optional[str] = None
    
    @classmethod
    def empty(cls) -> "SemanticContext":
        """
        Factory method: Create an empty SemanticContext with all fields None.
        
        Useful for initialization or representing failed extraction.
        """
        return cls(
            schema_version="v1",
            origin_station=None,
            destination_station=None,
            travel_date=None,
            day_mentioned=None,
            pnr_number=None,
            train_number=None,
            train_class=None,
            quota=None,
            passenger_count=None,
            weekday_from_date=None,
        )
    
    def with_weekday(self, weekday: str) -> "SemanticContext":
        """
        Immutable update: Create new SemanticContext with weekday_from_date set.
        
        Used after semantic extraction to add deterministically derived weekday.
        Returns new immutable copy; original is unchanged.
        
        Args:
            weekday: String day name (monday, tuesday, ..., sunday)
        
        Returns:
            New SemanticContext with weekday_from_date set
        """
        return SemanticContext(
            schema_version=self.schema_version,
            origin_station=self.origin_station,
            destination_station=self.destination_station,
            travel_date=self.travel_date,
            day_mentioned=self.day_mentioned,
            pnr_number=self.pnr_number,
            train_number=self.train_number,
            train_class=self.train_class,
            quota=self.quota,
            passenger_count=self.passenger_count,
            weekday_from_date=weekday,
        )
