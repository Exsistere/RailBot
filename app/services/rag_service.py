"""
RAGService — retrieval-only internal FAQ assistant.

This service does retrieval from internal Qdrant and uses LLM to generate a
grounded response. No ingestion/upload endpoints are exposed here.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from app.services.llm import client as llm_client

logger = logging.getLogger(__name__)


class RAGService:
    """Retrieval + grounded generation for FAQ_RAG intent."""

    def __init__(self) -> None:
        self._qdrant_url = os.getenv("QDRANT_URL", "")
        self._qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
        self._collection = os.getenv("QDRANT_COLLECTION", "railyatri_faq")
        self._top_k = int(os.getenv("QDRANT_TOP_K", "5"))

        self._qdrant_client = None
        try:
            from qdrant_client import QdrantClient

            if self._qdrant_url:
                self._qdrant_client = QdrantClient(
                    url=self._qdrant_url,
                    api_key=self._qdrant_api_key or None,
                    timeout=15,
                )
        except Exception as exc:
            logger.warning("RAGService: qdrant unavailable: %s", exc)
            self._qdrant_client = None

    def answer(self, query: str) -> Dict[str, Any]:
        """
        RAG flow:
          query -> embed -> qdrant retrieve -> grounded answer.
        """
        query = (query or "").strip()
        if not query:
            return {
                "message": "Please ask a railway FAQ question.",
                "response_type": "RAG_RESPONSE",
                "data": {"sources": []},
            }

        chunks = self._retrieve_chunks(query)
        if not chunks:
            return {
                "message": "I don't have that knowledge in my internal FAQ index yet.",
                "response_type": "RAG_RESPONSE",
                "data": {"sources": []},
            }

        context = "\n\n".join([c.get("text", "") for c in chunks if c.get("text")])
        prompt = (
            "Answer the user's railway FAQ using ONLY the retrieved context.\n"
            "If context does not contain the answer, reply: "
            "'I don't have that knowledge in my internal FAQ index yet.'\n\n"
            f"User query: {query}\n\nRetrieved context:\n{context}"
        )
        try:
            answer = llm_client.generate_text(prompt=prompt, system_prompt="Grounded FAQ assistant")
            answer = answer.strip() if answer else ""
        except Exception as exc:
            logger.error("RAGService: LLM failure: %s", exc)
            answer = ""

        if not answer:
            answer = "I don't have that knowledge in my internal FAQ index yet."

        return {
            "message": answer,
            "response_type": "RAG_RESPONSE",
            "data": {
                "sources": [c.get("source", "internal_faq") for c in chunks],
            },
        }

    def _retrieve_chunks(self, query: str) -> List[Dict[str, Any]]:
        """
        Retrieve top-k chunks from Qdrant.
        Uses qdrant text query API (if available) with graceful fallback.
        """
        if self._qdrant_client is None:
            return []

        try:
            # Prefer query_points text search API (works with collections configured for text/query).
            results = self._qdrant_client.query_points(
                collection_name=self._collection,
                query=query,
                limit=self._top_k,
            )
            points = getattr(results, "points", []) or []
            chunks: List[Dict[str, Any]] = []
            for p in points:
                payload = getattr(p, "payload", {}) or {}
                chunks.append(
                    {
                        "text": payload.get("text") or payload.get("content") or "",
                        "source": payload.get("source") or payload.get("title") or "internal_faq",
                    }
                )
            return [c for c in chunks if c.get("text")]
        except Exception as exc:
            logger.error("RAGService: Qdrant retrieval failure: %s", exc)
            return []

