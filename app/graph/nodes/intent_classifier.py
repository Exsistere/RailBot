"""
Node [I] — Intent Classifier Node.

Classifies the safe user_query into one or more intents using LLM.

Owned state mutations: intents

Precondition: is_safe must be True (asserted defensively).

Implementation: Uses LLM classification via centralised LLM service.
Falls back to UNKNOWN intent on any LLM/parse failure.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List

from app.models.state import GraphState, Intent
from app.services.llm import client as llm_client
from app.services.llm.prompts import (
    INTENT_CLASSIFIER_SYSTEM_PROMPT,
    INTENT_CLASSIFIER_USER_PROMPT_TEMPLATE,
)
from app.services.llm.parser import parse_intent_response

logger = logging.getLogger(__name__)


def intent_classifier_node(state: GraphState) -> Dict:
    """
    Classify user_query into a ranked list of intents.

    Returns a partial state dict.
    Mutates ONLY: intents
    """
    assert state.get("is_safe") is True, "IntentClassifier must not run on unsafe queries"

    query: str = state.get("user_query", "")
    intents: List[Intent] = _classify(query)

    logger.info(
        "IntentClassifier: detected intents=%s for query=%r",
        [i["type"] for i in intents],
        query[:60],
    )

    return {"intents": intents}


# ---------------------------------------------------------------------------
# Classification logic — LLM-powered
# ---------------------------------------------------------------------------

def _classify(query: str) -> List[Intent]:
    """
    LLM-based intent detection.

    Returns intents sorted by confidence DESC.
    Falls back to UNKNOWN if LLM call fails or returns unparseable output.
    """
    try:
        prompt = INTENT_CLASSIFIER_USER_PROMPT_TEMPLATE.format(query=query)
        result = llm_client.generate_json(prompt, system_prompt=INTENT_CLASSIFIER_SYSTEM_PROMPT)
        parsed = parse_intent_response(result)
        intents = [Intent(type=item["type"], confidence=item["confidence"]) for item in parsed]
        return _apply_deterministic_fallbacks(query, intents)

    except Exception as exc:
        logger.error("IntentClassifier: LLM call failed — returning UNKNOWN: %s", exc)
        return _apply_deterministic_fallbacks(query, [Intent(type="UNKNOWN", confidence=1.0)])


def _apply_deterministic_fallbacks(query: str, intents: List[Intent]) -> List[Intent]:
    """
    Heuristic fallback to prevent obvious intent misses by the LLM.
    """
    q = (query or "").lower()
    top = intents[0]["type"] if intents else "UNKNOWN"

    # CHECK_PNR_STATUS fallback
    # if top == "UNKNOWN":
    #     has_pnr_keyword = "pnr" in q or "booking status" in q or "ticket status" in q
    #     has_10_digit = bool(re.search(r"\b\d{10}\b", q))
    #     if has_pnr_keyword or has_10_digit:
    #         return [Intent(type="CHECK_PNR_STATUS", confidence=0.99)]

    # FAQ_RAG fallback
    if top == "UNKNOWN":
        faq_keywords = [
            "refund policy",
            "cancellation rule",
            "tatkal rule",
            "railway faq",
            "platform rule",
            "baggage rule",
        ]
        if any(k in q for k in faq_keywords):
            return [Intent(type="FAQ_RAG", confidence=0.95)]

    return intents
