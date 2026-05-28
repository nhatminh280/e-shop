from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Any

from .base_client import BackendClient


class MockBackendClient(BackendClient):
    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or Path(__file__).resolve().parents[1] / "data" / "mock_catalog.json"

    @cached_property
    def data(self) -> dict[str, Any]:
        with self.data_path.open(encoding="utf-8") as file:
            return json.load(file)

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
                and (product["category"] == anchor["category"] or set(product["tags"]) & set(anchor["tags"]))
            ]
            if products:
                return products[:limit]
            return [product for product in self.data["products"] if product["productId"] != anchor["productId"]][:limit]
        return self.catalog_search(query="", limit=limit)

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
        query_tokens = set(query.lower().split())
        scored: list[tuple[int, dict[str, Any]]] = []
        for doc in self.data["knowledge"]:
            text = f"{doc['title']} {doc['body']}".lower()
            score = sum(1 for token in query_tokens if token in text)
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[:limit]]

    def support_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"conversationId": "mock-support-conversation", "status": "created", **payload}

    def confirm_draft_action(self, draft_action_id: str) -> dict[str, Any]:
        return {"draftActionId": draft_action_id, "status": "completed"}

    def cancel_draft_action(self, draft_action_id: str) -> dict[str, Any]:
        return {"draftActionId": draft_action_id, "status": "cancelled"}
