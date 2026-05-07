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
            api_data_raw = self._api.check_pnr_status(resolved_pnr)
            logger.info(
                "PNRService: raw API response fetched for pnr=%s | type=%s | payload_preview=%s",
                resolved_pnr,
                type(api_data_raw).__name__,
                self._preview_payload(api_data_raw),
            )
        except Exception as exc:
            logger.error("PNRService: external API failure for %s: %s", resolved_pnr, exc)
            return {
                "ok": False,
                "message": "Unable to fetch PNR status right now. Please try again shortly.",
                "data": None,
            }

        api_data = self._normalize_api_payload(api_data_raw, fallback_pnr=resolved_pnr)
        logger.info(
            "PNRService: normalized API payload for pnr=%s | status=%s | has_train=%s | has_passengers=%s",
            resolved_pnr,
            api_data.get("status"),
            bool(api_data.get("train")),
            bool(api_data.get("passengers")),
        )
        if not self._is_successful_api_payload(api_data):
            return {
                "ok": False,
                "message": "PNR status unavailable or invalid PNR.",
                "data": {"PNR": resolved_pnr},
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
        success_states = {"successful", "success", "ok", "true", "1", "200"}
        return bool(re.fullmatch(r"\d{10}", pnr) and status in success_states)

    @staticmethod
    def _normalize_api_payload(payload: Any, fallback_pnr: str) -> Dict[str, Any]:
        """
        Normalize common NTES response variants into a stable shape for frontend/service.
        """
        if not isinstance(payload, dict):
            return {"PNR": fallback_pnr, "status": "failed", "train": [], "passengers": [], "other_info": []}

        # Common wrapper shape: {"data": {...}}
        inner = payload.get("data")
        if isinstance(inner, dict):
            payload = inner

        pnr = (
            payload.get("PNR")
            or payload.get("pnr")
            or payload.get("pnrNumber")
            or fallback_pnr
        )
        status = (
            payload.get("status")
            or payload.get("Status")
            or payload.get("result")
            or payload.get("code")
            or payload.get("success")
            or None
        )
        train = payload.get("train") or payload.get("Train")
        passengers = (
            payload.get("passengers")
            or payload.get("Passengers")
            or payload.get("passengerList")
        )
        other_info = payload.get("other_info") or payload.get("otherInfo") or payload.get("other")

        # NTES variant: train details as top-level fields
        if not train and (payload.get("trainNumber") or payload.get("trainName")):
            train = [
                {
                    "trainName": payload.get("trainName"),
                    "trainNumber": payload.get("trainNumber"),
                    "sourceStation": payload.get("sourceStation"),
                    "destinationStation": payload.get("destinationStation"),
                    "dateOfJourney": payload.get("dateOfJourney"),
                }
            ]

        if not other_info:
            other_info = []
            if payload.get("chartStatus") is not None:
                other_info.append({"chartStatus": payload.get("chartStatus")})

        # If explicit status missing but payload clearly contains PNR details,
        # mark as successful for downstream processing.
        if status is None:
            if pnr and (train or passengers):
                status = "successful"
            else:
                status = "failed"

        return {
            "PNR": str(pnr).strip(),
            "status": str(status).strip(),
            "train": train if isinstance(train, list) else [train],
            "passengers": passengers if isinstance(passengers, list) else [passengers],
            "other_info": other_info if isinstance(other_info, list) else [other_info],
        }

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

    @staticmethod
    def _preview_payload(payload: Any, max_len: int = 800) -> str:
        """
        Create a bounded one-line preview for logs.
        """
        try:
            text = str(payload).replace("\n", " ").replace("\r", " ")
            return text[:max_len] + ("..." if len(text) > max_len else "")
        except Exception:
            return "<unprintable payload>"
