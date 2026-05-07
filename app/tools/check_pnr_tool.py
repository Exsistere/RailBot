"""
CheckPNRTool — concrete tool for "check_pnr_status" step.

DUAL MODE:
  1. LEGACY: Reads PNR from plan[i].params
  2. NEW: Reads from shared_context.pnr_number

Key feature: Enriches shared_context with derived knowledge:
  - Inferred train number from PNR status
  - Waitlist detection
  - Latest user PNR caching
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.models.state import GraphState
from app.services.pnr_service import PNRService
from app.tools.base_tool import BaseTool, ToolValidationError

logger = logging.getLogger(__name__)


class CheckPNRTool(BaseTool):
    """
    Check PNR booking status and enrich SharedContext.

    Dual mode (backward compatible):
      - Reads from shared_context.pnr_number (new)
      - Falls back to plan[i].params (legacy)

    Returns memory_updates for downstream tools to use:
      - inferred_train_number
      - waitlist_detected
      - latest_user_pnr
    """

    def __init__(self, pnr_service: PNRService) -> None:
        self._pnr_service = pnr_service

    def _validate(self, state: GraphState) -> None:
        user_id = state.get("user_id", "")
        if not user_id:
            raise ToolValidationError("user_id is required for CHECK_PNR_STATUS")

    def _fetch_data(self, state: GraphState) -> Dict[str, Any]:
        user_id = state.get("user_id", "")
        pnr_number = self._get_pnr_number(state)

        logger.info(
            "CheckPNRTool: checking pnr=%s for user=%s",
            pnr_number,
            user_id,
        )

        return self._pnr_service.check_status(user_id=user_id, pnr_number=pnr_number)

    def _process(self, raw_data: Dict[str, Any], state: GraphState) -> Dict[str, Any]:
        payload = raw_data.get("data") or {}
        return {
            "ok": bool(raw_data.get("ok")),
            "message": raw_data.get("message", ""),
            "response_type": "PNR_STATUS",
            "data": payload,
        }

    def _get_memory_updates(self, result: Any, state: GraphState) -> Dict[str, Any]:
        """
        Extract knowledge from PNR result to enrich SharedContext.

        Memory updates enable downstream tools to:
        - Use inferred_train_number for alternate train searches
        - Know if traveler is waitlisted
        - Cache latest PNR for future reference
        """
        data = result.get("data", {}) if isinstance(result, dict) else {}
        if not data:
            return {}

        updates = {}

        # Extract inferred train number
        if data.get("train_number"):
            updates["inferred_train_number"] = data["train_number"]
            logger.debug(f"CheckPNRTool: inferred train_number={data['train_number']}")

        # Detect waitlist status
        status = data.get("status", "").upper()
        if "WAITLIST" in status or "WL" in status:
            updates["waitlist_detected"] = True
            logger.debug("CheckPNRTool: waitlist detected")

        # Cache latest user PNR
        pnr_number = self._get_pnr_number(state)
        if pnr_number and data.get("status"):
            updates["latest_user_pnr"] = pnr_number
            logger.debug(f"CheckPNRTool: caching latest_user_pnr={pnr_number}")

        return updates

    # ------------------------------------------------------------------
    # Parameter extraction — dual mode
    # ------------------------------------------------------------------

    def _get_pnr_number(self, state: GraphState) -> Optional[str]:
        """
        Get PNR number from shared_context (new) or plan params (legacy).

        If no PNR specified, fetches latest user PNR from DB.
        """
        shared_context = state.get("shared_context")

        # NEW: Try shared_context first
        if shared_context and shared_context.pnr_number:
            logger.debug("CheckPNRTool: using shared_context.pnr_number")
            return shared_context.pnr_number

        # LEGACY: Try plan params
        params = self._get_params_from_plan(state)
        if params.get("pnr_number"):
            logger.debug("CheckPNRTool: using plan params (legacy mode)")
            return params.get("pnr_number")

        # FALLBACK: Fetch latest PNR from DB for this user
        user_id = state.get("user_id", "")
        if user_id:
            try:
                from app.services.db.user_pnr_repository import UserPNRRepository
                repo = UserPNRRepository()
                latest = repo.get_latest_pnr_for_user(user_id)
                if latest:
                    logger.info(f"CheckPNRTool: fetched latest PNR from DB: {latest}")
                    return latest
            except Exception as exc:
                logger.warning(f"CheckPNRTool: failed to fetch latest PNR: {exc}")

        return None

    def _get_params_from_plan(self, state: GraphState) -> Dict[str, Any]:
        """Read params from active PlanStep (legacy mode)."""
        plan = state.get("plan", [])
        index = state.get("current_step_index", 0)
        if plan and 0 <= index < len(plan):
            return plan[index].get("params", {})
        return {}

