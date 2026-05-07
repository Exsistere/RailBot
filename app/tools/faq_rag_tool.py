"""
FAQRAGTool — concrete tool for "faq_rag" step.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.models.state import GraphState
from app.services.rag_service import RAGService
from app.tools.base_tool import BaseTool, ToolValidationError

logger = logging.getLogger(__name__)


class FAQRAGTool(BaseTool):
    """Thin tool wrapper around RAGService."""

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
                logger.debug("FAQRAGTool: chunk %d (source=%s): %s...", i+1, chunk.get("source", "unknown"), chunk.get("text", "")[:100])
        else:
            logger.info("FAQRAGTool: retrieved 0 chunks")
        return raw_data

    def _process(self, raw_data: Dict[str, Any], state: GraphState) -> Dict[str, Any]:
        return {
            "message": "",
            "response_type": "RAG_RESPONSE",
            "data": {
                "chunks": raw_data.get("chunks", []),
                "sources": raw_data.get("sources", []),
            },
        }

