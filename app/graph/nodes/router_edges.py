"""
Router Edge Functions — conditional routing decisions.

These are PURE READ functions: they inspect state and return the
name of the next node. They do NOT mutate state.

Separation of concerns:
  - router_node.py: state mutation (index advancement, retry tracking)
  - THIS FILE: routing decisions (which node runs next)
"""

from __future__ import annotations

import logging
from typing import List

from app.models.state import GraphState, PlanStep
from app.tools.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Edge 1: After Guardrail Node
# ---------------------------------------------------------------------------

def route_after_guardrail(state: GraphState) -> str:
    """
    Route based on Guardrail output.

    Returns:
        "intent_classifier" — query is safe
        "logger"            — query is unsafe (skip all processing, log and terminate)
    """
    is_safe: bool = state.get("is_safe", False)
    if is_safe:
        logger.debug("GuardrailEdge → intent_classifier")
        return "intent_classifier"
    logger.debug("GuardrailEdge → logger (unsafe query, final_response already set)")
    return "logger"


# ---------------------------------------------------------------------------
# Edge 2: After Router Node (main dispatch loop)
# ---------------------------------------------------------------------------

def route_from_router(state: GraphState) -> str:
    """
    Decide the next node after router_node has updated state.

    Logic (pure read — router_node has already done mutations):
      1. If plan is empty → responder
      2. If current_step_index >= len(plan) → responder (plan complete)
      3. If plan[i].step in TOOL_REGISTRY → tool_node
      4. Otherwise → responder (unknown step, already marked FAILED by router_node)

    Returns:
        "tool_node" | "responder"
    """
    plan: List[PlanStep] = state.get("plan", [])
    index: int = state.get("current_step_index", 0)

    # Plan is empty or exhausted
    if not plan or index >= len(plan):
        logger.debug("RouterEdge → responder (plan empty or complete, index=%d)", index)
        return "responder"

    step_name: str = plan[index].get("step", "")
    step_status: str = plan[index].get("status", "PENDING")

    # Step is registered and ready to execute
    if step_name in TOOL_REGISTRY and step_status == "PENDING":
        logger.debug("RouterEdge → tool_node (step='%s')", step_name)
        return "tool_node"

    # Step was FAILED+exhausted (router_node already advanced index past this)
    # or any other non-dispatchable state → go to responder
    logger.debug(
        "RouterEdge → responder (step='%s', status='%s')",
        step_name,
        step_status,
    )
    return "responder"
