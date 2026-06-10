from __future__ import annotations

from app.clients import MockBackendClient
from app.knowledge.ingestion import KnowledgeIngestionRecord, load_all_knowledge_records
from app.knowledge.vector_index import LocalHybridKnowledgeIndex


def test_hybrid_index_retrieves_product_knowledge_with_source_metadata() -> None:
    index = LocalHybridKnowledgeIndex.from_records(load_all_knowledge_records(MockBackendClient().data["products"]))

    results = index.retrieve("is the torrentshell jacket waterproof and how do i care for it", limit=2)

    assert results[0]["sourceId"] == "product-p003"
    assert results[0]["sourceType"] == "product"
    assert results[0]["scoreType"] == "hybrid"
    assert results[0]["score"] >= 0.7
    assert "waterproof" in results[0]["matchedTokens"]
    assert "Patagonia Torrentshell 3L Jacket" in results[0]["body"]


def test_hybrid_index_preserves_policy_retrieval() -> None:
    index = LocalHybridKnowledgeIndex.from_records(load_all_knowledge_records(MockBackendClient().data["products"]))

    results = index.retrieve("shipping fees standard domestic", limit=1)

    assert results[0]["sourceId"] == "shipping"
    assert results[0]["sourceType"] == "shipping"
    assert results[0]["scoreType"] == "hybrid"


def test_hybrid_index_prefers_earlier_chunks_when_scores_tie() -> None:
    records = [
        KnowledgeIngestionRecord(
            id="policies_faq:shipping:001",
            collection="policies_faq",
            sourceId="shipping",
            sourceType="shipping",
            title="Shipping Policy",
            locale="en-US",
            chunkIndex=1,
            text="# Shipping Policy\n## Later\nshipping policy",
            metadata={"sourceId": "shipping", "sourceType": "shipping", "title": "Shipping Policy"},
        ),
        KnowledgeIngestionRecord(
            id="policies_faq:shipping:000",
            collection="policies_faq",
            sourceId="shipping",
            sourceType="shipping",
            title="Shipping Policy",
            locale="en-US",
            chunkIndex=0,
            text="# Shipping Policy\n## First\nshipping policy",
            metadata={"sourceId": "shipping", "sourceType": "shipping", "title": "Shipping Policy"},
        ),
    ]

    results = LocalHybridKnowledgeIndex.from_records(records).retrieve("shipping policy", limit=1)

    assert "## First" in results[0]["body"]
