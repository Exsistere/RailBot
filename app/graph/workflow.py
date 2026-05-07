"""
LangGraph Workflow — StateGraph construction and compilation.

This module is the single wiring point for the entire graph:
  - Declares all nodes
  - Declares all edges (fixed + conditional)
  - Injects service dependencies into nodes that need them
  - Compiles and returns the runnable graph

Graph topology (per LLD — UNCHANGED):

    [Entry]
       ↓
   [G] guardrail
       ↓ is_safe=True           ↘ is_safe=False
   [I] intent_classifier        [L] logger → END
       ↓
   [P] planner
       ↓
   [R] router  ←─────────────────────────────────┐
       ↓ step in TOOL_REGISTRY                    │
   [T] tool_node ────────────────────────────────→┘
       ↓ index >= len(plan)
   [Re] responder
       ↓
   [L] logger
       ↓
   END
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app.models.state import GraphState

# Nodes
from app.graph.nodes.guardrail import guardrail_node
from app.graph.nodes.intent_classifier import intent_classifier_node
from app.graph.nodes.planner import planner_node
from app.graph.nodes.router_node import router_node
from app.graph.nodes.router_edges import route_after_guardrail, route_from_router
from app.graph.nodes.tool_node import tool_node, set_tool_factory
from app.graph.nodes.responder import responder_node
from app.graph.nodes.logger_node import logger_node, set_interaction_service

# Services + repositories
from app.services.db.connection import db_manager
from app.services.db.interaction_repository import InteractionRepository
from app.services.db.pnr_repository import PNRRepository
from app.services.db.tool_execution_repository import ToolExecutionRepository
from app.services.db.user_pnr_repository import UserPNRRepository
from app.services.railway_api_client import RailwayAPIClient
from app.services.rag_service import RAGService
from app.services.pnr_service import PNRService
from app.services.train_service import TrainService
from app.services.logging_service import LoggingService
from app.services.interaction_service import InteractionService
from app.services.llm import client as llm_client
from app.services.llm.parser import parse_semantic_extraction

# NLP (semantic extraction)
from app.nlp.semantic_extractor import SemanticExtractor

# Tools
from app.tools.registry import ToolFactory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service + dependency wiring
# ---------------------------------------------------------------------------

def _build_services():
    """
    Construct and wire all service dependencies.
    Called once at graph compilation time.
    """
    # Repositories (depend on db_manager singleton)
    interaction_repo = InteractionRepository(db_manager)
    tool_execution_repo = ToolExecutionRepository(db_manager)
    pnr_repo = PNRRepository(db_manager)
    user_pnr_repo = UserPNRRepository(db_manager)

    # External clients
    api_client = RailwayAPIClient()

    # Services
    train_service = TrainService(api_client)
    pnr_service = PNRService(
        pnr_repo=pnr_repo,
        user_pnr_repo=user_pnr_repo,
        railway_api_client=api_client,
    )
    rag_service = RAGService()
    logging_service = LoggingService(interaction_repo, tool_execution_repo)
    interaction_service = InteractionService(logging_service)

    # NEW: Semantic Extractor (ONE LLM call per query)
    semantic_extractor = SemanticExtractor(
        llm_client=llm_client,
        parser=parse_semantic_extraction,  # Module-level function
        cache_enabled=False,  # Caching hook available for future use
    )

    return train_service, pnr_service, rag_service, interaction_service, semantic_extractor


def _build_tool_factory(
    train_service: TrainService,
    pnr_service: PNRService,
    rag_service: RAGService,
) -> ToolFactory:
    """Create the ToolFactory with all available services."""
    return ToolFactory(
        train_service=train_service,
        pnr_service=pnr_service,
        rag_service=rag_service,
    )


# ---------------------------------------------------------------------------
# Graph compilation
# ---------------------------------------------------------------------------

def compile_graph():
    """
    Build, wire, and compile the LangGraph StateGraph.

    Returns a compiled Runnable that accepts a GraphState dict
    and returns the final GraphState dict.
    """
    # 1 — Build services
    train_service, pnr_service, rag_service, interaction_service, semantic_extractor = _build_services()

    # 2 — Inject dependencies into nodes that require them
    tool_factory = _build_tool_factory(train_service, pnr_service, rag_service)
    set_tool_factory(tool_factory)
    set_interaction_service(interaction_service)

    # NEW: Wrap planner_node to inject semantic_extractor
    def planner_node_with_extractor(state):
        return planner_node(state, semantic_extractor=semantic_extractor)

    # 3 — Construct graph
    graph = StateGraph(GraphState)

    # Register nodes
    graph.add_node("guardrail",         guardrail_node)
    graph.add_node("intent_classifier", intent_classifier_node)
    graph.add_node("planner",           planner_node_with_extractor)  # NEW: Use wrapper
    graph.add_node("router",            router_node)
    graph.add_node("tool_node",         tool_node)
    graph.add_node("responder",         responder_node)
    graph.add_node("logger",            logger_node)

    # Entry point
    graph.set_entry_point("guardrail")

    # Guardrail → conditional split
    graph.add_conditional_edges(
        "guardrail",
        route_after_guardrail,
        {
            "intent_classifier": "intent_classifier",
            "logger":            "logger",          # unsafe → skip all, go to logger
        },
    )

    # Linear pipeline: intent → planner → router
    graph.add_edge("intent_classifier", "planner")
    graph.add_edge("planner",           "router")

    # Router → conditional dispatch (tool or responder)
    graph.add_conditional_edges(
        "router",
        route_from_router,
        {
            "tool_node": "tool_node",
            "responder": "responder",
        },
    )

    # Tool always returns to router (creates the plan execution loop)
    graph.add_edge("tool_node", "router")

    # Responder → logger → END
    graph.add_edge("responder", "logger")
    graph.add_edge("logger",    END)

    # 4 — Compile
    compiled = graph.compile()
    logger.info("LangGraph workflow compiled successfully")
    return compiled


# ---------------------------------------------------------------------------
# Module-level compiled graph — imported by API routes
# ---------------------------------------------------------------------------

compiled_graph = compile_graph()
