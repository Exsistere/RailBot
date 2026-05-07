"""
FAQRAGTool — Context enrichment tool for FAQ/policy retrieval.

DESIGN:
  - Retrieves FAQ/policy chunks from Qdrant
  - Stores chunks in shared_context.retrieved_knowledge_chunks
  - Does NOT generate final answers (responder does that)
  - Enables RAG-aware response generation across all tools

Memory updates:
  - Appends retrieved chunks to shared_context
  - Responder synthesizes answers using chunks
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.models.state import GraphState
from app.services.rag_service import RAGService
from app.tools.base_tool import BaseTool, ToolValidationError

logger = logging.getLogger(__name__)


class FAQRAGTool(BaseTool):
    """
    FAQ/Policy retrieval and context enrichment tool.

    Behavior:
      1. Retrieve chunks from Qdrant based on user query
      2. Return structured chunk data
      3. Append chunks to shared_context via memory_updates

    This tool is a CONTEXT ENRICHMENT TOOL, not an answer generator.
    The responder uses chunks + other tool results to synthesize final answer.
    """

    def __init__(self, rag_service: RAGService) -> None:
        self._rag_service = rag_service

    def _validate(self, state: GraphState) -> None:
        if not (state.get("user_query") or "").strip():
            raise ToolValidationError("user_query is required for FAQ retrieval")

    def _fetch_data(self, state: GraphState) -> Dict[str, Any]:
        query = state.get("user_query", "")
        logger.info("FAQRAGTool: retrieving chunks for query=%r", query[:80])
        raw_data = self._rag_service.retrieve(query)
        chunks = raw_data.get("chunks", [])
        if chunks:
            sample = chunks[0]
            sample_text = sample.get("text", "")
            logger.info(
                "FAQRAGTool: retrieved %d chunks; sample chunk source=%s text=%r",
                len(chunks),
                sample.get("source", "unknown"),
                sample_text[:200],
            )
            for i, chunk in enumerate(chunks):
                logger.debug(
                    "FAQRAGTool: chunk %d (source=%s): %s...",
                    i + 1,
                    chunk.get("source", "unknown"),
                    chunk.get("text", "")[:100],
                )
        else:
            logger.info("FAQRAGTool: retrieved 0 chunks")
        return raw_data

    def _process(self, raw_data: Dict[str, Any], state: GraphState) -> Dict[str, Any]:
        """
        Normalize RAG retrieval output.

        Returns structured chunk data (no answer generation).
        """
        chunks = raw_data.get("chunks", [])
        return {
            "message": "",
            "response_type": "RAG_CONTEXT",  # Not a final answer
            "data": {
                "chunks": chunks,
                "sources": raw_data.get("sources", []),
            },
        }

    def _get_memory_updates(self, result: Any, state: GraphState) -> Dict[str, Any]:
        """
        Return memory updates to append chunks to shared_context.

        This enables the responder and other tools to access retrieved chunks.
        """
        data = result.get("data", {}) if isinstance(result, dict) else {}
        chunks = data.get("chunks", [])

        if chunks:
            logger.debug(f"FAQRAGTool: appending {len(chunks)} chunks to shared_context")
            return {"append_chunks": chunks}

        return {}

