"""
BaseRepository — shared query helpers for all repository subclasses.

Repositories never manage connection lifecycle — they receive a connection
from DatabaseManager. All raw SQL is confined to repository classes; no
other layer writes SQL directly.
"""

from __future__ import annotations

import json
import logging
from abc import ABC
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BaseRepository(ABC):
    """
    Abstract base providing low-level CRUD helpers.

    Subclasses call `self._execute`, `self._fetch_one`, `self._fetch_all`
    with a live psycopg2 connection. Connection management is the caller's
    responsibility (DatabaseManager).
    """

    # ------------------------------------------------------------------
    # Protected helpers — used by subclasses
    # ------------------------------------------------------------------

    def _execute(
        self,
        conn: Any,
        sql: str,
        params: Tuple = (),
    ) -> None:
        """Execute a DML statement (INSERT / UPDATE / DELETE)."""
        with conn.cursor() as cur:
            cur.execute(sql, params)

    def _fetch_one(
        self,
        conn: Any,
        sql: str,
        params: Tuple = (),
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single row as a dict, or None if not found."""
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row is None:
                return None
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))

    def _fetch_all(
        self,
        conn: Any,
        sql: str,
        params: Tuple = (),
    ) -> List[Dict[str, Any]]:
        """Fetch all rows as a list of dicts."""
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in rows]

    # ------------------------------------------------------------------
    # JSON helper — psycopg2 does not auto-serialise Python dicts for JSONB
    # ------------------------------------------------------------------

    @staticmethod
    def _to_json(value: Any) -> str:
        """Serialise a Python object to a JSON string for JSONB columns."""
        return json.dumps(value, default=str)
