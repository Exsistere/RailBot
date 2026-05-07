"""
DatabaseManager — connection lifecycle and schema initialisation.

Reads DATABASE_URL from environment. If the variable is absent or the
connection cannot be established, the manager silently marks the DB as
unavailable. All repositories check `is_available()` and fall back to
in-memory / file storage — no exception is ever surfaced to callers.

Schema management:
    All DDL lives exclusively in app/db/schema.sql.
    This module loads and executes that file once on connect.
    NO inline CREATE TABLE / ALTER TABLE statements belong here.
"""

from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# psycopg2 is optional; graceful degradation if not installed / DB absent
try:
    import psycopg2
    import psycopg2.extras
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    _PSYCOPG2_AVAILABLE = False

# Resolve schema.sql path relative to this file:
#   app/services/db/connection.py → app/db/schema.sql
_SCHEMA_SQL_PATH: Path = (
    Path(__file__).resolve().parent.parent.parent / "db" / "schema.sql"
)


class DBUnavailableError(Exception):
    """Raised internally when a DB connection cannot be obtained."""


load_dotenv()


class DatabaseManager:
    """
    Manages a single persistent PostgreSQL connection.

    Usage:
        db = DatabaseManager()
        if db.is_available():
            conn = db.get_connection()
    """

    def __init__(self) -> None:
        self._connection: Optional[object] = None
        self._available: bool = False
        self._url: Optional[str] = os.getenv("DATABASE_URL")
        self._try_connect()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """True if a live DB connection exists."""
        return self._available and self._connection is not None

    def get_connection(self) -> object:
        """
        Return the live psycopg2 connection.
        Raises DBUnavailableError if connection is not available.
        """
        if not self.is_available():
            raise DBUnavailableError("PostgreSQL is not available")
        # Reconnect if connection was closed
        try:
            if self._connection.closed:  # type: ignore[union-attr]
                self._try_connect()
        except Exception:
            self._available = False
            raise DBUnavailableError("PostgreSQL connection is closed")
        return self._connection

    def close(self) -> None:
        """Cleanly close the connection."""
        if self._connection is not None:
            try:
                self._connection.close()  # type: ignore[union-attr]
            except Exception:
                pass
            self._connection = None
            self._available = False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _try_connect(self) -> None:
        if not _PSYCOPG2_AVAILABLE:
            logger.warning("psycopg2 not installed — running without PostgreSQL")
            return
        if not self._url:
            logger.warning("DATABASE_URL not set — running without PostgreSQL")
            return
        try:
            self._connection = psycopg2.connect(self._url)
            self._connection.autocommit = True  # type: ignore[union-attr]
            self._available = True
            logger.info("PostgreSQL connection established")
            self._load_schema_sql()
        except Exception as exc:
            logger.warning(
                "PostgreSQL unavailable: %s — using in-memory fallback", exc
            )
            self._available = False
            self._connection = None

    def _load_schema_sql(self) -> None:
        """
        Execute app/db/schema.sql against the live connection.

        All CREATE TABLE / INDEX statements use IF NOT EXISTS — this is
        idempotent and safe to run on every startup.
        No inline DDL belongs anywhere else in the codebase.
        """
        if not _SCHEMA_SQL_PATH.exists():
            logger.error(
                "schema.sql not found at %s — database schema not initialised",
                _SCHEMA_SQL_PATH,
            )
            return
        try:
            schema_sql = _SCHEMA_SQL_PATH.read_text(encoding="utf-8")
            with self._connection.cursor() as cur:  # type: ignore[union-attr]
                cur.execute(schema_sql)
            logger.info("Database schema loaded from %s", _SCHEMA_SQL_PATH)
        except Exception as exc:
            logger.error("Schema initialisation failed: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton — imported by repositories
# ---------------------------------------------------------------------------
db_manager = DatabaseManager()
