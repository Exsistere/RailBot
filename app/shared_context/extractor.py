"""
SharedContextExtractor — Unified query understanding for collaborative agent system.

Responsibilities:
  - One LLM call per query to build generalized understanding
  - Populate SharedContext with semantic entities
  - Normalize railway entities (stations, dates, classes, quotas)
  - Extract: stations, dates, train class, quota, PNR, train number, policy topics
  - No planner logic, no DB calls, no tool execution, no response generation

Output: SharedContext (not tool params)

Design: Refactored from existing SemanticExtractor with focus on SharedContext.
"""

from __future__ import annotations

import logging
import json
from typing import Any, Callable, Optional, Protocol

from app.shared_context.models import SharedContext
from app.nlp.station_resolver import (
    StationResolver,
    TrainClassResolver,
    QuotaResolver,
)

logger = logging.getLogger(__name__)


class LLMClientLike(Protocol):
    """Protocol for LLM client that supports JSON generation."""
    def generate_json(self, prompt: str, system_prompt: str = "") -> dict: ...


class SharedContextExtractor:
    """
    Unified extractor that builds SharedContext from user query.

    Makes exactly ONE LLM call per query to extract railway entities.
    Normalizes and canonicalizes extracted values.
    Returns immutable SharedContext for downstream consumption.

    RESPONSIBILITIES:
      - Parse user query with LLM
      - Extract generic railway entities
      - Normalize station codes, dates, classes, quotas
      - Populate SharedContext
      - Handle failures gracefully (return partial context)

    NOT RESPONSIBILITIES:
      - Tool-specific param extraction (done by tool layer)
      - Response generation (done by responder)
      - Planner logic (done by planner node)
      - DB operations (done by services)

    Usage:
        extractor = SharedContextExtractor(llm_client, station_resolver, ...)
        shared_ctx = extractor.extract("Delhi to Mumbai on 15 June", intents=["SEARCH_TRAINS"])
    """

    def __init__(
        self,
        llm_client: LLMClientLike,
        station_resolver: Optional[StationResolver] = None,
        train_class_resolver: Optional[TrainClassResolver] = None,
        quota_resolver: Optional[QuotaResolver] = None,
    ):
        """
        Initialize the extractor.

        Args:
            llm_client: LLM client with generate_json(prompt, system_prompt) method
            station_resolver: Resolver for station normalization (optional)
            train_class_resolver: Resolver for train class codes (optional)
            quota_resolver: Resolver for quota codes (optional)
        """
        self.llm_client = llm_client
        self.station_resolver = station_resolver or StationResolver()
        self.train_class_resolver = train_class_resolver or TrainClassResolver()
        self.quota_resolver = quota_resolver or QuotaResolver()

    def extract(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        intent_hints: Optional[list[str]] = None,
    ) -> SharedContext:
        """
        Extract semantic context from user query.

        Makes exactly ONE LLM call to extract all railway entities.

        Args:
            query: Raw user input
            user_id: Authenticated user ID (optional)
            session_id: Session UUID (optional)
            intent_hints: Detected intents (e.g., ["SEARCH_TRAINS"]) to guide extraction

        Returns:
            SharedContext with extracted entities
            On failure, returns partial context with available fields
        """
        logger.info(f"SharedContextExtractor: extracting from query='{query[:80]}'...")

        # Build prompt context
        intent_context = ""
        if intent_hints:
            intent_context = f"\nDetected intents: {', '.join(intent_hints)}\nUse these to guide extraction."

        # Call LLM once to extract all entities
        try:
            llm_response = self.llm_client.generate_json(
                prompt=_build_extraction_prompt(query, intent_context),
                system_prompt=_EXTRACTION_SYSTEM_PROMPT,
            )
        except Exception as exc:
            logger.error(f"SharedContextExtractor: LLM call failed: {exc}")
            # Return partial context on failure
            return SharedContext(
                user_id=user_id,
                session_id=session_id,
                original_query=query,
                intents=intent_hints or [],
            )

        # Parse and normalize extracted entities
        context = self._build_shared_context(
            llm_response,
            query=query,
            user_id=user_id,
            session_id=session_id,
            intent_hints=intent_hints,
        )

        logger.info(
            f"SharedContextExtractor: extracted context with "
            f"origin={context.origin_station}, dest={context.destination_station}, "
            f"date={context.travel_date}, pnr={context.pnr_number}"
        )
        return context

    def _build_shared_context(
        self,
        llm_data: dict,
        query: str,
        user_id: Optional[str],
        session_id: Optional[str],
        intent_hints: Optional[list[str]],
    ) -> SharedContext:
        """
        Build SharedContext from LLM extraction output.

        Normalizes and canonicalizes extracted values.
        """
        # Extract raw values from LLM response
        origin_raw = llm_data.get("origin_station", "").strip()
        destination_raw = llm_data.get("destination_station", "").strip()
        travel_date_raw = llm_data.get("travel_date", "").strip()
        train_class_raw = llm_data.get("train_class", "").strip()
        quota_raw = llm_data.get("quota", "").strip()
        pnr_raw = llm_data.get("pnr_number", "").strip()
        train_number_raw = llm_data.get("train_number", "").strip()
        policy_topic_raw = llm_data.get("policy_topic", "").strip()

        # Normalize using resolvers
        origin_station = self.station_resolver.resolve(origin_raw) if origin_raw else None
        destination_station = self.station_resolver.resolve(destination_raw) if destination_raw else None
        train_class = self.train_class_resolver.resolve(train_class_raw) if train_class_raw else None
        quota = self.quota_resolver.resolve(quota_raw) if quota_raw else None

        # Compute travel_day from travel_date if available
        travel_day = None
        if travel_date_raw:
            try:
                from app.nlp.date_utils import date_to_weekday
                travel_day = date_to_weekday(travel_date_raw)
            except Exception as exc:
                logger.debug(f"Could not derive weekday from {travel_date_raw}: {exc}")

        return SharedContext(
            user_id=user_id,
            session_id=session_id,
            original_query=query,
            intents=intent_hints or [],
            origin_station=origin_station,
            destination_station=destination_station,
            travel_date=travel_date_raw if travel_date_raw else None,
            travel_day=travel_day,
            train_class=train_class,
            quota=quota or "GN",  # Default to General quota
            pnr_number=pnr_raw if pnr_raw else None,
            train_number=train_number_raw if train_number_raw else None,
            policy_topic=policy_topic_raw if policy_topic_raw else None,
        )


