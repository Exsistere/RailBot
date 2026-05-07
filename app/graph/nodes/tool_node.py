"""
Node [T] — Generic Tool Node.

Executes whatever tool is mapped to the current plan step via TOOL_REGISTRY.
Contains NO hardcoded tool names. Adding a new tool requires zero changes here.

SHARED CONTEXT INTEGRATION:
  1. Execute tool → get { status, data, memory_updates, ... }
  2. Merge memory_updates into shared_context via merge_shared_context
  3. Store tool_results (execution metadata only, not rendering logic)
  4. Update plan step status

Owned state mutations: tool_results, plan[i].status, plan[i].result, shared_context

Tool execution contract:
  1. Read step_name from plan[current_step_index]
  2. Set plan[i].status = "RUNNING"
  3. Create tool via ToolFactory (dependency injection)
  4. Call tool.execute(state) → returns { status, data, memory_updates, metadata, ... }
  5. Merge memory_updates into shared_context
  6. Write tool_results[step_name] = envelope
  7. Set plan[i].status = "COMPLETED" or "FAILED"
  8. Set plan[i].result = envelope.data
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.models.state import GraphState, PlanStep
from app.shared_context import merge_shared_context

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

    NEW FLOW (Shared Context Integration):
      1. Execute tool
      2. Extract memory_updates from tool result
      3. Merge memory_updates into shared_context
      4. Store tool_results
      5. Update plan step status

    Returns a partial state dict.
    Mutates ONLY: tool_results, plan[i].status, plan[i].result, shared_context
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
        return _build_result(state, plan, index, step_name, envelope)

    # 3 — Execute tool (never raises — BaseTool.execute() catches all)
    envelope: Dict[str, Any] = tool.execute(state)

    logger.info(
        "ToolNode: step '%s' finished with status=%s",
        step_name,
        envelope.get("status"),
    )

    # 4 — Extract and merge memory_updates into shared_context
    memory_updates = envelope.get("memory_updates")
    updated_shared_context = state.get("shared_context")
    
    if memory_updates and updated_shared_context:
        try:
            from app.shared_context.models import MemoryUpdate
            update_obj = MemoryUpdate(**memory_updates) if isinstance(memory_updates, dict) else memory_updates
            updated_shared_context = merge_shared_context(updated_shared_context, update_obj)
            logger.debug(f"ToolNode: merged memory_updates into shared_context")
        except Exception as exc:
            logger.warning(f"ToolNode: memory merge failed: {exc}")

    # 5 — Write results and update plan step status
    final_status = "COMPLETED" if envelope.get("status") == "SUCCESS" else "FAILED"
    return _build_result(state, plan, index, step_name, envelope, final_status, updated_shared_context)


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
    state: GraphState,
    plan: List[PlanStep],
    index: int,
    step_name: str,
    envelope: Dict[str, Any],
    final_status: str = "FAILED",
    shared_context: Optional[Any] = None,
) -> Dict:
    """Build the state patch after tool execution."""
    updated_plan = list(plan)
    step = dict(updated_plan[index])
    step["status"] = final_status
    step["result"] = envelope.get("data")
    updated_plan[index] = PlanStep(**step)

    tool_results = dict({})
    tool_results[step_name] = envelope

    result_dict = {
        "plan": updated_plan,
        "tool_results": tool_results,
    }
    
    if shared_context is not None:
        result_dict["shared_context"] = shared_context

    return result_dict


def _fail_step(state: GraphState, error_msg: str) -> Dict:
    """Build a FAILED state patch when tool cannot even be created."""
    plan: List[PlanStep] = state.get("plan", [])
    index: int = state.get("current_step_index", 0)
    if not plan or index >= len(plan):
        return {}
    step_name = plan[index].get("step", "unknown")
    envelope = {"status": "FAILED", "data": None, "error": error_msg}
    return _build_result(state, plan, index, step_name, envelope, "FAILED")
