"""
RAGIngestService — developer-only ingestion utility for FAQ documents.

This is not exposed via API routes. Intended to be used from local scripts/CI.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Dict, List

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)


class RAGIngestService:
    """Developer-side helper to ingest/update FAQ docs in Qdrant."""

    def __init__(self) -> None:
        self._qdrant_url = os.getenv("QDRANT_URL", "")
        self._qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
        self._collection = os.getenv("QDRANT_COLLECTION", "railyatri_faq")
        self._embedding_model_name = os.getenv(
            "RAG_EMBEDDING_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        if not self._qdrant_url:
            raise ValueError("QDRANT_URL is required for ingestion")
        self._client = QdrantClient(
            url=self._qdrant_url,
            api_key=self._qdrant_api_key or None,
            timeout=30,
        )
        self._embedder = TextEmbedding(model_name=self._embedding_model_name)

    def ingest_documents(self, documents: List[Dict[str, str]]) -> int:
        """
        Ingest list of documents where each item has:
          - text (required)
          - source (optional)
          - title (optional)
        """
        if not documents:
            return 0

        texts = [d.get("text", "").strip() for d in documents if d.get("text", "").strip()]
        if not texts:
            return 0

        vectors = list(self._embedder.embed(texts))
        vector_size = len(vectors[0])
        self._ensure_collection(vector_size)

        points: List[PointStruct] = []
        text_idx = 0
        for d in documents:
            text = d.get("text", "").strip()
            if not text:
                continue
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vectors[text_idx],
                    payload={
                        "text": text,
                        "source": d.get("source", "internal_faq"),
                        "title": d.get("title", ""),
                    },
                )
            )
            text_idx += 1

        self._client.upsert(collection_name=self._collection, points=points)
        logger.info("RAGIngestService: upserted %d docs into %s", len(points), self._collection)
        return len(points)

    def _ensure_collection(self, vector_size: int) -> None:
        collections = self._client.get_collections()
        names = {c.name for c in collections.collections}
        if self._collection not in names:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

