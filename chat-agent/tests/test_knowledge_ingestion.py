from __future__ import annotations

from pathlib import Path

import pytest

from app.clients import MockBackendClient
from app.knowledge.ingestion import (
    build_policy_faq_records,
    build_product_knowledge_records,
    load_all_knowledge_records,
    load_policy_faq_records,
)
from app.knowledge.loader import load_knowledge_documents
from app.schemas import KnowledgeDocument


def test_empty_policy_faq_documents_create_no_records() -> None:
    assert build_policy_faq_records([]) == []


def test_load_policy_faq_records_covers_all_seed_sources() -> None:
    records = load_policy_faq_records()
    source_ids = {record.source_id for record in records}

    assert source_ids == {
        "faq-account",
        "faq-order",
        "faq-product",
        "payment",
        "return-refund",
        "shipping",
        "size-guide",
    }
    assert {record.collection for record in records} == {"policies_faq"}


def test_policy_faq_records_preserve_metadata_and_context() -> None:
    records = load_policy_faq_records()
    shipping = next(record for record in records if record.source_id == "shipping")

    assert shipping.metadata["sourceId"] == "shipping"
    assert shipping.metadata["sourceType"] == "shipping"
    assert shipping.metadata["title"] == shipping.title
    assert shipping.metadata["sourcePath"].endswith("shipping.md")
    assert "# Shipping Policy" in shipping.text
    assert "## " in shipping.text


def test_policy_faq_record_ids_are_deterministic() -> None:
    first = [record.id for record in load_policy_faq_records()]
    second = [record.id for record in load_policy_faq_records()]

    assert first == second
    assert all(record_id.startswith("policies_faq:") for record_id in first)


def test_policy_faq_documents_are_split_into_section_chunks() -> None:
    records = load_policy_faq_records()
    shipping_records = [record for record in records if record.source_id == "shipping"]

    assert len(shipping_records) > 1
    assert [record.chunk_index for record in shipping_records] == list(range(len(shipping_records)))
    assert all(record.id.endswith(f":{index:03d}") for index, record in enumerate(shipping_records))
    assert all(record.text.startswith("# Shipping Policy\n") for record in shipping_records)
    assert all("## " in record.text for record in shipping_records)


def test_policy_faq_records_preserve_intro_before_first_section() -> None:
    document = KnowledgeDocument(
        sourceId="shipping",
        sourceType="shipping",
        title="Shipping Policy",
        locale="en-US",
        heading="Shipping Policy",
        body="# Shipping Policy\nIntro paragraph mentions remote area surcharges.\n\n## Delivery\nStandard delivery details.",
        sourcePath=Path("shipping.md"),
        wordCount=10,
    )

    records = build_policy_faq_records([document])

    assert "Intro paragraph mentions remote area surcharges." in records[0].text
    assert "## Delivery" in records[0].text


def test_policy_faq_builder_rejects_duplicate_record_ids() -> None:
    document = load_knowledge_documents()[0]

    with pytest.raises(ValueError, match="duplicate knowledge ingestion record id"):
        build_policy_faq_records([document, document])


def test_product_knowledge_records_are_built_from_catalog_products() -> None:
    records = build_product_knowledge_records(MockBackendClient().data["products"])
    first = records[0]

    assert len(records) == 8
    assert {record.collection for record in records} == {"products_knowledge"}
    assert first.source_id == "product-p001"
    assert first.source_type == "product"
    assert first.metadata["productId"] == "p001"
    assert first.metadata["slug"] == "patagonia-cap-cool-daily-shirt"
    assert "Patagonia Cap Cool Daily Shirt" in first.text
    assert "quick dry" in first.text
    assert "care" in first.text.lower()


def test_product_knowledge_care_detects_hyphenated_water_resistant_tag() -> None:
    [record] = build_product_knowledge_records(
        [
            {
                "productId": "p900",
                "name": "Trail Windbreaker",
                "slug": "trail-windbreaker",
                "category": "jacket",
                "gender": "unisex",
                "tags": ["water-resistant", "travel"],
                "colors": ["navy"],
                "sizes": ["M"],
                "description": "Light jacket for changing weather.",
            }
        ]
    )

    assert "water-resistant daily use" in record.text


def test_load_all_knowledge_records_combines_policy_and_product_collections() -> None:
    records = load_all_knowledge_records(MockBackendClient().data["products"])

    assert {"policies_faq", "products_knowledge"} <= {record.collection for record in records}
    assert "product-p003" in {record.source_id for record in records}
