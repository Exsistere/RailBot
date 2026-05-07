"""
Node [Re] — Universal Responder Node.

Synthesises tool_results into a coherent natural-language response.

NEW FLOW (Shared Context Based):
  - Reads shared_context for semantic understanding
  - Reads tool_results for execution data
  - Uses universal LLM prompt (no tool-specific branching)
  - Supports multi-tool workflows naturally
  - Future tools require ZERO responder changes

Owned state mutations: final_response ONLY.

Design: Universal synthesis instead of tool-specific branches.
All synthesis logic lives in LLM prompts, not Python branching.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any, Dict, List, Optional

from app.models.state import GraphState, Intent
from app.services.llm import client as llm_client
from app.services.llm.prompts import (
    UNIVERSAL_RESPONDER_SYSTEM_PROMPT,
    UNIVERSAL_RESPONDER_USER_PROMPT_TEMPLATE,
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

    NEW FLOW:
      1. Check safety status — echo Guardrail refusal if unsafe
      2. Check for SMALL_TALK — return friendly reply
      3. Check for empty plan — return capability hint
      4. Check for all-failed plan — return failure message
      5. UNIVERSAL PATH — LLM synthesis for all other cases

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
    user_query: str = state.get("user_query", "")
    plan: List[Dict] = state.get("plan", [])
    tool_results: Dict[str, Any] = state.get("tool_results", {})
    shared_context = state.get("shared_context")

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
    all_failed = all(step.get("status") == "FAILED" for step in plan if step.get("status"))
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
    # Branch 4: UNIVERSAL SYNTHESIS PATH
    # ------------------------------------------------------------------
    # Use shared_context + tool_results for universal synthesis
    response = _synthesize_response(
        query=user_query,
        shared_context=shared_context,
        tool_results=tool_results,
    )
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
# Universal Response Synthesis — LLM-powered
# ---------------------------------------------------------------------------

def _synthesize_response(
    query: str,
    shared_context: Optional[Any],
    tool_results: Dict[str, Any],
) -> str:
    """
    Synthesize a universal response from shared_context and tool_results.

    Uses LLM to intelligently combine tool outputs without branching logic.
    Falls back to fallback formatting if LLM fails.
    """
    # Extract context fields
    origin = ""
    destination = ""
    travel_date = ""
    train_class = ""
    quota = ""
    pnr_number = ""
    executed_tools = []
    failed_tools = []
    retrieved_chunks = []

    if shared_context:
        origin = shared_context.origin_station or ""
        destination = shared_context.destination_station or ""
        travel_date = shared_context.travel_date or ""
        train_class = shared_context.train_class or ""
        quota = shared_context.quota or ""
        pnr_number = shared_context.pnr_number or ""
        executed_tools = shared_context.executed_tools or []
        failed_tools = shared_context.failed_tools or []
        retrieved_chunks = shared_context.retrieved_knowledge_chunks or []

    # Format tool results for prompt
    tool_results_json = json.dumps(tool_results, indent=2, default=str) if tool_results else "{}"

    # Format retrieved chunks
    chunks_text = ""
    if retrieved_chunks:
        chunk_strs = []
        for chunk in retrieved_chunks[:3]:  # Limit to first 3 chunks
            text = chunk.get("text", "").strip()
            source = chunk.get("source", "FAQ")
            if text:
                chunk_strs.append(f"({source}) {text[:300]}")
        chunks_text = "\n".join(chunk_strs) if chunk_strs else "No chunks retrieved"
    else:
        chunks_text = "No FAQ chunks retrieved"

    try:
        prompt = UNIVERSAL_RESPONDER_USER_PROMPT_TEMPLATE.format(
            query=query,
            origin_station=origin,
            destination_station=destination,
            travel_date=travel_date,
            train_class=train_class,
            quota=quota,
            pnr_number=pnr_number,
            tool_results_json=tool_results_json,
            retrieved_chunks=chunks_text,
            executed_tools=", ".join(executed_tools) if executed_tools else "none",
            failed_tools=", ".join(failed_tools) if failed_tools else "none",
        )

        response = llm_client.generate_text(
            prompt,
            system_prompt=UNIVERSAL_RESPONDER_SYSTEM_PROMPT
        )

        if response and len(response) > 10:
            return response

        logger.warning("Responder: LLM returned empty/short response — using fallback")
        return _fallback_synthesis(tool_results, executed_tools, failed_tools)

    except Exception as exc:
        logger.error("Responder: LLM synthesis failed — using fallback: %s", exc)
        return _fallback_synthesis(tool_results, executed_tools, failed_tools)


# ---------------------------------------------------------------------------
# Fallback synthesis when LLM fails
# ---------------------------------------------------------------------------

def _fallback_synthesis(
    tool_results: Dict[str, Any],
    executed_tools: List[str],
    failed_tools: List[str],
) -> str:
    """
    Fallback response when universal LLM synthesis fails.

    Formats available tool results plainly without complex logic.
    """
    if not tool_results:
        return "I couldn't find any information matching your query. Please try again."

    # Try to extract train search results
    search_result = tool_results.get("search_trains", {})
    if search_result.get("status") == "SUCCESS":
        data = search_result.get("data", {})
        trains = data.get("trains", [])
        total = data.get("total", 0)
        echoed = data.get("query_echoed", {})

        if total == 0:
            return (
                f"No trains found from {echoed.get('origin', '?')} "
                f"to {echoed.get('destination', '?')} "
                f"on {echoed.get('date', '?')}. Try a different date or nearby stations."
            )

        lines = [
            f"Found {total} train(s) from "
            f"{echoed.get('origin', '?')} → {echoed.get('destination', '?')} "
            f"on {echoed.get('date', '?')}:\n"
        ]

        for i, train in enumerate(trains[:5], start=1):
            avail = train.get("availability", {})
            fare = avail.get("fare_inr", "N/A")
            lines.append(
                f"{i}. {train.get('train_name')} ({train.get('train_number')})\n"
                f"   {train.get('departure_time')} → {train.get('arrival_time')} "
                f"({train.get('duration')})\n"
                f"   {avail.get('class', 'N/A')} | {avail.get('status', 'N/A')} | ₹{fare}\n"
            )

        return "\n".join(lines)

    # Try PNR result
    pnr_result = tool_results.get("check_pnr_status", {})
    if pnr_result.get("status") == "SUCCESS":
        data = pnr_result.get("data", {})
        if data:
            return data.get("message", "PNR information retrieved successfully.")

    # Fallback: generic tool summary
    summaries = []
    for tool_name in executed_tools:
        summaries.append(f"✅ {tool_name}: completed")
    for tool_name in failed_tools:
        summaries.append(f"⚠️ {tool_name}: failed")

    if summaries:
        return "Tool execution summary:\n" + "\n".join(summaries)

    return "Your request was processed but no results were available."

