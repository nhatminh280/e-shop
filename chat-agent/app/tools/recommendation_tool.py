from __future__ import annotations

from app.clients import BackendClientError

from .base import BaseTool, ToolResult, to_product_card, validate_product_payload


class RecommendationTool(BaseTool):
    def similar(
        self,
        product_id: str | None = None,
        variant_id: str | None = None,
        recent_product_ids: list[str] | None = None,
    ) -> ToolResult:
        try:
            products = self.client.recommend_similar(
                product_id=product_id,
                variant_id=variant_id,
                recent_product_ids=recent_product_ids or [],
            )
        except BackendClientError as exc:
            return self.client_error(exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self.unexpected_error(exc)
        if not products:
            return ToolResult(status="empty_result", data=[], summary="0 recommendations")
        if any(not validate_product_payload(product) for product in products):
            return ToolResult(status="validation_error", data=[], summary="invalid recommendation payload")
        try:
            cards = [to_product_card(product, reason="similar style") for product in products]
        except (TypeError, ValueError, KeyError) as exc:
            return ToolResult(status="validation_error", data=[], summary="invalid recommendation payload", error=str(exc))
        return ToolResult(status="success", data=cards, summary=f"{len(cards)} recommendations")
