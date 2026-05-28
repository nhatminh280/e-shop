from __future__ import annotations

from app.clients import BackendClientError

from .base import BaseTool, ToolResult


class OrderTool(BaseTool):
    def list(self, user_id: str | None) -> ToolResult:
        if not user_id:
            return ToolResult(status="unauthorized", data=[], summary="auth required")
        try:
            orders = self.client.order_list(user_id=user_id)
        except BackendClientError as exc:
            return self.client_error(exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self.unexpected_error(exc)
        if not orders:
            return ToolResult(status="empty_result", data=[], summary="0 orders")
        if any("status" not in order or not (order.get("orderNumber") or order.get("orderId")) for order in orders):
            return ToolResult(status="validation_error", data=[], summary="invalid order payload")
        return ToolResult(status="success", data=orders, summary=f"{len(orders)} orders")

    def lookup(self, order_id: str, user_id: str | None) -> ToolResult:
        if not user_id:
            return ToolResult(status="unauthorized", data=None, summary="auth required")
        try:
            order = self.client.order_lookup(order_id=order_id, user_id=user_id)
        except BackendClientError as exc:
            return self.client_error(exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self.unexpected_error(exc)
        if not order:
            return ToolResult(status="empty_result", data=None, summary="order not found")
        if "status" not in order or not (order.get("orderNumber") or order.get("orderId")):
            return ToolResult(status="validation_error", data=None, summary="invalid order payload")
        return ToolResult(status="success", data=order, summary="order found")

    def latest_purchased_item(self, product_id: str | None, user_id: str | None) -> ToolResult:
        if not user_id:
            return ToolResult(status="unauthorized", data=None, summary="auth required")
        try:
            item = self.client.latest_purchased_item(product_id=product_id, user_id=user_id)
        except BackendClientError as exc:
            return self.client_error(exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self.unexpected_error(exc)
        if not item:
            return ToolResult(status="empty_result", data=None, summary="latest purchased item not found")
        return ToolResult(status="success", data=item, summary="latest purchased item")
