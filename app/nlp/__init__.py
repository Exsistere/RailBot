"""
NLP module for semantic extraction and entity recognition.

This module is the single source of truth for semantic understanding of user queries.
It provides immutable, canonical semantic contexts that feed deterministic intent-specific
parameter extraction.

Public API:
- SemanticContext: Immutable frozen dataclass with extracted railway entities
- ConfidenceValue: Optional confidence metadata wrapper
- SemanticExtractor: LLM-based entity extraction (one call per query)
- canonicalize_semantic_context: Normalizes extracted values to canonical forms
- derive_weekday: Deterministic weekday derivation from ISO date
- StationResolver, TrainClassResolver, QuotaResolver: Entity normalization
"""

from app.nlp.semantic_schema import (
    ConfidenceValue,
    SemanticContext,
)
from app.nlp.semantic_extractor import SemanticExtractor
from app.nlp.normalization import canonicalize_semantic_context
from app.nlp.date_utils import derive_weekday, is_valid_iso_date
from app.nlp.station_resolver import (
    StationResolver,
    TrainClassResolver,
    QuotaResolver,
)

__all__ = [
    "ConfidenceValue",
    "SemanticContext",
    "SemanticExtractor",
    "canonicalize_semantic_context",
    "derive_weekday",
    "is_valid_iso_date",
    "StationResolver",
    "TrainClassResolver",
    "QuotaResolver",
]
