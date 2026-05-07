"""
Auth Routes — registration and login endpoints.

These endpoints are public (no JWT required).
On success, /login returns a JWT that must be included
in subsequent requests to protected routes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService
from app.services.db.connection import db_manager
from app.services.db.user_repository import UserRepository

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

# ---------------------------------------------------------------------------
# Service wiring — lightweight, same pattern used in workflow.py
# ---------------------------------------------------------------------------

_user_repo = UserRepository(db_manager)
_auth_service = AuthService(_user_repo)


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@auth_router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(request: RegisterRequest) -> RegisterResponse:
    """Create a new user with email and password."""
    try:
        user = _auth_service.register_user(request.email, request.password)
        return RegisterResponse(
            id=user["id"],
            email=user["email"],
            message="Registration successful",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@auth_router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT",
)
def login(request: LoginRequest) -> TokenResponse:
    """Validate credentials and return a Bearer token."""
    try:
        result = _auth_service.login_user(request.email, request.password)
        return TokenResponse(
            access_token=result["access_token"],
            token_type=result["token_type"],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
