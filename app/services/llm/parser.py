"""
LLM Output Parser — validates and sanitises LLM JSON responses.

Each node has a dedicated parse function that:
  1. Validates the JSON structure against the expected schema
  2. Applies type coercion and defaults for missing fields
  3. Returns a safe fallback on any parse failure

The graph MUST NOT crash on malformed LLM responses.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Guardrail parser
# ---------------------------------------------------------------------------

def parse_guardrail_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalise a guardrail LLM response.

    Expected:
        {"is_safe": bool, "attack_type": str | null}

    Fallback (fail closed):
        {"is_safe": False, "attack_type": "OTHER"}
    """
    try:
        is_safe = data.get("is_safe")
        attack_type = data.get("attack_type")

        # Type validation
        if not isinstance(is_safe, bool):
            logger.warning("Guardrail parser: is_safe is not bool (%r) — defaulting to unsafe", is_safe)
            return {"is_safe": False, "attack_type": "OTHER"}

        # Validate attack_type values
        valid_types = {"PROMPT_INJECTION", "JAILBREAK", "PII_LEAK", "HATE_SPEECH", "OTHER", None}
        if attack_type not in valid_types:
            logger.warning("Guardrail parser: unknown attack_type %r — normalising to OTHER", attack_type)
            attack_type = "OTHER" if not is_safe else None

        # Consistency: safe + attack_type set → override to safe
        if is_safe:
            attack_type = None

        return {"is_safe": is_safe, "attack_type": attack_type}

    except Exception as exc:
        logger.error("Guardrail parser: unexpected error — failing closed: %s", exc)
        return {"is_safe": False, "attack_type": "OTHER"}


# ---------------------------------------------------------------------------
# Intent classifier parser
# ---------------------------------------------------------------------------

_VALID_INTENTS = {"SEARCH_TRAINS", "SMALL_TALK", "UNKNOWN"}


def parse_intent_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate and normalise an intent classification LLM response.

    Expected:
        {"intents": [{"type": str, "confidence": float}, ...]}

    Fallback:
        [{"type": "UNKNOWN", "confidence": 1.0}]
    """
    try:
        intents_raw = data.get("intents", [])
        if not isinstance(intents_raw, list) or len(intents_raw) == 0:
            logger.warning("Intent parser: empty or invalid intents list — returning UNKNOWN")
            return [{"type": "UNKNOWN", "confidence": 1.0}]

        validated: List[Dict[str, Any]] = []
        for item in intents_raw:
            intent_type = item.get("type", "UNKNOWN")
            confidence = item.get("confidence", 0.5)

            # Normalise type
            if intent_type not in _VALID_INTENTS:
                logger.warning("Intent parser: unsupported intent type %r — skipping", intent_type)
                continue

            # Clamp confidence
            try:
                confidence = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                confidence = 0.5

            validated.append({"type": intent_type, "confidence": round(confidence, 2)})

        if not validated:
            return [{"type": "UNKNOWN", "confidence": 1.0}]

        # Sort by confidence DESC
        return sorted(validated, key=lambda x: x["confidence"], reverse=True)

    except Exception as exc:
        logger.error("Intent parser: unexpected error — returning UNKNOWN: %s", exc)
        return [{"type": "UNKNOWN", "confidence": 1.0}]


# ---------------------------------------------------------------------------
# Planner parser (parameter extraction)
# ---------------------------------------------------------------------------

def parse_planner_params(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalise planner parameter extraction response.

    Expected (SEARCH_TRAINS):
        {
            "origin_station": str,
            "destination_station": str,
            "travel_date": str,
            "train_class": str | null,
            "quota": str
        }

    Fallback:
        All fields set to empty string / None / "GN".
    """
    try:
        return {
            "origin_station": _str_or_default(data.get("origin_station"), ""),
            "destination_station": _str_or_default(data.get("destination_station"), ""),
            "travel_date": _str_or_default(data.get("travel_date"), ""),
            "train_class": data.get("train_class") if data.get("train_class") else None,
            "quota": _str_or_default(data.get("quota"), "GN"),
        }
    except Exception as exc:
        logger.error("Planner parser: unexpected error — returning empty params: %s", exc)
        return {
            "origin_station": "",
            "destination_station": "",
            "travel_date": "",
            "train_class": None,
            "quota": "GN",
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _str_or_default(value: Any, default: str) -> str:
    """Coerce a value to str, falling back to default on None or non-str."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    return str(value)


# ---------------------------------------------------------------------------
# Semantic extraction parser (NEW)
# ---------------------------------------------------------------------------

def parse_semantic_extraction(data: Dict[str, Any]):
    """
    Validate and parse semantic extraction LLM response.
    
    Converts LLM JSON output into app.nlp.semantic_schema.SemanticContext.
    
    Expected input (from LLM):
        {
            "origin_station": "station name or code",
            "destination_station": "station name or code",
            "travel_date": "date string (any format)",
            "day_mentioned": "day name if user mentioned",
            "pnr_number": "PNR reference",
            "train_number": "train number",
            "train_class": "class name",
            "quota": "quota name",
            "passenger_count": "number"
        }
    
    Returns:
        SemanticContext with ConfidenceValue-wrapped fields
    
    Note: Normalization (station code resolution, etc.) happens in
    canonicalize_semantic_context, not here.
    """
    from app.nlp.semantic_schema import SemanticContext, ConfidenceValue
    
    try:
        def _cv(raw: Any) -> Optional[ConfidenceValue]:
            """
            Accept either:
              - "NDLS"
              - {"value": "NDLS", "confidence": 0.82}
            """
            if raw is None:
                return None
            if isinstance(raw, dict):
                val = raw.get("value")
                conf = raw.get("confidence", 1.0)
                if val is None:
                    return None
                try:
                    conf_f = float(conf)
                except (TypeError, ValueError):
                    conf_f = 1.0
                conf_f = max(0.0, min(1.0, conf_f))
                return ConfidenceValue(value=str(val), confidence=conf_f)
            if isinstance(raw, str):
                val = raw.strip()
                return ConfidenceValue(value=val, confidence=1.0) if val else None
            # Coerce primitives (int/float) to string
            return ConfidenceValue(value=str(raw), confidence=1.0)
        
        origin = data.get("origin_station")
        dest = data.get("destination_station")
        date_str = data.get("travel_date")
        day_mentioned = data.get("day_mentioned")
        pnr = data.get("pnr_number")
        train_num = data.get("train_number")
        train_class = data.get("train_class")
        quota = data.get("quota")
        pax = data.get("passenger_count")
        
        # Create semantic context with extracted values
        return SemanticContext(
            schema_version="v1",
            origin_station=_cv(origin),
            destination_station=_cv(dest),
            travel_date=_cv(date_str),
            day_mentioned=str(day_mentioned).strip().lower() if day_mentioned else None,
            pnr_number=_cv(pnr),
            train_number=_cv(train_num),
            train_class=_cv(train_class),
            quota=_cv(quota),
            passenger_count=_cv(pax),
            weekday_from_date=None,  # Set later by Planner
        )
    
    except Exception as exc:
        logger.error(f"Semantic extraction parser: unexpected error — returning empty context: {exc}")
        return SemanticContext.empty()
