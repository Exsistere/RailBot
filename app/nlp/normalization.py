"""
Canonical normalization layer for semantic contexts.

Transforms raw extracted SemanticContext (from LLM) into canonical form:
- Station names → canonical codes
- Train classes → canonical abbreviations
- Quotas → canonical abbreviations
- Dates → ISO format validation
- Text → trimmed and normalized

All invalid/unresolved values → set to None (don't fail extraction).
"""

from typing import Dict, Optional
from app.nlp.semantic_schema import SemanticContext, ConfidenceValue
from app.nlp.date_utils import is_valid_iso_date
from app.nlp.station_resolver import (
    StationResolver,
    TrainClassResolver,
    QuotaResolver,
)


def canonicalize_semantic_context(
    context: SemanticContext,
    resolvers: Dict[str, object] = None
) -> SemanticContext:
    """
    Canonicalize a raw extracted semantic context.
    
    Applies normalization rules:
    1. Resolve station names → codes using StationResolver
    2. Resolve train class names → abbreviations using TrainClassResolver
    3. Resolve quota names → abbreviations using QuotaResolver
    4. Validate and normalize dates (must be ISO YYYY-MM-DD)
    5. Trim and normalize text fields
    6. Invalid values → set to None
    
    Args:
        context: Raw extracted SemanticContext (may contain unresolved values)
        resolvers: Dict with keys: 'station', 'train_class', 'quota'
                  Values are resolver instances (StationResolver, etc.)
                  If None, uses default resolvers (minimal normalization)
    
    Returns:
        New canonicalized SemanticContext with all values in canonical form
    
    Raises:
        Nothing. All normalization failures silently result in None values.
    """
    if resolvers is None:
        resolvers = {}
    
    station_resolver = resolvers.get("station")
    class_resolver = resolvers.get("train_class")
    quota_resolver = resolvers.get("quota")
    
    # Normalize origin station
    canonical_origin = None
    if context.origin_station:
        resolved = (
            station_resolver(context.origin_station.value)
            if station_resolver
            else context.origin_station.value
        )
        if resolved:
            canonical_origin = ConfidenceValue(
                value=resolved.upper(),
                confidence=context.origin_station.confidence
            )
    
    # Normalize destination station
    canonical_dest = None
    if context.destination_station:
        resolved = (
            station_resolver(context.destination_station.value)
            if station_resolver
            else context.destination_station.value
        )
        if resolved:
            canonical_dest = ConfidenceValue(
                value=resolved.upper(),
                confidence=context.destination_station.confidence
            )
    
    # Normalize and validate travel date
    canonical_date = None
    if context.travel_date and context.travel_date.value:
        if is_valid_iso_date(context.travel_date.value):
            canonical_date = context.travel_date
        # else: invalid date → set to None
    
    # Normalize day_mentioned (already should be lowercase from extraction)
    canonical_day_mentioned = None
    if context.day_mentioned:
        day_lower = context.day_mentioned.strip().lower()
        valid_days = {
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday"
        }
        if day_lower in valid_days:
            canonical_day_mentioned = day_lower
    
    # Normalize PNR number (uppercase, no spaces)
    canonical_pnr = None
    if context.pnr_number and context.pnr_number.value:
        pnr_cleaned = context.pnr_number.value.strip().upper()
        if pnr_cleaned:
            canonical_pnr = ConfidenceValue(
                value=pnr_cleaned,
                confidence=context.pnr_number.confidence
            )
    
    # Normalize train number (uppercase, no spaces)
    canonical_train_num = None
    if context.train_number and context.train_number.value:
        train_cleaned = context.train_number.value.strip().upper()
        if train_cleaned:
            canonical_train_num = ConfidenceValue(
                value=train_cleaned,
                confidence=context.train_number.confidence
            )
    
    # Normalize train class
    canonical_class = None
    if context.train_class:
        resolved = (
            class_resolver(context.train_class.value)
            if class_resolver
            else context.train_class.value
        )
        resolved_upper = None
        if resolved:
            candidate = resolved.upper()
            valid_classes = {"SL", "3A", "2A", "1A", "CC", "EC", "2S"}
            if candidate in valid_classes:
                resolved_upper = candidate
        if resolved_upper:
            canonical_class = ConfidenceValue(
                value=resolved_upper,
                confidence=context.train_class.confidence
            )
    
    # Normalize quota
    canonical_quota = None
    if context.quota:
        resolved = (
            quota_resolver(context.quota.value)
            if quota_resolver
            else context.quota.value
        )
        resolved_upper = None
        if resolved:
            candidate = resolved.upper()
            valid_quotas = {"GN", "TQ", "PT", "LD"}
            if candidate in valid_quotas:
                resolved_upper = candidate
        if resolved_upper:
            canonical_quota = ConfidenceValue(
                value=resolved_upper,
                confidence=context.quota.confidence
            )
    
    # Normalize passenger count (ensure it's numeric)
    canonical_pax = None
    if context.passenger_count and context.passenger_count.value:
        try:
            pax_int = int(context.passenger_count.value)
            if pax_int > 0:
                canonical_pax = ConfidenceValue(
                    value=str(pax_int),
                    confidence=context.passenger_count.confidence
                )
        except (ValueError, TypeError):
            pass  # Invalid passenger count → None
    
    # Create new canonicalized context (immutable copy)
    return SemanticContext(
        schema_version=context.schema_version,
        origin_station=canonical_origin,
        destination_station=canonical_dest,
        travel_date=canonical_date,
        day_mentioned=canonical_day_mentioned,
        pnr_number=canonical_pnr,
        train_number=canonical_train_num,
        train_class=canonical_class,
        quota=canonical_quota,
        passenger_count=canonical_pax,
        weekday_from_date=context.weekday_from_date,  # Already set or None
    )
