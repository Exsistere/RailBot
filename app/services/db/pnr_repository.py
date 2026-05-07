"""
PNRRepository — DB access for the pnrs table.

Lightweight cached PNR journey state. External API remains source of truth.
This is a read-through cache: upsert on each API fetch, read on cache hit.

Repositories contain ONLY DB logic. No service/tool/graph calls.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.db.base_repository import BaseRepository
from app.services.db.connection import DatabaseManager

logger = logging.getLogger(__name__)


class PNRRepository(BaseRepository):
    """Handles pnrs table operations."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_by_pnr_number(self, pnr_number: str) -> Optional[Dict[str, Any]]:
        """
        Look up a PNR record by its number.
        Returns the row dict or None on miss / DB unavailable.
        """
        if not self._db.is_available():
            return None
        try:
            conn = self._db.get_connection()
            return self._fetch_one(
                conn,
                """
                SELECT id, pnr_number, train_number, journey_date,
                       last_known_status, updated_at
                FROM pnrs
                WHERE pnr_number = %s
                """,
                (pnr_number,),
            )
        except Exception as exc:
            logger.error("PNRRepository.get_by_pnr_number failed: %s", exc)
            return None

    def upsert(
        self,
        pnr_number: str,
        train_number: Optional[str] = None,
        journey_date: Optional[str] = None,
        last_known_status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Insert or update a PNR record.

        Uses INSERT ... ON CONFLICT (pnr_number) DO UPDATE to keep the
        latest known status fresh.

        Returns the upserted row (with id), or None if DB unavailable.
        """
        if not self._db.is_available():
            return None
        now = datetime.now(timezone.utc)
        try:
            conn = self._db.get_connection()
            # Check if exists first to get the id
            existing = self.get_by_pnr_number(pnr_number)
            if existing:
                pnr_id = str(existing["id"])
                self._execute(
                    conn,
                    """
                    UPDATE pnrs
                    SET train_number = COALESCE(%s, train_number),
                        journey_date = COALESCE(%s::date, journey_date),
                        last_known_status = COALESCE(%s, last_known_status),
                        updated_at = %s
                    WHERE pnr_number = %s
                    """,
                    (train_number, journey_date, last_known_status, now, pnr_number),
                )
            else:
                pnr_id = str(uuid.uuid4())
                self._execute(
                    conn,
                    """
                    INSERT INTO pnrs (id, pnr_number, train_number, journey_date,
                                      last_known_status, updated_at)
                    VALUES (%s, %s, %s, %s::date, %s, %s)
                    """,
                    (pnr_id, pnr_number, train_number, journey_date,
                     last_known_status, now),
                )
            return {"id": pnr_id, "pnr_number": pnr_number}
        except Exception as exc:
            logger.error("PNRRepository.upsert failed: %s", exc)
            return None