# ============================================================================
# PROMPTS
# ============================================================================

_EXTRACTION_SYSTEM_PROMPT = """\
You are a semantic extractor for a railway travel assistant.

Your job is to extract railway-related entities from user queries.

Extract the following entities if present in the query:
- origin_station: Departure station (city name or code, e.g., "New Delhi", "Delhi", "NDLS")
- destination_station: Arrival station (city name or code, e.g., "Mumbai", "CST", "CSTM")
- travel_date: Travel date. If relative (today, tomorrow, next Monday), convert to YYYY-MM-DD.
  Use current date context if provided. Do NOT hallucinate dates.
- travel_day: Day of week if mentioned (e.g., "Monday", "tuesday")
- train_class: Travel class if specified (e.g., "sleeper", "AC", "3A", "second AC")
- quota: Booking quota if specified (e.g., "general", "tatkal", "ladies")
- pnr_number: PNR reference number if provided
- train_number: Specific train number if provided
- policy_topic: If user asks FAQ/policy questions, extract topic (e.g., "refund", "cancellation", "tatkal")

Rules:
- Extract ONLY information explicitly stated or clearly implied
- Do NOT hallucinate entities not in the query
- Return empty string for missing entities
- Be conservative — if unsure, return empty rather than guess

Respond with ONLY a JSON object. No other text."""


def _build_extraction_prompt(query: str, intent_context: str = "") -> str:
    """Build the extraction prompt for LLM."""
    return f"""\
Extract railway entities from this user query.

User query: "{query}"{intent_context}

Respond with exactly this JSON format:
{{
  "origin_station": "city or station code or empty string",
  "destination_station": "city or station code or empty string",
  "travel_date": "YYYY-MM-DD or empty string",
  "travel_day": "day name or empty string",
  "train_class": "class code/name or empty string",
  "quota": "quota type or empty string",
  "pnr_number": "PNR reference or empty string",
  "train_number": "train number or empty string",
  "policy_topic": "FAQ topic or empty string"
}}"""
