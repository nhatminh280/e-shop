from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.knowledge.loader import load_knowledge_documents
from app.schemas.chat import CamelModel
from app.schemas.knowledge import KnowledgeDocument, KnowledgeSourceType


POLICIES_FAQ_COLLECTION = "policies_faq"
PRODUCTS_KNOWLEDGE_COLLECTION = "products_knowledge"


class KnowledgeIngestionRecord(CamelModel):
    id: str
    collection: Literal["policies_faq", "products_knowledge"] = POLICIES_FAQ_COLLECTION
    source_id: str = Field(alias="sourceId")
    source_type: KnowledgeSourceType = Field(alias="sourceType")
    title: str
    locale: str
    chunk_index: int = Field(alias="chunkIndex")
    text: str
    metadata: dict[str, Any]


def build_policy_faq_records(documents: list[KnowledgeDocument]) -> list[KnowledgeIngestionRecord]:
    records: list[KnowledgeIngestionRecord] = []
    for document in documents:
        for chunk_index, section in enumerate(_sections_for(document)):
            records.append(
                KnowledgeIngestionRecord(
                    id=f"{POLICIES_FAQ_COLLECTION}:{document.source_id}:{chunk_index:03d}",
                    collection=POLICIES_FAQ_COLLECTION,
                    sourceId=document.source_id,
                    sourceType=document.source_type,
                    title=document.title,
                    locale=document.locale,
                    chunkIndex=chunk_index,
                    text=section,
                    metadata=_metadata_for(document),
                )
            )
    _ensure_unique_ids(records)
    return records


def load_policy_faq_records() -> list[KnowledgeIngestionRecord]:
    return build_policy_faq_records(load_knowledge_documents())


def build_product_knowledge_records(products: list[dict[str, Any]]) -> list[KnowledgeIngestionRecord]:
    records = [
        KnowledgeIngestionRecord(
            id=f"{PRODUCTS_KNOWLEDGE_COLLECTION}:product-{product['productId']}:000",
            collection=PRODUCTS_KNOWLEDGE_COLLECTION,
            sourceId=f"product-{product['productId']}",
            sourceType="product",
            title=product["name"],
            locale="en-US",
            chunkIndex=0,
            text=_product_knowledge_text(product),
            metadata=_product_metadata(product),
        )
        for product in products
    ]
    _ensure_unique_ids(records)
    return records


def load_all_knowledge_records(products: list[dict[str, Any]]) -> list[KnowledgeIngestionRecord]:
    records = [*load_policy_faq_records(), *build_product_knowledge_records(products)]
    _ensure_unique_ids(records)
    return records


def _metadata_for(document: KnowledgeDocument) -> dict[str, Any]:
    return {
        "sourceId": document.source_id,
        "sourceType": document.source_type,
        "title": document.title,
        "locale": document.locale,
        "heading": document.heading,
        "sourcePath": str(document.source_path),
        "wordCount": document.word_count,
    }


def _product_metadata(product: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceId": f"product-{product['productId']}",
        "sourceType": "product",
        "productId": product["productId"],
        "slug": product["slug"],
        "category": product["category"],
        "gender": product["gender"],
        "tags": product.get("tags", []),
        "colors": product.get("colors", []),
        "sizes": product.get("sizes", []),
    }


def _product_knowledge_text(product: dict[str, Any]) -> str:
    tags = ", ".join(product.get("tags", []))
    colors = ", ".join(product.get("colors", []))
    sizes = ", ".join(product.get("sizes", []))
    return "\n".join(
        [
            f"# {product['name']}",
            "## Product Overview",
            product.get("description", ""),
            f"Category: {product['category']}. Gender: {product['gender']}. Available colors: {colors}. Available sizes: {sizes}.",
            f"Product tags and attributes: {tags}.",
            "## Material And Care",
            _product_material_and_care(product),
            "## Best Use",
            _product_best_use(product),
        ]
    ).strip()


def _product_material_and_care(product: dict[str, Any]) -> str:
    tags = set(product.get("tags", []))
    normalized_tags = {_normalize_tag(tag) for tag in tags}
    category = product.get("category", "")
    if "waterproof" in normalized_tags or "rain" in normalized_tags or "shell" in normalized_tags:
        return (
            f"{product['name']} is positioned as a waterproof shell product. "
            "For care, close zippers before washing, use mild detergent, avoid fabric softener, "
            "and follow the garment care label to preserve the weather-protection finish."
        )
    if "water resistant" in normalized_tags or category == "backpack":
        return (
            f"{product['name']} is built for travel and water-resistant daily use. "
            "Wipe dirt with a damp cloth, air dry fully, and avoid bleach or high heat."
        )
    if "cotton" in tags:
        return (
            f"{product['name']} uses a cotton-focused casual fabric profile. "
            "Wash cold with similar colors and tumble dry low unless the product label says otherwise."
        )
    if "quick dry" in tags:
        return (
            f"{product['name']} is a lightweight quick-dry technical layer. "
            "Wash cold, avoid fabric softener, and hang dry or tumble dry low."
        )
    return (
        f"{product['name']} should be cared for according to the garment label. "
        "Use mild detergent, wash with similar colors, and avoid bleach or unnecessary high heat."
    )


def _product_best_use(product: dict[str, Any]) -> str:
    tags = ", ".join(product.get("tags", []))
    return f"Best use is guided by these catalog tags: {tags}."


def _normalize_tag(tag: str) -> str:
    return tag.lower().replace("-", " ").replace("_", " ").strip()


def _sections_for(document: KnowledgeDocument) -> list[str]:
    lines = document.body.splitlines()
    h1 = lines[0].strip()
    sections: list[list[str]] = []
    intro: list[str] = []
    current: list[str] = []
    for line in lines[1:]:
        if line.startswith("## "):
            if current:
                sections.append(current)
            current = [*intro, line] if intro and not sections else [line]
            intro = []
        elif current:
            current.append(line)
        elif line.strip():
            intro.append(line)
    if current:
        sections.append(current)
    elif intro:
        sections.append(intro)
    return [
        "\n".join([h1, *section]).strip()
        for section in sections
        if "\n".join(section).strip()
    ]


def _ensure_unique_ids(records: list[KnowledgeIngestionRecord]) -> None:
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate knowledge ingestion record id")
