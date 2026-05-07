"""
GraphState and sub-schema definitions.

All fields are Optional — nodes must handle missing values gracefully.
State is append-only: fields are never deleted or overwritten with degraded data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict

# TYPE_CHECKING import to avoid circular dependency
try:
    from app.nlp.semantic_schema import SemanticContext
except ImportError:
    SemanticContext = Any  # Fallback if NLP module not yet available


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------

class Intent(TypedDict, total=False):
    """Detected intent with confidence score."""
    type: str          # e.g. "SEARCH_TRAINS" | "SMALL_TALK" | "UNKNOWN"
    confidence: float  # 0.0 – 1.0


class PlanStep(TypedDict, total=False):
    """
    A single step in the execution plan.

    INVARIANT: `step` MUST exactly match a key in TOOL_REGISTRY.
    The Planner is responsible for producing valid keys.

    Status lifecycle: PENDING → RUNNING → COMPLETED | FAILED
    """
    step: str            # Registry key, e.g. "search_trains"
    status: str          # PENDING | RUNNING | COMPLETED | FAILED
    result: Any          # Raw output from tool; None until executed
    params: Dict[str, Any]  # Planner-extracted slots; tools read from here


# ---------------------------------------------------------------------------
# GraphState — single shared data envelope
# ---------------------------------------------------------------------------

class GraphState(TypedDict, total=False):
    """
    The single shared data envelope passed through every LangGraph node.

    Nodes communicate exclusively through this state — never directly.
    Fields are never deleted; downstream nodes can trust set values.

    Ownership:
        user_query          → Written by Application Layer (API route)
        user_id             → Written by Application Layer (from JWT)
        conversation_id     → Written by Application Layer (ConversationService)
        message_history     → Written by Application Layer (ConversationService)
        is_safe             → Written by Guardrail Node
        attack_type         → Written by Guardrail Node
        intents             → Written by Intent Classifier Node
        plan                → Written by Planner Node
        current_step_index  → Written by Planner (init=0), Router Node
        retry_counts        → Written by Router Node
        tool_results        → Written by Tool Node
        final_response      → Written by Responder Node
    """

    # -- Application Layer --
    user_query: str                              # Raw NL input; never mutated after set
    user_id: str                                 # Authenticated user identifier (from JWT)
    conversation_id: Optional[str]               # Active conversation UUID (from ConversationService)
    message_history: Optional[List[Dict[str, Any]]]  # Recent messages: [{role, content, created_at}]

    # -- Guardrail Node --
    is_safe: Optional[bool]                      # True=safe, False=flagged, None=unevaluated
    attack_type: Optional[str]                   # PROMPT_INJECTION | JAILBREAK | PII_LEAK | HATE_SPEECH | OTHER | None

    # -- Intent Classifier Node --
    intents: List[Intent]                        # Sorted by confidence DESC

    # -- Semantic Extraction (Planner Node) --
    semantic_context: Optional[SemanticContext]  # WRITE-ONCE immutable context populated by Planner
                                                  # Contains: origin_station, destination_station, travel_date,
                                                  # day_mentioned, pnr_number, train_number, train_class, quota, etc.
                                                  # ALL downstream consumers treat this as read-only.
                                                  # Normalized and canonical values only.

    # -- Planner Node --
    plan: List[PlanStep]                         # Ordered execution steps
    current_step_index: int                      # Zero-based pointer into plan[]

    # -- Router Node --
    retry_counts: Dict[int, int]                 # { step_index: retry_count }

    # -- Tool Node --
    tool_results: Dict[str, Any]                 # { step_name: { status, data, error } }

    # -- Responder Node --
    final_response: Optional[str]                # Human-readable reply; None until Responder runs
