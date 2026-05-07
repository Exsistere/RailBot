"""
Node [L] — Logger Node.

Terminal node. Persists the complete interaction record to the Data Layer.
Does NOT modify any GraphState field.

Failures are SILENTLY suppressed — logging must never affect user experience
or final_response. (LLD constraint C5 — idempotent logger)
"""

from __future__ import annotations

import logging
from typing import Dict

from app.models.state import GraphState

logger = logging.getLogger(__name__)

# InteractionService injected at startup via set_interaction_service()
_interaction_service = None


def set_interaction_service(service) -> None:
    """
    Inject the InteractionService instance at application startup.
    Called once from app/graph/workflow.py during graph compilation.
    """
    global _interaction_service
    _interaction_service = service


def logger_node(state: GraphState) -> Dict:
    """
    Persist the full interaction record. Returns empty dict (no state mutation).

    This is always the last node — final_response is guaranteed to be set
    (by either Guardrail or Responder) before this node executes.
    """
    try:
        if _interaction_service is None:
            logger.warning("LoggerNode: InteractionService not injected — skipping DB log")
            _fallback_log(state)
            return {}

        _interaction_service.log_interaction(dict(state))
        logger.debug(
            "LoggerNode: interaction persisted for user_id=%s",
            state.get("user_id", "anonymous"),
        )
    except Exception as exc:
        # Absolute last resort — never surface to caller
        logger.error("LoggerNode: unexpected error (suppressed): %s", exc, exc_info=True)
        try:
            _fallback_log(state)
        except Exception:
            pass

    # Always return empty dict — Logger owns no state fields
    return {}


# ---------------------------------------------------------------------------
# Fallback: structured Python log when service is unavailable
# ---------------------------------------------------------------------------

def _fallback_log(state: GraphState) -> None:
    """Emit a structured log entry when DB and service are unavailable."""
    import json
    entry = {
        "user_id": state.get("user_id", ""),
        "query_hash": _hash(state.get("user_query", "")),
        "is_safe": state.get("is_safe"),
        "attack_type": state.get("attack_type"),
        "intents": state.get("intents", []),
        "final_response_length": len(state.get("final_response", "") or ""),
    }
    logger.info("LoggerNode [FALLBACK]: %s", json.dumps(entry, default=str))


def _hash(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()[:16]
