from __future__ import annotations

from app.services import DraftService, draft_service
from app.clients import BackendClientError

from .base import BaseTool, ToolResult


class CartTool(BaseTool):
    def __init__(self, client, drafts: DraftService | None = None) -> None:
        super().__init__(client)
        self.drafts = drafts or draft_service

    def get(self, user_id: str | None) -> ToolResult:
        try:
            cart = self.client.cart_get(user_id=user_id)
        except BackendClientError as exc:
            return self.client_error(exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self.unexpected_error(exc)
        if not isinstance(cart, dict) or "itemCount" not in cart:
            return ToolResult(status="validation_error", data=None, summary="invalid cart payload")
        return ToolResult(status="success", data=cart, summary=f"{cart['itemCount']} current cart items")

    def add_draft(self, product_id: str, variant_id: str | None, quantity: int) -> ToolResult:
        draft = self.drafts.create_draft_action(
            "cart.add",
            {"productId": product_id, "variantId": variant_id, "quantity": quantity},
        )
        return ToolResult(status="success", data=draft, summary="cart.add draft")

    def update_quantity_draft(self, product_id: str, quantity: int) -> ToolResult:
        draft = self.drafts.create_draft_action(
            "cart.update_quantity",
            {"productId": product_id, "quantity": quantity},
        )
        return ToolResult(status="success", data=draft, summary="cart.update_quantity draft")

    def remove_item_draft(self, product_id: str) -> ToolResult:
        draft = self.drafts.create_draft_action("cart.remove_item", {"productId": product_id})
        return ToolResult(status="success", data=draft, summary="cart.remove_item draft")
