"""
CheckPNRTool — concrete tool for "check_pnr_status" step.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.models.state import GraphState
from app.services.pnr_service import PNRService
from app.tools.base_tool import BaseTool, ToolValidationError

logger = logging.getLogger(__name__)


class CheckPNRTool(BaseTool):
    """Validate params, call PNRService, and return structured PNR payload."""

    def __init__(self, pnr_service: PNRService) -> None:
        self._pnr_service = pnr_service

    def _validate(self, state: GraphState) -> None:
        user_id = state.get("user_id", "")
        if not user_id:
            raise ToolValidationError("user_id is required for CHECK_PNR_STATUS")

    def _fetch_data(self, state: GraphState) -> Dict[str, Any]:
        params = self._get_params(state)
        user_id = state.get("user_id", "")
        pnr_number = params.get("pnr_number")
        logger.info("CheckPNRTool: checking pnr=%s for user=%s", pnr_number, user_id)
        return self._pnr_service.check_status(user_id=user_id, pnr_number=pnr_number)

    def _process(self, raw_data: Dict[str, Any], state: GraphState) -> Dict[str, Any]:
        payload = raw_data.get("data") or {}
        return {
            "ok": bool(raw_data.get("ok")),
            "message": raw_data.get("message", ""),
            "response_type": "PNR_STATUS",
            "data": payload,
        }

    def _get_params(self, state: GraphState) -> Dict[str, Any]:
        plan = state.get("plan", [])
        index = state.get("current_step_index", 0)
        if plan and 0 <= index < len(plan):
            return plan[index].get("params", {})
        return {}

