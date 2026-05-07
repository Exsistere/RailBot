"""
RAGService — retrieval-only internal FAQ assistant.

This service ONLY retrieves chunks from Qdrant. Response generation belongs to
the Responder node so intent + retrieved context are handled centrally.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)


class RAGService:
    """Retrieval-only service for FAQ_RAG intent."""

    def __init__(self) -> None:
        self._qdrant_url = os.getenv("QDRANT_URL", "")
        self._qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
        self._collection = os.getenv("QDRANT_COLLECTION", "railyatri_faq")
        self._top_k = int(os.getenv("QDRANT_TOP_K", "5"))

        self._embedding_model_name = os.getenv(
            "RAG_EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        self._qdrant_client = None
        self._embedder = None
        try:
            from qdrant_client import QdrantClient
            from fastembed import TextEmbedding

            if self._qdrant_url:
                self._qdrant_client = QdrantClient(
                    url=self._qdrant_url,
                    api_key=self._qdrant_api_key or None,
                    timeout=15,
                )
            self._embedder = TextEmbedding(model_name=self._embedding_model_name)
        except Exception as exc:
            logger.warning("RAGService: retrieval stack unavailable: %s", exc)
            self._qdrant_client = None
            self._embedder = None

    def retrieve(self, query: str) -> Dict[str, object]:
        """Retrieve top-k chunks and sources for the query."""
        query = (query or "").strip()
        if not query:
            return {"chunks": [], "sources": []}

        chunks = self._retrieve_chunks(query)
        return {
            "chunks": chunks,
            "sources": [c.get("source", "internal_faq") for c in chunks],
        }

    def _retrieve_chunks(self, query: str) -> List[Dict[str, str]]:
        """
        Retrieve top-k chunks from Qdrant.
        Uses qdrant text query API (if available) with graceful fallback.
        """
        if self._qdrant_client is None or self._embedder is None:
            return []

        try:
            vector = list(self._embedder.embed([query]))[0]
            results = self._qdrant_client.query_points(
                collection_name=self._collection,
                query=vector,
                limit=self._top_k,
            )
            points = getattr(results, "points", []) or []
            chunks: List[Dict[str, str]] = []
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

