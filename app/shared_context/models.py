"""
SharedContext and MemoryUpdate models.

SharedContext is the central conversational and semantic memory object
that flows through the entire workflow.

Design principles:
  - Immutable after creation (evolves only through merge operations)
  - Contains ONLY semantic understanding and derived knowledge
  - NO rendering concerns, raw tool payloads, or frontend metadata
  - Tool-agnostic (supports any tool)
  - Scalable (new tools don't require schema changes)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SharedContext:
    """
    Central immutable shared memory for the collaborative multi-tool agent system.

    Represents conversational context and semantic understanding extracted from
    user queries and enriched by tool execution.

    OWNERSHIP:
      - Created by SharedContextExtractor after semantic extraction
      - Evolved through tool memory_updates via merge_shared_context
      - Read-only for tools (they read from it, optionally return updates)
      - Passed through entire workflow

    INVARIANTS:
      - All optional fields default to None or empty collections
      - No tool-specific branching; tools read what they need
      - No frontend rendering metadata
      - No raw API payloads or HTML generation

    FIELDS EXPLAINED:

    USER SESSION:
      user_id: Authenticated user identifier (from JWT)
      session_id: Conversation/session UUID

    QUERY UNDERSTANDING:
      original_query: Raw user input text
      intents: Detected intent types (e.g., ["SEARCH_TRAINS", "FAQ_RAG"])

    RAILWAY ENTITIES (extracted from query):
      origin_station: Departure station code (e.g., "NDLS")
      destination_station: Arrival station code (e.g., "CSTM")
      travel_date: Travel date (YYYY-MM-DD format)
      travel_day: Day of week (e.g., "monday") derived from travel_date
      train_class: Travel class (SL, 3A, 2A, 1A, CC, EC, 2S)
      quota: Booking quota (GN, TQ, LD, PT)

    PNR/BOOKING ENTITIES:
      pnr_number: PNR booking reference
      train_number: Specific train number

    POLICY/FAQ:
      policy_topic: FAQ category (e.g., "refund_policy", "cancellation")

    DERIVED KNOWLEDGE (enriched by tool execution):
      latest_user_pnr: Most recent PNR for user (from PNR tool)
      inferred_train_number: Train number derived from PNR (from PNR tool)
      waitlist_detected: Whether PNR is waitlisted (from PNR tool)
      alternate_route_required: Whether alternates needed (multi-tool workflows)

    RAG CONTEXT:
      retrieved_knowledge_chunks: FAQ/document retrieval results

    EXECUTION METADATA:
      executed_tools: Tools that have run successfully
      failed_tools: Tools that failed during execution
    """

    # ========================================================================
    # USER SESSION
    # ========================================================================

    user_id: Optional[str] = None
    session_id: Optional[str] = None

    # ========================================================================
    # QUERY UNDERSTANDING
    # ========================================================================

    original_query: str = ""
    intents: List[str] = field(default_factory=list)

    # ========================================================================
    # RAILWAY ENTITIES
    # ========================================================================

    origin_station: Optional[str] = None
    destination_station: Optional[str] = None
    travel_date: Optional[str] = None
    travel_day: Optional[str] = None
    train_class: Optional[str] = None
    quota: Optional[str] = None

    # ========================================================================
    # PNR/BOOKING ENTITIES
    # ========================================================================

    pnr_number: Optional[str] = None
    train_number: Optional[str] = None

    # ========================================================================
    # POLICY/FAQ ENTITIES
    # ========================================================================

    policy_topic: Optional[str] = None

    # ========================================================================
    # DERIVED KNOWLEDGE (enriched by tool execution)
    # ========================================================================

    latest_user_pnr: Optional[str] = None
    inferred_train_number: Optional[str] = None
    waitlist_detected: bool = False
    alternate_route_required: bool = False

    # ========================================================================
    # RAG CONTEXT (retrieved documents/FAQ chunks)
    # ========================================================================

    retrieved_knowledge_chunks: List[Dict[str, Any]] = field(default_factory=list)

    # ========================================================================
    # EXECUTION METADATA
    # ========================================================================

    executed_tools: List[str] = field(default_factory=list)
    failed_tools: List[str] = field(default_factory=list)

    def copy(self) -> SharedContext:
        """Create a shallow copy of this context."""
        return SharedContext(
            user_id=self.user_id,
            session_id=self.session_id,
            original_query=self.original_query,
            intents=list(self.intents),
            origin_station=self.origin_station,
            destination_station=self.destination_station,
            travel_date=self.travel_date,
            travel_day=self.travel_day,
            train_class=self.train_class,
            quota=self.quota,
            pnr_number=self.pnr_number,
            train_number=self.train_number,
            policy_topic=self.policy_topic,
            latest_user_pnr=self.latest_user_pnr,
            inferred_train_number=self.inferred_train_number,
            waitlist_detected=self.waitlist_detected,
            alternate_route_required=self.alternate_route_required,
            retrieved_knowledge_chunks=list(self.retrieved_knowledge_chunks),
            executed_tools=list(self.executed_tools),
            failed_tools=list(self.failed_tools),
        )


@dataclass
class MemoryUpdate:
    """
    Represents updates to SharedContext returned by a tool.

    Tools do NOT mutate SharedContext directly. Instead, they return a MemoryUpdate
    which is merged safely into SharedContext by the tool node.

    DESIGN:
      - All fields optional (tools only update what they know about)
      - Merger only overwrites None values with updates
      - Supports append-only operations (e.g., adding chunks, executed tools)

    FIELDS:
      origin_station: Override origin (rarely used)
      destination_station: Override destination
      travel_date: Override travel date
      travel_day: Override travel day
      train_class: Override class
      quota: Override quota
      pnr_number: Override PNR
      train_number: New train number (discovered by PNR tool)
      policy_topic: Override policy topic
      latest_user_pnr: Set most recent PNR (PNR tool)
      inferred_train_number: Infer train number from PNR
      waitlist_detected: Flag waitlist status
      alternate_route_required: Flag if alternates needed
      append_chunks: Append FAQ chunks (not replace)
      append_executed_tool: Add tool name to executed_tools list
      append_failed_tool: Add tool name to failed_tools list
    """

    origin_station: Optional[str] = None
    destination_station: Optional[str] = None
    travel_date: Optional[str] = None
    travel_day: Optional[str] = None
    train_class: Optional[str] = None
    quota: Optional[str] = None
    pnr_number: Optional[str] = None
    train_number: Optional[str] = None
    policy_topic: Optional[str] = None
    latest_user_pnr: Optional[str] = None
    inferred_train_number: Optional[str] = None
    waitlist_detected: Optional[bool] = None
    alternate_route_required: Optional[bool] = None
    append_chunks: List[Dict[str, Any]] = field(default_factory=list)
    append_executed_tool: Optional[str] = None
    append_failed_tool: Optional[str] = None
