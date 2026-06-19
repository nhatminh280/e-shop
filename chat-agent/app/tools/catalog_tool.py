from __future__ import annotations

from typing import Any

from app.clients import BackendClientError

from .base import BaseTool, ToolResult, to_product_card, validate_product_payload


class CatalogTool(BaseTool):
    MAX_DETAIL_ENRICHMENT = 4

    def search(self, query: str, filters: dict[str, Any] | None = None) -> ToolResult:
        try:
            products = self.client.catalog_search(query=query, filters=filters or {})
            products = self._enrich_search_results(products)
            return self._cards_result(products)
        except BackendClientError as exc:
            return self.client_error(exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self.unexpected_error(exc)

    def filter(
        self,
        category: str | None = None,
        color: str | None = None,
        size: str | None = None,
        gender: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        in_stock: bool | None = None,
    ) -> ToolResult:
        filters = {
            key: value
            for key, value in {
                "category": category,
                "color": color,
                "size": size,
                "gender": gender,
                "price_min": price_min,
                "price_max": price_max,
                "in_stock": in_stock,
            }.items()
            if value is not None
        }
        try:
            products = self.client.catalog_filter(filters=filters)
            return self._cards_result(products)
        except BackendClientError as exc:
            return self.client_error(exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self.unexpected_error(exc)

    def detail(self, slug: str) -> ToolResult:
        try:
            product = self.client.catalog_detail(slug=slug)
            if not product:
                return ToolResult(status="empty_result", data=None, summary="product not found")
            if not validate_product_payload(product):
                return ToolResult(status="validation_error", data=None, summary="invalid catalog payload")
            return ToolResult(status="success", data=to_product_card(product), summary="product detail")
        except BackendClientError as exc:
            return self.client_error(exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self.unexpected_error(exc)

    def _enrich_search_results(self, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for index, product in enumerate(products):
            if index >= self.MAX_DETAIL_ENRICHMENT:
                enriched.append(product)
                continue
            slug = product.get("slug")
            if not slug or not validate_product_payload(product):
                enriched.append(product)
                continue
            try:
                detail = self.client.catalog_detail(slug=slug)
            except BackendClientError:
                detail = None
            if isinstance(detail, dict):
                enriched.append({**product, **detail})
            else:
                enriched.append(product)
        return enriched

    @staticmethod
    def _cards_result(products: list[dict[str, Any]]) -> ToolResult:
        if not products:
            return ToolResult(status="empty_result", data=[], summary="0 product cards")
        if any(not validate_product_payload(product) for product in products):
            return ToolResult(status="validation_error", data=[], summary="invalid catalog payload")
        try:
            cards = [to_product_card(product) for product in products]
        except (TypeError, ValueError, KeyError) as exc:
            return ToolResult(status="validation_error", data=[], summary="invalid catalog payload", error=str(exc))
        return ToolResult(status="success", data=cards, summary=f"{len(cards)} product cards")
