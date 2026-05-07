"""
UserPNRRepository — DB access for the user_pnrs table.

Maps users to tracked PNRs. References pnrs.id (UUID FK) — not raw
pnr_number — for proper normalisation.

Repositories contain ONLY DB logic. No service/tool/graph calls.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.db.base_repository import BaseRepository
from app.services.db.connection import DatabaseManager

logger = logging.getLogger(__name__)


class UserPNRRepository(BaseRepository):
    """Handles user_pnrs table operations."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add_pnr_for_user(
        self,
        user_id: str,
        pnr_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Associate a PNR (by pnrs.id UUID) with a user.

        Returns the created row dict, or None if DB unavailable.
        """
        if not self._db.is_available():
            logger.warning("UserPNRRepository: DB unavailable")
            return None

        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        try:
            conn = self._db.get_connection()
            self._execute(
                conn,
                """
                INSERT INTO user_pnrs (id, user_id, pnr_id, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (record_id, user_id, pnr_id, now),
            )
            return {"id": record_id, "user_id": user_id, "pnr_id": pnr_id}
        except Exception as exc:
            logger.error("UserPNRRepository.add_pnr_for_user failed: %s", exc)
            return None

    # Compatibility alias expected by new orchestration/service layer
    def save_user_pnr(self, user_id: str, pnr_id: str) -> Optional[Dict[str, Any]]:
        return self.add_pnr_for_user(user_id=user_id, pnr_id=pnr_id)

    def get_latest_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the most recently tracked PNR for a user.

        Returns a row joining user_pnrs + pnrs, or None.
        """
        if not self._db.is_available():
            return None
        try:
            conn = self._db.get_connection()
            return self._fetch_one(
                conn,
                """
                SELECT up.id, up.user_id, up.created_at,
                       p.id AS pnr_id, p.pnr_number, p.train_number,
                       p.journey_date, p.last_known_status
                FROM user_pnrs up
                JOIN pnrs p ON p.id = up.pnr_id
                WHERE up.user_id = %s
                ORDER BY up.created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
        except Exception as exc:
            logger.error("UserPNRRepository.get_latest_for_user failed: %s", exc)
            return None

    # Compatibility alias expected by new orchestration/service layer
    def get_latest_pnr_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.get_latest_for_user(user_id)

    def exists(self, user_id: str, pnr_id: str) -> bool:
        """Check whether a user->pnr relation already exists."""
        if not self._db.is_available():
            return False
        try:
            conn = self._db.get_connection()
            row = self._fetch_one(
                conn,
                """
                SELECT 1
                FROM user_pnrs
                WHERE user_id = %s AND pnr_id = %s
                LIMIT 1
                """,
                (user_id, pnr_id),
            )
            return row is not None
        except Exception as exc:
            logger.error("UserPNRRepository.exists failed: %s", exc)
            return False

    def get_all_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Return all PNRs tracked by a user, newest first.
        """
        if not self._db.is_available():
            return []
        try:
            conn = self._db.get_connection()
            return self._fetch_all(
                conn,
                """
                SELECT up.id, up.user_id, up.created_at,
                       p.id AS pnr_id, p.pnr_number, p.train_number,
                       p.journey_date, p.last_known_status
                FROM user_pnrs up
                JOIN pnrs p ON p.id = up.pnr_id
                WHERE up.user_id = %s
                ORDER BY up.created_at DESC
                """,
                (user_id,),
            )
        except Exception as exc:
            logger.error("UserPNRRepository.get_all_for_user failed: %s", exc)
            return []
