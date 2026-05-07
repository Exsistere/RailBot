"""
Node [Re] — Responder Node.

Synthesises tool_results into a coherent natural-language response.

Response strategy is driven by top_intent from GraphState.intents:
  - SMALL_TALK  → friendly conversational reply (no tool data expected)
  - UNKNOWN     → helpful capability hint
  - SEARCH_TRAINS (happy path) → LLM-formatted train results
  - SEARCH_TRAINS (all failed) → graceful failure message
  - is_safe=False → echo Guardrail refusal

Owned state mutations: final_response ONLY.

Implementation: Uses LLM via centralised service for response generation.
Falls back to template-based responses on LLM failure.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any, Dict, List, Optional

from app.models.state import GraphState, Intent, PlanStep
from app.services.llm import client as llm_client
from app.services.llm.prompts import (
    RESPONDER_SYSTEM_PROMPT,
    RESPONDER_USER_PROMPT_TEMPLATE,
    FAQ_RAG_RESPONDER_SYSTEM_PROMPT,
    FAQ_RAG_RESPONDER_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Small talk responses — friendly, varied, no tool calls needed
# ---------------------------------------------------------------------------

_SMALL_TALK_RESPONSES = [
    "Hi there! 👋 I'm RailYatri, your AI railway assistant. Ask me about trains, routes, schedules, or availability!",
    "Hello! 🚆 Ready to help with your train journey. Try: \"Trains from Delhi to Mumbai on 15 June\".",
    "Hey! Great to see you. I can help you search for trains across India. Where are you headed?",
    "Good to have you here! I specialise in Indian railway queries — schedules, routes, and availability.",
    "Hi! I'm here to make your train travel planning easier. What route are you planning?",
    "Hello! 🙏 You can ask me things like: \"Show trains from Surat to Mumbai tomorrow.\"",
]

_THANKS_RESPONSES = [
    "You're welcome! 😊 Let me know if you need anything else.",
    "Happy to help! Feel free to ask about any train route.",
    "Anytime! Safe travels 🚆",
]


def responder_node(state: GraphState) -> Dict:
    """
    Generate the final natural-language response.

    Branches explicitly on top_intent — not just on empty tool_results.

    Returns a partial state dict.
    Mutates ONLY: final_response
    """
    is_safe: Optional[bool] = state.get("is_safe")

    # Safety refusal — Guardrail already set final_response; echo it through
    if is_safe is False:
        existing = state.get("final_response", "I'm unable to process that request.")
        logger.info("Responder: unsafe query path — echoing Guardrail refusal")
        return {"final_response": existing}

    intents: List[Intent] = state.get("intents", [])
    top_intent: str = intents[0]["type"] if intents else "UNKNOWN"

    plan: List[PlanStep] = state.get("plan", [])
    tool_results: Dict[str, Any] = state.get("tool_results", {})
    user_query: str = state.get("user_query", "")

    logger.info(
        "Responder: top_intent=%s plan_len=%d tool_results_keys=%s",
        top_intent,
        len(plan),
        list(tool_results.keys()),
    )

    # ------------------------------------------------------------------
    # Branch 1: SMALL_TALK — friendly reply, no tool data
    # ------------------------------------------------------------------
    if top_intent == "SMALL_TALK":
        logger.info("Responder: SMALL_TALK path")
        return {"final_response": _get_small_talk_reply(user_query)}

    # ------------------------------------------------------------------
    # Branch 2: UNKNOWN or no plan produced
    # ------------------------------------------------------------------
    if top_intent == "UNKNOWN" or not plan:
        logger.info("Responder: UNKNOWN intent — returning capability hint")
        return {
            "final_response": (
                "I'm not sure I understood that. I can help with Indian railway queries.\n\n"
                "Try something like:\n"
                "• \"Trains from Delhi to Mumbai on 15 June\"\n"
                "• \"Show me sleeper trains from Surat to Chennai tomorrow\""
            )
        }

    # ------------------------------------------------------------------
    # Branch 3: All tool steps FAILED
    # ------------------------------------------------------------------
    all_failed = all(step.get("status") == "FAILED" for step in plan)
    if all_failed:
        logger.warning("Responder: all plan steps FAILED")
        return {
            "final_response": (
                "I wasn't able to complete your request at this time. "
                "This might be a temporary issue with the railway data service.\n"
                "Please try again in a moment, or rephrase your query."
            )
        }

    # ------------------------------------------------------------------
    # Branch 3.5: Structured response passthrough for new tools
    # ------------------------------------------------------------------
    if top_intent == "CHECK_PNR_STATUS":
        pnr_result = tool_results.get("check_pnr_status", {})
        pnr_data = pnr_result.get("data") if isinstance(pnr_result, dict) else None
        if pnr_data and pnr_data.get("message"):
            return {"final_response": pnr_data.get("message")}

    if top_intent == "FAQ_RAG":
        rag_result = tool_results.get("faq_rag", {})
        rag_data = rag_result.get("data") if isinstance(rag_result, dict) else None
        logger.info(
            "Responder: FAQ_RAG tool data present=%s",
            bool(rag_data),
        )
        if rag_data:
            inner_data = rag_data.get("data", {})
            chunks = inner_data.get("chunks", [])
            logger.info(
                "Responder: FAQ_RAG chunks=%d sample=%r",
                len(chunks),
                chunks[0].get("text", "")[:200] if chunks else "",
            )
            response = _format_faq_rag_response(user_query, chunks)
            logger.info("Responder: FAQ_RAG final_response=%r", response)
            return {"final_response": response}

    # ------------------------------------------------------------------
    # Branch 4: Happy path — format tool results using LLM
    # ------------------------------------------------------------------
    response = _format_response(tool_results, plan, user_query)
    logger.info("Responder: generated final_response (%d chars)", len(response))
    return {"final_response": response}


# ---------------------------------------------------------------------------
# Small talk reply helpers
# ---------------------------------------------------------------------------

def _get_small_talk_reply(query: str) -> str:
    """Return a contextually appropriate small talk response."""
    q = query.lower().strip()
    if any(word in q for word in ["thanks", "thank you", "thx", "ty"]):
        return random.choice(_THANKS_RESPONSES)
    if any(word in q for word in ["bye", "goodbye", "see you", "cya"]):
        return "Goodbye! 👋 Come back anytime for train search help. Safe travels!"
    if "how are you" in q or "how r u" in q:
        return "I'm doing great, thank you! Ready to help you find the perfect train. 🚆 Where are you travelling?"
    if "what can you do" in q or "help" in q or "what do you do" in q:
        return (
            "I can help you with:\n"
            "• 🔍 **Search trains** between any two stations\n"
            "• 📅 Check train schedules and availability\n"
            "• 🎟️ Find fares and class options\n\n"
            "Just ask something like: *\"Trains from Mumbai to Delhi on 20 June\"*"
        )
    return random.choice(_SMALL_TALK_RESPONSES)


# ---------------------------------------------------------------------------
# Response formatting — LLM-powered with template fallback
# ---------------------------------------------------------------------------

def _format_response(
    tool_results: Dict[str, Any],
    plan: List[PlanStep],
    user_query: str,
) -> str:
    """Format tool results into a human-readable response using LLM."""

    results_str = json.dumps(tool_results, indent=2, default=str)

    try:
        prompt = RESPONDER_USER_PROMPT_TEMPLATE.format(
            query=user_query,
            tool_results=results_str,
        )
        response = llm_client.generate_text(prompt, system_prompt=RESPONDER_SYSTEM_PROMPT)

        if response and len(response) > 10:
            return response

        logger.warning("Responder: LLM returned empty/short response — using fallback")
        return _fallback_format(tool_results)

    except Exception as exc:
        logger.error("Responder: LLM call failed — using template fallback: %s", exc)
        return _fallback_format(tool_results)


# ---------------------------------------------------------------------------
# Fallback formatting — template-based (used when LLM fails)
# ---------------------------------------------------------------------------

def _fallback_format(tool_results: Dict[str, Any]) -> str:
    """Template-based fallback when LLM is unavailable."""

    search_result = tool_results.get("search_trains", {})
    data = search_result.get("data") if search_result else None

    if data:
        trains = data.get("trains", [])
        total = data.get("total", 0)
        echoed = data.get("query_echoed", {})

        if total == 0:
            return (
                f"No trains found from **{echoed.get('origin', '?')}** "
                f"to **{echoed.get('destination', '?')}** "
                f"on {echoed.get('date', '?')}.\n\n"
                "Try a different date or nearby stations."
            )

        lines = [
            f"Found **{total} train(s)** from "
            f"{echoed.get('origin', '?')} → {echoed.get('destination', '?')} "
            f"on {echoed.get('date', '?')}:\n"
        ]

        for i, train in enumerate(trains, start=1):
            avail = train.get("availability", {})
            status_str = avail.get("status", "N/A")
            fare = avail.get("fare_inr", "N/A")
            days = ", ".join(train.get("days_of_run", []))

            lines.append(
                f"{i}. **{train.get('train_name')} ({train.get('train_number')})**\n"
                f"   🕐 {train.get('departure_time')} → {train.get('arrival_time')} "
                f"({train.get('duration')})\n"
                f"   Class: {avail.get('class', 'N/A')} | Status: {status_str} | "
                f"Fare: ₹{fare}\n"
                f"   Runs on: {days}\n"
            )

        return "\n".join(lines)

    if tool_results:
        summaries = []
        for step_name, result in tool_results.items():
            if result.get("status") == "SUCCESS":
                summaries.append(f"✅ {step_name}: completed successfully.")
            else:
                summaries.append(f"⚠️ {step_name}: {result.get('error', 'failed')}.")
        return "\n".join(summaries)

    return "I couldn't find any information matching your query. Please try again."


def _format_faq_rag_response(user_query: str, chunks: List[Dict[str, Any]]) -> str:
    """
    Generate grounded FAQ answer from retrieved chunks.
    """
    if not chunks:
        return "I don't have that knowledge in my internal FAQ index yet."
    retrieved_context = "\n\n".join(
        [
            f"- Source: {c.get('source', 'internal_faq')}\n  Content: {c.get('text', '')}"
            for c in chunks
            if c.get("text")
        ]
    )
    if not retrieved_context.strip():
        return "I don't have that knowledge in my internal FAQ index yet."
    try:
        prompt = FAQ_RAG_RESPONDER_USER_PROMPT_TEMPLATE.format(
            query=user_query,
            retrieved_chunks=retrieved_context,
        )
        logger.info(
            "Responder: FAQ_RAG prompt built with %d chunks; sample context=%r",
            len(chunks),
            retrieved_context[:300],
        )
        logger.info("Responder: FAQ_RAG full prompt length=%d", len(prompt))
        logger.debug("Responder: FAQ_RAG full prompt: %s", prompt)
        response = llm_client.generate_text(
            prompt=prompt,
            system_prompt=FAQ_RAG_RESPONDER_SYSTEM_PROMPT,
        )
        response = (response or "").strip()
        no_knowledge_phrase = "i don't have that knowledge in my internal faq index yet"
        if response and len(response) > 10 and no_knowledge_phrase not in response.lower():
            return response

        logger.warning(
            "Responder: FAQ_RAG LLM returned empty/short/no-knowledge response — using chunk fallback"
        )
        logger.debug("Responder: FAQ_RAG prompt: %s", prompt)
        logger.debug("Responder: FAQ_RAG response: %r", response)
        return _fallback_faq_rag_response(chunks)
    except Exception as exc:
        logger.error("Responder: FAQ_RAG response generation failed: %s", exc)
        return _fallback_faq_rag_response(chunks)


def _fallback_faq_rag_response(chunks: List[Dict[str, Any]]) -> str:
    """Fallback response when FAQ RAG LLM generation fails or returns nothing."""
    if not chunks:
        return "I don't have that knowledge in my internal FAQ index yet."

    bullet_lines = []
    for chunk in chunks[:3]:
        text = chunk.get("text", "").strip()
        if not text:
            continue
        source = chunk.get("source", "internal_faq")
        snippet = text.replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:197].rstrip() + "..."
        bullet_lines.append(f"- ({source}) {snippet}")

    if not bullet_lines:
        return "I don't have that knowledge in my internal FAQ index yet."

    return "I found relevant information in the FAQ content:\n" + "\n".join(bullet_lines)
