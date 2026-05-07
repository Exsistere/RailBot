"""
PNRService — orchestrates PNR-related operations.

Responsibilities:
  - Resolve "latest" PNR references for a user
  - Upsert PNR state from external API results
  - Link PNRs to users via user_pnrs

This service:
  - Orchestrates UserPNRRepository + PNRRepository + external API
  - MUST NOT contain FastAPI route logic
  - MUST NOT contain LangGraph orchestration
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.services.db.pnr_repository import PNRRepository
from app.services.db.user_pnr_repository import UserPNRRepository

logger = logging.getLogger(__name__)


class PNRService:
    """Facade over PNRRepository and UserPNRRepository."""

    def __init__(
        self,
        pnr_repo: PNRRepository,
        user_pnr_repo: UserPNRRepository,
    ) -> None:
        self._pnr_repo = pnr_repo
        self._user_pnr_repo = user_pnr_repo

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_latest_pnr_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the most recently tracked PNR for a user.

        Returns a dict with pnr_number, train_number, journey_date,
        last_known_status — or None if no PNR is tracked.

        Future: trigger external API call + update pnrs.last_known_status.
        """
        return self._user_pnr_repo.get_latest_for_user(user_id)

    def get_all_pnrs_for_user(self, user_id: str) -> list:
        """Return all PNRs tracked by a user."""
        return self._user_pnr_repo.get_all_for_user(user_id)

    def track_pnr_for_user(
        self,
        user_id: str,
        pnr_number: str,
        train_number: Optional[str] = None,
        journey_date: Optional[str] = None,
        last_known_status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Register a PNR under a user's account.

        Flow:
          1. Upsert into pnrs (create or update cached state)
          2. Link via user_pnrs (user_id → pnrs.id)

        Returns the user_pnrs row, or None on failure.
        """
        pnr_record = self._pnr_repo.upsert(
            pnr_number=pnr_number,
            train_number=train_number,
            journey_date=journey_date,
            last_known_status=last_known_status,
        )
        if pnr_record is None:
            logger.warning("PNRService: could not upsert PNR %s — DB unavailable?", pnr_number)
            return None

        return self._user_pnr_repo.add_pnr_for_user(
            user_id=user_id,
            pnr_id=pnr_record["id"],
        )

    def update_pnr_status(
        self,
        pnr_number: str,
        last_known_status: str,
    ) -> None:
        """
        Update the cached status of a PNR after an external API call.
        Called by the CHECK_PNR_STATUS tool (future).
        """
        self._pnr_repo.upsert(
            pnr_number=pnr_number,
            last_known_status=last_known_status,
        )
