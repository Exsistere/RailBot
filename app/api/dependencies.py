"""
API Dependencies — FastAPI dependency injection for authentication.

Provides `get_current_user` to extract and validate the JWT from the
Authorization header.  Used as a dependency in protected route handlers.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# OAuth2 scheme — looks for "Authorization: Bearer <token>" header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    FastAPI dependency that extracts and validates the JWT.

    Returns the authenticated user_id (str).
    Raises HTTP 401 if the token is missing, invalid, or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = AuthService.decode_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except Exception:
        logger.debug("JWT validation failed", exc_info=True)
        raise credentials_exception
