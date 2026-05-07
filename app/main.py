"""
FastAPI Application Entry Point.

Configures the app, registers routers, and sets up logging.
Run with: uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.api.auth_routes import auth_router

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RailYatri — Railway Assistant API",
    description=(
        "LangGraph-powered railway assistant. "
        "Supports natural language queries for train search."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — permissive for development; tighten for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(api_router, prefix="/api/v1", tags=["Railway Assistant"])
app.include_router(auth_router, tags=["Authentication"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe — returns 200 if the app is running."""
    return {"status": "ok", "service": "railyatri-api"}


# ---------------------------------------------------------------------------
# Startup event
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    logger.info("RailYatri API starting up...")
    # Graph is compiled at import time in workflow.py;
    # any startup errors will surface here.
    try:
        from app.graph.workflow import compiled_graph  # noqa: F401
        logger.info("LangGraph workflow ready")
    except Exception as exc:
        logger.error("Failed to compile LangGraph workflow: %s", exc, exc_info=True)
        raise
