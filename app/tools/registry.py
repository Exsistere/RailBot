"""
TOOL_REGISTRY and ToolFactory.

TOOL_REGISTRY: maps PlanStep.step keys → tool classes (Strategy pattern).
ToolFactory:   creates tool instances with injected service dependencies.

Adding a new tool requires ONLY:
  1. Implement NewTool(BaseTool) in its own file
  2. Add one entry to TOOL_REGISTRY below
  3. Pass required services in ToolFactory._build_kwargs()

Zero changes to: router, tool_node, workflow, any existing tool.
"""

from __future__ import annotations

import logging
from typing import Dict, Type

from app.tools.base_tool import BaseTool
from app.tools.check_pnr_tool import CheckPNRTool
from app.tools.faq_rag_tool import FAQRAGTool
from app.tools.search_trains_tool import SearchTrainsTool

# Future tools imported here:
# from app.tools.check_pnr_tool import CheckPNRTool
# from app.tools.book_ticket_tool import BookTicketTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TOOL_REGISTRY — the single source of truth for step → tool mapping.
#
# INVARIANT: every key here MUST match a PlanStep.step value that the
# Planner can produce. Planner and Registry must stay in sync.
# ---------------------------------------------------------------------------

TOOL_REGISTRY: Dict[str, Type[BaseTool]] = {
    "search_trains": SearchTrainsTool,
    "check_pnr_status": CheckPNRTool,
    "faq_rag": FAQRAGTool,
    # "book_ticket":  BookTicketTool,  ← future: add here only
}


# ---------------------------------------------------------------------------
# ToolFactory — Dependency Injection container for tools
# ---------------------------------------------------------------------------

class ToolFactory:
    """
    Creates tool instances with the correct service dependencies injected.

    Usage:
        factory = ToolFactory(train_service=..., interaction_service=...)
        tool = factory.create("search_trains")
        result = tool.execute(state)
    """

    def __init__(self, **services) -> None:
        """
        Args:
            **services: Named service instances.
                        Keys must match constructor param names of tool classes.
        """
        self._services = services

    def create(self, step_name: str) -> BaseTool:
        """
        Instantiate the tool registered under step_name.

        Raises:
            KeyError: if step_name is not in TOOL_REGISTRY (caller must handle).
        """
        if step_name not in TOOL_REGISTRY:
            raise KeyError(
                f"No tool registered for step '{step_name}'. "
                f"Available: {list(TOOL_REGISTRY.keys())}"
            )

        tool_class = TOOL_REGISTRY[step_name]
        kwargs = self._build_kwargs(tool_class)
        logger.debug("ToolFactory creating %s for step '%s'", tool_class.__name__, step_name)
        return tool_class(**kwargs)

    def _build_kwargs(self, tool_class: Type[BaseTool]) -> Dict:
        """
        Match available services to the tool class __init__ parameters.
        Only passes services the tool actually needs (by parameter name).
        """
        import inspect
        sig = inspect.signature(tool_class.__init__)
        params = {
            name for name, _ in sig.parameters.items()
            if name != "self"
        }
        return {k: v for k, v in self._services.items() if k in params}
