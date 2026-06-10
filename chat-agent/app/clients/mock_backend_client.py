from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Any

from app.knowledge import LocalHybridKnowledgeIndex, load_all_knowledge_records

from .base_client import BackendClient


class MockBackendClient(BackendClient):
    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or Path(__file__).resolve().parents[1] / "data" / "mock_catalog.json"

    @cached_property
    def data(self) -> dict[str, Any]:
        with self.data_path.open(encoding="utf-8") as file:
            return json.load(file)

    @cached_property
    def knowledge_documents(self) -> list[dict[str, Any]]:
        return [
            {
                "sourceId": record.source_id,
                "sourceType": record.source_type,
                "title": record.title,
                "locale": record.locale,
                "body": record.text,
                "score": 0.0,
                "scoreType": "hybrid",
                "matchedTokenCount": 0,
                "matchedTokens": [],
            }
            for record in self.knowledge_index.records
        ]

    @cached_property
    def knowledge_index(self) -> LocalHybridKnowledgeIndex:
        return LocalHybridKnowledgeIndex.from_records(load_all_knowledge_records(self.data["products"]))

    def catalog_search(self, query: str, filters: dict[str, Any] | None = None, limit: int = 4) -> list[dict[str, Any]]:
        filters = filters or {}
        query_tokens = [token for token in query.lower().split() if token]
        matches: list[dict[str, Any]] = []

        for product in self.data["products"]:
            searchable = " ".join(
                [
                    product["name"],
                    product["slug"],
                    product["category"],
                    product["gender"],
                    product.get("description", ""),
                    " ".join(product.get("tags", [])),
                    " ".join(product.get("colors", [])),
                    " ".join(product.get("sizes", [])),
                ]
            ).lower()
            if query_tokens and not all(token in searchable for token in query_tokens):
                continue
            if filters.get("category") and filters["category"] != product["category"]:
                continue
            if filters.get("color") and filters["color"] not in product.get("colors", []):
                continue
            if filters.get("size") and filters["size"] not in product.get("sizes", []):
                continue
            if filters.get("gender") and filters["gender"] not in (product["gender"], "unisex"):
                continue
            if filters.get("in_stock") and product.get("stock", 0) <= 0:
                continue
            if filters.get("price_min") is not None and product["price"] < filters["price_min"]:
                continue
            if filters.get("price_max") is not None and product["price"] > filters["price_max"]:
                continue
            matches.append(product)

        return matches[:limit]

    def catalog_filter(self, filters: dict[str, Any], limit: int = 4) -> list[dict[str, Any]]:
        return self.catalog_search(query="", filters=filters, limit=limit)

    def catalog_detail(self, slug: str) -> dict[str, Any] | None:
        needle = slug.strip().lower()
        return next(
            (
                product
                for product in self.data["products"]
                if product["productId"].lower() == needle or product["slug"].lower() == needle
            ),
            None,
        )

    def recommend_similar(
        self,
        product_id: str | None = None,
        variant_id: str | None = None,
        recent_product_ids: list[str] | None = None,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        anchor_id = product_id or (recent_product_ids or [None])[0]
        anchor = self.catalog_detail(anchor_id) if anchor_id else None
        if anchor:
            products = [
                product
                for product in self.data["products"]
                if product["productId"] != anchor["productId"]
                and (product["category"] == anchor["category"] or set(_product_tags(product)) & set(_product_tags(anchor)))
            ]
            if products:
                return products[:limit]
            return [product for product in self.data["products"] if product["productId"] != anchor["productId"]][:limit]
        return self.catalog_search(query="", limit=limit)

    def recommend_personalized(
        self,
        user_id: str | None = None,
        recent_product_ids: list[str] | None = None,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        recent_products = [
            product
            for product_id in recent_product_ids or []
            if (product := self.catalog_detail(product_id))
        ]
        recent_categories = {product["category"] for product in recent_products}
        recent_tags = set().union(*(set(_product_tags(product)) for product in recent_products)) if recent_products else set()

        scored: list[tuple[float, dict[str, Any]]] = []
        for product in self.data["products"]:
            if product["productId"] in set(recent_product_ids or []):
                continue
            score = 0.35 + min(product.get("stock", 0), 20) / 100
            reasons: list[str] = []
            if product["category"] in recent_categories:
                score += 0.35
                reasons.append("same category as recently viewed")
            if set(_product_tags(product)) & recent_tags:
                score += 0.25
                reasons.append("matches recent browsing tags")
            if not reasons:
                reasons.append("popular in-stock product")
            scored.append((round(min(score, 0.99), 4), {**product, "recommendationReason": "; ".join(reasons)}))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {**product, "recommendationRank": index + 1, "recommendationScore": score}
            for index, (score, product) in enumerate(scored[:limit])
        ]

    def cart_get(self, user_id: str | None) -> dict[str, Any]:
        return {"userId": user_id, "items": [], "itemCount": 0}

    def order_list(self, user_id: str | None) -> list[dict[str, Any]]:
        return self.data["orders"] if user_id else []

    def order_lookup(self, order_id: str, user_id: str | None) -> dict[str, Any] | None:
        if not user_id:
            return None
        normalized = order_id.strip().upper()
        return next((order for order in self.data["orders"] if order["orderNumber"] == normalized), None)

    def latest_purchased_item(self, product_id: str | None, user_id: str | None) -> dict[str, Any] | None:
        if not user_id:
            return None
        return self.data["products"][0] if product_id is None else self.catalog_detail(product_id)

    def knowledge_retrieve(self, query: str, limit: int = 2) -> list[dict[str, Any]]:
        return self.knowledge_index.retrieve(query, limit=limit)

    def support_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"conversationId": "mock-support-conversation", "status": "created", **payload}

    def confirm_draft_action(self, draft_action_id: str) -> dict[str, Any]:
        return {"draftActionId": draft_action_id, "status": "completed"}

    def cancel_draft_action(self, draft_action_id: str) -> dict[str, Any]:
        return {"draftActionId": draft_action_id, "status": "cancelled"}


def _product_tags(product: dict[str, Any]) -> list[str]:
    return list(product.get("tags") or [])
