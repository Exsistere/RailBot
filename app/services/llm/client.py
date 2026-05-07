"""
LLM Client — centralised access to the Groq-hosted OpenAI-compatible API.

All LLM calls across the application flow through this module.
Nodes NEVER call the Groq/OpenAI SDK directly.

Features:
  - Exponential backoff retries (via tenacity)
  - Timeout handling
  - Deterministic settings (temperature=0)
  - Structured JSON generation + plain text generation
  - Graceful error surfacing (never crashes the caller)
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (environment-driven)
# ---------------------------------------------------------------------------

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """Lazily initialise and return the OpenAI-compatible client."""
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY environment variable is not set. "
                "Set it to use LLM features."
            )
        _client = OpenAI(
            api_key=GROQ_API_KEY,
            base_url=GROQ_BASE_URL,
            timeout=LLM_TIMEOUT_SECONDS,
        )
        logger.info("LLM client initialised — model=%s", LLM_MODEL)
    return _client


# ---------------------------------------------------------------------------
# Retry decorator — shared by both public methods
# ---------------------------------------------------------------------------

_retry_decorator = retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_json(prompt: str, system_prompt: str = "") -> Dict[str, Any]:
    """
    Send a prompt to the LLM and parse the response as JSON.

    Args:
        prompt: The user/task prompt.
        system_prompt: Optional system message to set behaviour.

    Returns:
        Parsed JSON dict from the LLM response.

    Raises:
        ValueError: If the response cannot be parsed as valid JSON.
        RuntimeError: If the LLM call fails after retries.
    """
    raw = _call_llm(prompt, system_prompt)
    return _extract_json(raw)


def generate_text(prompt: str, system_prompt: str = "") -> str:
    """
    Send a prompt to the LLM and return the raw text response.

    Args:
        prompt: The user/task prompt.
        system_prompt: Optional system message to set behaviour.

    Returns:
        Plain text string from the LLM.

    Raises:
        RuntimeError: If the LLM call fails after retries.
    """
    return _call_llm(prompt, system_prompt)


# ---------------------------------------------------------------------------
# Internal — LLM call with retries
# ---------------------------------------------------------------------------

@_retry_decorator
def _call_llm(prompt: str, system_prompt: str = "") -> str:
    """
    Make a single chat completion call with retry logic.

    Uses temperature=0 for deterministic output.
    """
    client = _get_client()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    start = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=2048,
        )
        latency = time.monotonic() - start

        content = response.choices[0].message.content or ""
        logger.info(
            "LLM call | model=%s | latency=%.2fs | prompt_chars=%d | response_chars=%d",
            LLM_MODEL,
            latency,
            len(prompt),
            len(content),
        )
        return content.strip()

    except Exception as exc:
        latency = time.monotonic() - start
        logger.error(
            "LLM call FAILED | model=%s | latency=%.2fs | error=%s",
            LLM_MODEL,
            latency,
            exc,
        )
        raise


# ---------------------------------------------------------------------------
# Internal — JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> Dict[str, Any]:
    """
    Extract a JSON object from LLM output.

    Handles common issues:
      - Markdown code fences (```json ... ```)
      - Leading/trailing text around JSON
      - Nested JSON within prose
    """
    # Strip markdown code fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        cleaned = cleaned[first_newline + 1:]
        # Remove closing fence
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].rstrip()

    # Try direct parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return {"items": parsed}
        return parsed
    except json.JSONDecodeError:
        pass

    # Try to find JSON object boundaries
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Try to find JSON array boundaries
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start:end + 1])
            return {"items": parsed}  # Wrap array in dict
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse JSON from LLM response: %r", raw[:200])
    raise ValueError(f"Could not extract valid JSON from LLM response: {raw[:200]}")
