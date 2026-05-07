"""
Node [R] — Router Node (state mutation only).

Advances current_step_index and manages retry_counts after tool execution.
Pure deterministic logic — NO LLM calls, NO external I/O.

Owned state mutations: current_step_index, retry_counts

Separation of concerns:
  - This file: state mutation (what happened, update the index)
  - router_edges.py: routing decision (where to go next)

NEVER crashes — all edge cases handled with guard clauses.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from app.models.state import GraphState, PlanStep
from app.tools.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)

MAX_RETRIES: int = 1  # Per LLD spec


def router_node(state: GraphState) -> Dict:
    """
    Update current_step_index and retry_counts based on the outcome
    of the most recently executed tool step.

    Logic:
      - If no steps have run yet (first entry from Planner): no mutation needed.
        router_edges will dispatch to the first tool.
      - If the active step is COMPLETED: increment index (move forward).
      - If the active step is FAILED:
          * retries remaining → do NOT increment (re-dispatch same step)
          * retries exhausted → increment index (skip failed step)
      - If step is unknown (not in registry): mark FAILED, increment index.
      - If index out of bounds: guard-clamp (router_edges handles TERMINAL case).

    Returns a partial state dict.
    Mutates ONLY: current_step_index, retry_counts, plan[i].status (unknown step)
    """
    plan: List[PlanStep] = state.get("plan", [])
    index: int = state.get("current_step_index", 0)
    retry_counts: Dict[int, int] = dict(state.get("retry_counts", {}))  # copy

    # Guard: empty plan or index already beyond plan
    if not plan or index >= len(plan):
        logger.debug("Router: plan complete or empty — no index mutation")
        return {}

    current_step: PlanStep = plan[index]
    step_name: str = current_step.get("step", "")
    status: str = current_step.get("status", "PENDING")

    # ----------------------------------------------------------------
    # Case 1: Step is PENDING → first visit from Planner
    # No index change; router_edges will dispatch to tool.
    # ----------------------------------------------------------------
    if status == "PENDING":
        # Check if step is in registry; if not, mark FAILED immediately
        if step_name not in TOOL_REGISTRY:
            logger.warning(
                "Router: step '%s' not found in TOOL_REGISTRY — marking FAILED, skipping",
                step_name,
            )
            updated_plan = _update_plan_step(plan, index, status="FAILED")
            return {
                "plan": updated_plan,
                "current_step_index": index + 1,
                "retry_counts": retry_counts,
            }
        logger.debug("Router: step '%s' is PENDING — dispatching to tool", step_name)
        return {}

    # ----------------------------------------------------------------
    # Case 2: Step COMPLETED → advance index
    # ----------------------------------------------------------------
    if status == "COMPLETED":
        new_index = index + 1
        logger.info("Router: step '%s' COMPLETED — advancing index to %d", step_name, new_index)
        return {
            "current_step_index": new_index,
            "retry_counts": retry_counts,
        }

    # ----------------------------------------------------------------
    # Case 3: Step FAILED → check retry policy
    # ----------------------------------------------------------------
    if status == "FAILED":
        current_retries = retry_counts.get(index, 0)

        if current_retries < MAX_RETRIES:
            # Retry: increment retry count, reset status to PENDING
            retry_counts[index] = current_retries + 1
            updated_plan = _update_plan_step(plan, index, status="PENDING")
            logger.warning(
                "Router: step '%s' FAILED — retrying (attempt %d/%d)",
                step_name,
                retry_counts[index],
                MAX_RETRIES,
            )
            return {
                "plan": updated_plan,
                "retry_counts": retry_counts,
            }
        else:
            # Retries exhausted → skip step, advance index
            new_index = index + 1
            logger.warning(
                "Router: step '%s' FAILED — retries exhausted, advancing to index %d",
                step_name,
                new_index,
            )
            return {
                "current_step_index": new_index,
                "retry_counts": retry_counts,
            }

    # ----------------------------------------------------------------
    # Case 4: RUNNING or any unexpected status → treat as pending
    # (should not occur in normal flow)
    # ----------------------------------------------------------------
    logger.warning("Router: unexpected step status '%s' for step '%s'", status, step_name)
    return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update_plan_step(
    plan: List[PlanStep],
    index: int,
    **updates,
) -> List[PlanStep]:
    """Return a new plan list with the step at index updated."""
    updated = list(plan)
    step = dict(updated[index])
    step.update(updates)
    updated[index] = PlanStep(**step)
    return updated
