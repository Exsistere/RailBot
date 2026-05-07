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
        logger.info("FAQRAGTool: retrieving answer for query=%r", query[:80])
        return self._rag_service.answer(query)

    def _process(self, raw_data: Dict[str, Any], state: GraphState) -> Dict[str, Any]:
        return {
            "message": raw_data.get("message", ""),
            "response_type": "RAG_RESPONSE",
            "data": raw_data.get("data", {"sources": []}),
        }

