"""
Node [T] — Generic Tool Node.

Executes whatever tool is mapped to the current plan step via TOOL_REGISTRY.
Contains NO hardcoded tool names. Adding a new tool requires zero changes here.

Owned state mutations: tool_results, plan[i].status, plan[i].result

Tool execution contract:
  1. Read step_name from plan[current_step_index]
  2. Set plan[i].status = "RUNNING"
  3. Create tool via ToolFactory (dependency injection)
  4. Call tool.execute(state) → returns { status, data, error } envelope
  5. Write tool_results[step_name] = envelope
  6. Set plan[i].status = "COMPLETED" or "FAILED"
  7. Set plan[i].result = envelope.data
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.models.state import GraphState, PlanStep

logger = logging.getLogger(__name__)

# _tool_factory is injected at app startup via set_tool_factory()
# This avoids module-level singletons while keeping node signature clean.
_tool_factory = None


def set_tool_factory(factory) -> None:
    """
    Inject the ToolFactory instance at application startup.
    Called once from app/graph/workflow.py during graph compilation.
    """
    global _tool_factory
    _tool_factory = factory


def tool_node(state: GraphState) -> Dict:
    """
    Generic tool executor — resolves and runs the current plan step's tool.

    Returns a partial state dict.
    Mutates ONLY: tool_results, plan[i].status, plan[i].result
    """
    if _tool_factory is None:
        logger.error("ToolNode: ToolFactory not initialised — call set_tool_factory() at startup")
        return _fail_step(state, "ToolFactory not initialised")

    plan: List[PlanStep] = state.get("plan", [])
    index: int = state.get("current_step_index", 0)

    # Guard: invalid index
    if not plan or index < 0 or index >= len(plan):
        logger.error("ToolNode: invalid current_step_index=%d (plan length=%d)", index, len(plan))
        return {}

    current_step: PlanStep = plan[index]
    step_name: str = current_step.get("step", "")

    # 1 — Mark step as RUNNING
    updated_plan = _set_step_status(plan, index, "RUNNING")

    logger.info("ToolNode: executing step '%s' (index=%d)", step_name, index)

    # 2 — Create tool via factory (resolves tool class + injects services)
    try:
        tool = _tool_factory.create(step_name)
    except KeyError as exc:
        logger.error("ToolNode: %s", exc)
        envelope = {"status": "FAILED", "data": None, "error": str(exc)}
        return _build_result(plan, index, step_name, envelope)

    # 3 — Execute tool (never raises — BaseTool.execute() catches all)
    envelope: Dict[str, Any] = tool.execute(state)

    logger.info(
        "ToolNode: step '%s' finished with status=%s",
        step_name,
        envelope.get("status"),
    )

    # 4 — Write results and update plan step status
    final_status = "COMPLETED" if envelope.get("status") == "SUCCESS" else "FAILED"
    return _build_result(plan, index, step_name, envelope, final_status)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_step_status(
    plan: List[PlanStep],
    index: int,
    status: str,
) -> List[PlanStep]:
    updated = list(plan)
    step = dict(updated[index])
    step["status"] = status
    updated[index] = PlanStep(**step)
    return updated


def _build_result(
    plan: List[PlanStep],
    index: int,
    step_name: str,
    envelope: Dict[str, Any],
    final_status: str = "FAILED",
) -> Dict:
    """Build the state patch after tool execution."""
    updated_plan = list(plan)
    step = dict(updated_plan[index])
    step["status"] = final_status
    step["result"] = envelope.get("data")
    updated_plan[index] = PlanStep(**step)

    tool_results = dict({})
    tool_results[step_name] = envelope

    return {
        "plan": updated_plan,
        "tool_results": tool_results,
    }


def _fail_step(state: GraphState, error_msg: str) -> Dict:
    """Build a FAILED state patch when tool cannot even be created."""
    plan: List[PlanStep] = state.get("plan", [])
    index: int = state.get("current_step_index", 0)
    if not plan or index >= len(plan):
        return {}
    step_name = plan[index].get("step", "unknown")
    envelope = {"status": "FAILED", "data": None, "error": error_msg}
    return _build_result(plan, index, step_name, envelope, "FAILED")
