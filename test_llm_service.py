"""Quick verification script for the LLM service layer."""

from app.services.llm.client import _extract_json
from app.services.llm.parser import (
    parse_guardrail_response,
    parse_intent_response,
    parse_planner_params,
)

# --- JSON extraction tests ---
r = _extract_json('{"is_safe": true}')
assert r == {"is_safe": True}, f"FAIL plain: {r}"

r = _extract_json('```json\n{"type": "SEARCH_TRAINS"}\n```')
assert r == {"type": "SEARCH_TRAINS"}, f"FAIL fenced: {r}"

r = _extract_json('Result: {"is_safe": false, "attack_type": "JAILBREAK"} done')
assert r["attack_type"] == "JAILBREAK", f"FAIL embedded: {r}"

r = _extract_json('[{"type": "SEARCH_TRAINS"}]')
assert "items" in r, f"FAIL array: {r}"

# --- Parser tests ---
r = parse_guardrail_response({"is_safe": True, "attack_type": None})
assert r == {"is_safe": True, "attack_type": None}

r = parse_guardrail_response({"is_safe": False, "attack_type": "JAILBREAK"})
assert r == {"is_safe": False, "attack_type": "JAILBREAK"}

r = parse_guardrail_response({"is_safe": "yes"})
assert r["is_safe"] is False  # fail closed

r = parse_intent_response({"intents": [{"type": "SEARCH_TRAINS", "confidence": 0.95}]})
assert r[0]["type"] == "SEARCH_TRAINS"

r = parse_intent_response({"intents": []})
assert r[0]["type"] == "UNKNOWN"

r = parse_planner_params({
    "origin_station": "NDLS",
    "destination_station": "BCT",
    "travel_date": "2026-06-10",
    "train_class": "SL",
    "quota": "GN",
})
assert r["origin_station"] == "NDLS"

r = parse_planner_params({})
assert r["quota"] == "GN"

print("All LLM service tests PASSED")
