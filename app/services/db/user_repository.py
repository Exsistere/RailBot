"""
UserRepository — DB access for the users table.

Handles user creation and lookup for authentication.
Follows the same patterns as TrainRepository / InteractionRepository.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.db.base_repository import BaseRepository
from app.services.db.connection import DatabaseManager

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    """Repository for the ``users`` table."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create_user(
        self,
        email: str,
        password_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Insert a new user row and return the created record.

        Returns None if the DB is unavailable.
        Raises ``ValueError`` if the email is already taken (unique constraint).
        """
        if not self._db.is_available():
            logger.warning("UserRepository: DB unavailable — cannot create user")
            return None

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        try:
            conn = self._db.get_connection()
            self._execute(
                conn,
                """
                INSERT INTO users (id, email, password_hash, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, email, password_hash, now),
            )
            logger.info("User created: %s", email)
            return {
                "id": user_id,
                "email": email,
                "created_at": now.isoformat(),
            }
        except Exception as exc:
            # psycopg2 unique-violation code: 23505
            if hasattr(exc, "pgcode") and exc.pgcode == "23505":  # type: ignore[union-attr]
                raise ValueError(f"Email already registered: {email}") from exc
            logger.error("UserRepository.create_user failed: %s", exc)
            raise

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a user row by email.

        Returns the user dict or None if not found / DB unavailable.
        """
        if not self._db.is_available():
            logger.warning("UserRepository: DB unavailable — cannot look up user")
            return None

        try:
            conn = self._db.get_connection()
            return self._fetch_one(
                conn,
                "SELECT id, email, password_hash, created_at FROM users WHERE email = %s",
                (email,),
            )
        except Exception as exc:
            logger.error("UserRepository.get_user_by_email failed: %s", exc)
            return None
