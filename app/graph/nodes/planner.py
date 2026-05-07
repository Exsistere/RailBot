"""
Node [P] — Planner Node.

Translates detected intents into a deterministic execution plan.

NEW FLOW (v2):
  1. Call SemanticExtractor.extract(query, intent) → ONE LLM call per query
  2. Canonicalize semantic context (normalize stations, classes, quotas)
  3. Derive deterministic fields (weekday from date)
  4. Store immutable semantic_context in state (WRITE-ONCE, READ-MANY)
  5. For each plan step: call intent-specific extractor with semantic_context (deterministic only)

The Planner is the ONLY node that:
  - Calls SemanticExtractor (ONE LLM call for all intents)
  - Creates/writes semantic_context
  - Creates PlanStep.params

All downstream nodes (tools, responder, etc.) read semantic_context as read-only.

BACKWARD COMPATIBILITY:
  - PlanStep.params format unchanged
  - Tool signatures unchanged
  - Workflow topology unchanged
  
FUTURE EXTENSIBILITY:
  - Adding CHECK_PNR_STATUS requires ONLY:
      1. New extractor + registry entry
      2. New tool implementation
    Zero changes to planner.py

Implementation:
  - Uses semantic extraction + intent-specific extractors (Strategy pattern)
  - Adding new intent requires:
      1. Add entry to _INTENT_TO_STEPS mapping
      2. Add extractor in planner_extractors/ + register in PARAM_EXTRACTOR_REGISTRY
      3. Implement tool + register in TOOL_REGISTRY
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.models.state import GraphState, Intent, PlanStep
from app.planner_extractors.registry import PARAM_EXTRACTOR_REGISTRY
from app.nlp import (
    SemanticExtractor,
    canonicalize_semantic_context,
    derive_weekday,
    SemanticContext,
)
from app.nlp.station_resolver import (
    StationResolver,
    TrainClassResolver,
    QuotaResolver,
    DEFAULT_STATION_MAPPING,
    DEFAULT_TRAIN_CLASS_MAPPING,
    DEFAULT_QUOTA_MAPPING,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent → plan step mapping
# ---------------------------------------------------------------------------

_INTENT_TO_STEPS: Dict[str, List[str]] = {
    "SEARCH_TRAINS": ["search_trains"],
    "SMALL_TALK":    [],   # empty plan → Responder handles directly
    # "CHECK_PNR_STATUS": ["check_pnr"],       ← future
    # "SEAT_AVAILABILITY": ["seat_availability"], ← future
}


def planner_node(
    state: GraphState,
    semantic_extractor: Optional[SemanticExtractor] = None
) -> Dict:
    """
    Build an execution plan from the top-ranked intent.
    
    NEW FLOW:
      1. Extract semantic context from query (ONE LLM call)
      2. Canonicalize semantic context
      3. Extract intent-specific parameters (deterministic only)
      4. Create execution plan

    Returns a partial state dict.
    Mutates: plan, current_step_index, semantic_context
    """
    intents: List[Intent] = state.get("intents", [])
    user_query: str = state.get("user_query", "")

    if not intents:
        logger.warning("Planner: no intents provided — producing empty plan")
        return {
            "plan": [],
            "current_step_index": 0,
            "semantic_context": None,
        }

    top_intent = intents[0]["type"]
    step_names = _INTENT_TO_STEPS.get(top_intent, [])

    # Log SMALL_TALK and UNKNOWN explicitly
    if top_intent == "SMALL_TALK":
        logger.info("Planner: SMALL_TALK intent — empty plan, Responder will handle")
        return {
            "plan": [],
            "current_step_index": 0,
            "semantic_context": None,
        }

    if not step_names:
        logger.warning("Planner: no steps mapped for intent '%s' — empty plan", top_intent)
        return {
            "plan": [],
            "current_step_index": 0,
            "semantic_context": None,
        }

    # =====================================================================
    # NEW: Semantic Extraction (ONE LLM call per query)
    # =====================================================================
    
    if semantic_extractor is None:
        logger.error("Planner: SemanticExtractor not injected — cannot extract semantics")
        return {
            "plan": [],
            "current_step_index": 0,
            "semantic_context": None,
        }
    
    # Extract semantic entities (ONE LLM call)
    semantic_context = semantic_extractor.extract(
        query=user_query,
        intent_hint=top_intent
    )
    logger.debug(f"Planner: semantic extraction result: {semantic_context}")
    
    # =====================================================================
    # Canonicalize semantic context
    # =====================================================================
    resolvers = {
        "station": StationResolver(DEFAULT_STATION_MAPPING),
        "train_class": TrainClassResolver(DEFAULT_TRAIN_CLASS_MAPPING),
        "quota": QuotaResolver(DEFAULT_QUOTA_MAPPING),
    }
    semantic_context = canonicalize_semantic_context(semantic_context, resolvers)
    logger.debug(f"Planner: canonicalized semantic context: {semantic_context}")
    
    # =====================================================================
    # Derive deterministic fields (weekday from date)
    # =====================================================================
    if (
        semantic_context.travel_date
        and semantic_context.travel_date.value
        and not semantic_context.weekday_from_date
    ):
        try:
            weekday = derive_weekday(semantic_context.travel_date.value)
            semantic_context = semantic_context.with_weekday(weekday)
            logger.debug(f"Planner: derived weekday: {weekday}")
        except ValueError as e:
            logger.warning(f"Planner: failed to derive weekday: {e}")
    
    # =====================================================================
    # Extract intent-specific parameters (deterministic only, NO LLM)
    # =====================================================================
    params = _extract_params(semantic_context, top_intent)
    logger.info(f"Planner: extracted intent-specific params={params} for intent={top_intent}")

    # =====================================================================
    # Create execution plan
    # =====================================================================
    plan: List[PlanStep] = [
        PlanStep(
            step=step_name,
            status="PENDING",
            result=None,
            params=params,
        )
        for step_name in step_names
    ]

    logger.info(f"Planner: produced plan with steps={[s['step'] for s in plan]}")
    
    return {
        "plan": plan,
        "current_step_index": 0,
        "semantic_context": semantic_context,
    }


# ---------------------------------------------------------------------------
# Slot extraction — deterministic intent-specific mapping
# ---------------------------------------------------------------------------

def _extract_params(
    semantic_context: SemanticContext,
    intent: str
) -> Dict[str, Any]:
    """
    Extract intent-specific parameters from semantic context (deterministic only).
    
    NO LLM calls. Pure deterministic mapping from canonical semantic context.

    Resolves the correct intent-specific extractor from registry.
    Falls back to {} if no extractor is registered.

    Args:
        semantic_context: Immutable canonical SemanticContext (from semantic extraction)
        intent: Intent type (e.g., "SEARCH_TRAINS")
    
    Returns:
        Dict of tool-specific parameters, ready for PlanStep.params
    """
    extractor_cls = PARAM_EXTRACTOR_REGISTRY.get(intent)

    if extractor_cls is None:
        logger.warning(
            f"Planner: no extractor registered for intent '{intent}' — using empty params"
        )
        return {}

    try:
        # Call extractor with semantic context (not query string)
        return extractor_cls().extract(semantic_context)
    except Exception as exc:
        logger.error(
            f"Planner: extractor {extractor_cls.__name__} raised unexpectedly "
            f"— returning empty params: {exc}"
        )
        return {}
