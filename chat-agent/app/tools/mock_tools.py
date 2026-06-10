from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.clients import MockBackendClient
from app.schemas import DraftAction, ProductCard


class MockTools:
    def __init__(self, client: MockBackendClient | None = None) -> None:
        self.client = client or MockBackendClient()

    def catalog_search(self, query: str, filters: dict[str, Any] | None = None) -> list[ProductCard]:
        products = self.client.search_products(query=query, filters=filters)
        return [self._to_product_card(product) for product in products]

    def catalog_filter(self, filters: dict[str, Any]) -> list[ProductCard]:
        return self.catalog_search(query="", filters=filters)

    def catalog_detail(self, product_id_or_slug: str) -> ProductCard | None:
        product = self.client.product_detail(product_id_or_slug)
        return self._to_product_card(product) if product else None

    def recommend_similar(self, product_id_or_slug: str | None = None, query: str = "") -> list[ProductCard]:
        products = self.client.similar_products(product_id_or_slug=product_id_or_slug, query=query)
        return [self._to_product_card(product, reason="similar style") for product in products]

    def cart_get(self, user_id: str | None) -> dict[str, Any]:
        return self.client.cart_summary(user_id=user_id)

    def cart_add_draft(self, product: ProductCard, quantity: int = 1) -> DraftAction:
        return DraftAction(
            draftActionId=f"draft_{uuid4().hex}",
            type="cart.add_draft",
            label=f"Add {product.name} to cart",
            payload={"productId": product.product_id, "quantity": quantity},
            needsConfirmation=True,
        )

    def order_list(self, user_id: str | None) -> list[dict[str, Any]]:
        return self.client.order_list(user_id=user_id)

    def order_lookup(self, order_number: str, user_id: str | None) -> dict[str, Any] | None:
        return self.client.order_lookup(order_number=order_number, user_id=user_id)

    def support_create_draft(self, message: str) -> DraftAction:
        return DraftAction(
            draftActionId=f"draft_{uuid4().hex}",
            type="support.create_draft",
            label="Create support conversation",
            payload={"message": message},
            needsConfirmation=True,
        )

    def knowledge_retrieve(self, query: str) -> list[dict[str, Any]]:
        return self.client.retrieve_knowledge(query=query)

    @staticmethod
    def _to_product_card(product: dict[str, Any], reason: str | None = None) -> ProductCard:
        return ProductCard(
            productId=product["productId"],
            name=product["name"],
            slug=product["slug"],
            category=product["category"],
            gender=product["gender"],
            price=product["price"],
            currency=product.get("currency", "VND"),
            imageUrl=product.get("imageUrl"),
            colors=product.get("colors", []),
            sizes=product.get("sizes", []),
            inStock=product.get("stock", 0) > 0,
            stock=product.get("stock", 0),
            reason=reason,
        )
