from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest


def test_embedder_returns_384_dim_normalized_vector() -> None:
    from app.knowledge import embedder

    vector = embedder.embed_text("how do I return an item?")

    assert isinstance(vector, list)
    assert len(vector) == 384
    norm = sum(v * v for v in vector) ** 0.5
    assert abs(norm - 1.0) < 1e-3


def test_qdrant_knowledge_index_returns_normalized_documents() -> None:
    from app.knowledge.qdrant_index import QdrantKnowledgeIndex

    fake_hit = MagicMock()
    fake_hit.score = 0.82
    fake_hit.payload = {
        "sourceId": "shipping",
        "sourceType": "shipping",
        "title": "Shipping Policy",
        "locale": "en-US",
        "body": "Standard delivery within Vietnam takes 3 to 5 business days.",
        "chunkIndex": 2,
    }
    fake_client = MagicMock()
    fake_client.search.return_value = [fake_hit]

    index = QdrantKnowledgeIndex(client=fake_client, collection_name="knowledge_documents_v1")
    results = index.retrieve("when will my order arrive?", limit=3)

    assert results
    first = results[0]
    assert first["sourceId"] == "shipping"
    assert first["scoreType"] == "vector"
    assert first["score"] == 0.82
    assert "matchedTokenCount" in first
    fake_client.search.assert_called_once()
    _, kwargs = fake_client.search.call_args
    assert kwargs["collection_name"] == "knowledge_documents_v1"
    assert kwargs["limit"] == 3


def _qdrant_available() -> bool:
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            timeout=2.0,
        )
        client.get_collections()
        return True
    except Exception:
        return False


def _knowledge_collection_populated() -> bool:
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            timeout=2.0,
        )
        info = client.get_collection("knowledge_documents_v1")
        return getattr(info, "points_count", 0) > 0
    except Exception:
        return False


@pytest.mark.skipif(not _qdrant_available(), reason="qdrant not reachable on localhost:6333")
@pytest.mark.skipif(
    not _knowledge_collection_populated(),
    reason="knowledge_documents_v1 collection not populated; run `python -m app.knowledge.ingest_to_qdrant`",
)
def test_qdrant_knowledge_retrieve_end_to_end_after_ingestion() -> None:
    from app.knowledge.qdrant_index import QdrantKnowledgeIndex

    index = QdrantKnowledgeIndex()
    results = index.retrieve("how do I return an item?", limit=3)

    assert results, "expected at least one result"
    source_ids = {r["sourceId"] for r in results}
    assert "return-refund" in source_ids
    assert results[0]["score"] > 0.4
