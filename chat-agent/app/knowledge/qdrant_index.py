from __future__ import annotations

import logging
import os
import re
from typing import Any

from app.knowledge.embedder import embed_text


logger = logging.getLogger(__name__)


COLLECTION_NAME_DEFAULT = os.getenv("KNOWLEDGE_QDRANT_COLLECTION", "knowledge_documents_v1")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class QdrantKnowledgeIndex:
    def __init__(
        self,
        *,
        client: Any | None = None,
        collection_name: str = COLLECTION_NAME_DEFAULT,
    ) -> None:
        self.collection_name = collection_name
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(
                host=os.getenv("QDRANT_HOST", "localhost"),
                port=int(os.getenv("QDRANT_PORT", "6333")),
                api_key=os.getenv("QDRANT_API_KEY") or None,
                timeout=float(os.getenv("QDRANT_TIMEOUT_SECONDS", "5")),
            )
        return self._client

    def retrieve(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        vector = embed_text(query)
        try:
            hits = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit,
                with_payload=True,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("qdrant_search_failed", extra={"error": str(exc)})
            return []
        query_tokens = {token for token in _TOKEN_RE.findall(query.lower())}
        results: list[dict[str, Any]] = []
        for hit in hits:
            payload = getattr(hit, "payload", {}) or {}
            body_text = str(payload.get("body", "")).lower()
            matched_tokens = sorted(token for token in query_tokens if token in body_text)
            results.append(
                {
                    "sourceId": payload.get("sourceId", "unknown"),
                    "sourceType": payload.get("sourceType", "unknown"),
                    "title": payload.get("title", ""),
                    "locale": payload.get("locale", "en-US"),
                    "body": payload.get("body", ""),
                    "score": round(float(getattr(hit, "score", 0.0)), 4),
                    "scoreType": "vector",
                    "matchedTokenCount": len(matched_tokens),
                    "matchedTokens": matched_tokens,
                }
            )
        return results
