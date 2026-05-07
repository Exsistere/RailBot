"""
Node [G] — Guardrail Node.

First line of defence. Evaluates raw user_query for safety violations
before any LLM processing or tool invocation.

Owned state mutations: is_safe, attack_type, final_response (refusal only)

Fail-safe contract (LLD C4):
  - Any exception → is_safe=False, attack_type="OTHER"
  - Never allow an unevaluated query through

Implementation: Uses LLM classification via centralised LLM service.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Dict

from app.models.state import GraphState
from app.services.llm import client as llm_client
from app.services.llm.prompts import GUARDRAIL_SYSTEM_PROMPT, GUARDRAIL_USER_PROMPT_TEMPLATE
from app.services.llm.parser import parse_guardrail_response

logger = logging.getLogger(__name__)

_REFUSAL_MESSAGE = (
    "I'm sorry, I'm unable to process that request. "
    "Please ask me about train schedules, availability, or travel information."
)


def guardrail_node(state: GraphState) -> Dict:
    """
    Evaluate user_query for safety violations.

    Returns a partial state dict (LangGraph merges it into GraphState).
    Mutates ONLY: is_safe, attack_type, final_response.
    """
    try:
        query: str = state.get("user_query", "").strip()
        user_id: str = state.get("user_id", "anonymous")

        # Empty query — fail safe
        if not query:
            logger.warning("Guardrail: empty query from user_id=%s", user_id)
            return _deny(user_id, query, "OTHER", "Empty query received")

        # LLM-based safety classification
        prompt = GUARDRAIL_USER_PROMPT_TEMPLATE.format(query=query)
        result = llm_client.generate_json(prompt, system_prompt=GUARDRAIL_SYSTEM_PROMPT)
        parsed = parse_guardrail_response(result)

        if parsed["is_safe"]:
            logger.info(
                "Guardrail: SAFE | user_id=%s | query_hash=%s",
                user_id,
                _hash(query),
            )
            return {
                "is_safe": True,
                "attack_type": None,
            }
        else:
            logger.warning(
                "Guardrail: %s detected | user_id=%s | query_hash=%s",
                parsed["attack_type"],
                user_id,
                _hash(query),
            )
            return _deny(user_id, query, parsed["attack_type"])

    except Exception as exc:
        # Fail-safe: any unhandled exception → DENY (LLD C4)
        logger.error("Guardrail: unexpected exception — defaulting to DENY: %s", exc, exc_info=True)
        return _deny(
            state.get("user_id", "anonymous"),
            state.get("user_query", ""),
            "OTHER",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deny(
    user_id: str,
    query: str,
    attack_type: str,
    detail: str = "",
) -> Dict:
    """Build a DENY state patch."""
    logger.info(
        "Guardrail DENY | user_id=%s | attack_type=%s | detail=%s",
        user_id,
        attack_type,
        detail,
    )
    return {
        "is_safe": False,
        "attack_type": attack_type,
        "final_response": _REFUSAL_MESSAGE,
    }


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]
