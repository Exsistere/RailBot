"""
PNRService — orchestration layer for CHECK_PNR_STATUS tool.

Flow:
  1) If explicit pnr_number is provided:
     - validate format
     - call external API
     - persist only valid/successful PNRs
  2) Else:
     - fetch latest tracked PNR for user
     - call external API with that PNR

Service owns orchestration; repositories own persistence.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from app.services.db.pnr_repository import PNRRepository
from app.services.db.user_pnr_repository import UserPNRRepository
from app.services.railway_api_client import RailwayAPIClient

logger = logging.getLogger(__name__)


class PNRService:
    """Facade over PNRRepository, UserPNRRepository, and RailwayAPIClient."""

    def __init__(
        self,
        pnr_repo: PNRRepository,
        user_pnr_repo: UserPNRRepository,
        railway_api_client: RailwayAPIClient,
    ) -> None:
        self._pnr_repo = pnr_repo
        self._user_pnr_repo = user_pnr_repo
        self._api = railway_api_client

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def check_status(self, user_id: str, pnr_number: Optional[str] = None) -> Dict[str, Any]:
        """
        Return latest PNR status for a user.

        - Uses provided pnr_number if present, else user's latest tracked PNR.
        - Persists only valid/successful responses.
        """
        resolved_pnr = (pnr_number or "").strip()
        if resolved_pnr:
            if not self._is_valid_pnr(resolved_pnr):
                return {
                    "ok": False,
                    "message": "Invalid PNR format. Please provide a 10-digit PNR number.",
                    "data": None,
                }
        else:
            latest = self._user_pnr_repo.get_latest_pnr_for_user(user_id)
            if not latest or not latest.get("pnr_number"):
                return {
                    "ok": False,
                    "message": "No saved PNR found for your account. Please provide a PNR number.",
                    "data": None,
                }
            resolved_pnr = str(latest["pnr_number"])

        try:
            api_data = self._api.check_pnr_status(resolved_pnr)
        except Exception as exc:
            logger.error("PNRService: external API failure for %s: %s", resolved_pnr, exc)
            return {
                "ok": False,
                "message": "Unable to fetch PNR status right now. Please try again shortly.",
                "data": None,
            }

        if not self._is_successful_api_payload(api_data):
            return {
                "ok": False,
                "message": "PNR status unavailable or invalid PNR.",
                "data": {"pnr_number": resolved_pnr},
            }

        # Persist only valid/successful payloads
        try:
            train = (api_data.get("train") or [{}])[0]
            passengers = api_data.get("passengers") or []
            current_status = passengers[0].get("currentStatus") if passengers else None
            pnr_row = self._pnr_repo.upsert(
                pnr_number=resolved_pnr,
                train_number=train.get("trainNumber"),
                journey_date=self._to_iso_date(train.get("dateOfJourney")),
                last_known_status=current_status,
            )
            if pnr_row and not self._user_pnr_repo.exists(user_id=user_id, pnr_id=pnr_row["id"]):
                self._user_pnr_repo.save_user_pnr(user_id=user_id, pnr_id=pnr_row["id"])
        except Exception as exc:
            logger.error("PNRService: persistence failed (suppressed): %s", exc)

        return {
            "ok": True,
            "message": f"Fetched latest status for PNR {resolved_pnr}.",
            "data": api_data,
        }

    @staticmethod
    def _is_valid_pnr(pnr_number: str) -> bool:
        return bool(re.fullmatch(r"\d{10}", pnr_number or ""))

    @staticmethod
    def _is_successful_api_payload(payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        pnr = str(payload.get("PNR", "")).strip()
        status = str(payload.get("status", "")).strip().lower()
        return bool(re.fullmatch(r"\d{10}", pnr) and status == "successful")

    @staticmethod
    def _to_iso_date(date_str: Optional[str]) -> Optional[str]:
        """
        Convert DD-MM-YYYY -> YYYY-MM-DD for DB compatibility.
        """
        if not date_str or not isinstance(date_str, str):
            return None
        try:
            dd, mm, yyyy = date_str.split("-")
            return f"{yyyy}-{mm}-{dd}"
        except Exception:
            return None
