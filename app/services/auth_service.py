"""
AuthService — authentication business logic.

Responsibilities:
  - register_user(email, password) → hash + persist
  - login_user(email, password)    → verify + issue JWT
  - verify_password / create_access_token (internal helpers)

This service is isolated from the LangGraph workflow.
It depends only on UserRepository and standard crypto libraries.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import bcrypt
from jose import JWTError, jwt

from app.services.db.user_repository import UserRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (read from environment with safe defaults)
# ---------------------------------------------------------------------------

JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "railyatri-dev-secret-change-me")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_MINUTES: int = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))


class AuthService:
    """Handles user registration, login, and token management."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def register_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Register a new user.

        Returns a dict with user info (no password hash exposed).
        Raises ValueError if the email is already taken or DB is unavailable.
        """
        password_hash = self._hash_password(password)
        user = self._user_repo.create_user(email, password_hash)
        if user is None:
            raise ValueError("User registration failed — database unavailable")
        logger.info("User registered: %s", email)
        return user

    def login_user(self, email: str, password: str) -> Dict[str, str]:
        """
        Authenticate a user and return a JWT.

        Returns: {"access_token": "<jwt>", "token_type": "bearer"}
        Raises ValueError on invalid credentials.
        """
        user = self._user_repo.get_user_by_email(email)
        if user is None:
            raise ValueError("Invalid email or password")

        if not self._verify_password(password, user["password_hash"]):
            raise ValueError("Invalid email or password")

        token = self._create_access_token(user_id=str(user["id"]))
        logger.info("User logged in: %s", email)
        return {"access_token": token, "token_type": "bearer"}

    # ------------------------------------------------------------------
    # Token verification (used by dependency layer)
    # ------------------------------------------------------------------

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        Decode and validate a JWT.

        Returns the payload dict.
        Raises JWTError if the token is invalid or expired.
        """
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash a plain-text password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def _verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain-text password against a bcrypt hash."""
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )

    @staticmethod
    def _create_access_token(user_id: str) -> str:
        """Create a signed JWT containing the user_id claim."""
        expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES)
        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
