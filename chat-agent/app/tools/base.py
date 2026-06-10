from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.clients import BackendClient, BackendClientError
from app.schemas import ProductCard, ToolStatus


ToolResultStatus = Literal["success", "empty_result", "timeout", "unauthorized", "backend_error", "validation_error"]


@dataclass
class ToolResult:
    status: ToolStatus
    data: Any = None
    summary: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "success"


class BaseTool:
    def __init__(self, client: BackendClient) -> None:
        self.client = client

    @staticmethod
    def client_error(exc: BackendClientError) -> ToolResult:
        status = exc.status if exc.status in {"timeout", "unauthorized", "backend_error", "validation_error"} else "backend_error"
        return ToolResult(status=status, data=None, summary="backend client error", error=str(exc))

    @staticmethod
    def unexpected_error(exc: Exception) -> ToolResult:
        return ToolResult(status="backend_error", data=None, summary="tool failed", error=exc.__class__.__name__)


def to_product_card(
    product: dict[str, Any],
    reason: str | None = None,
    recommendation_rank: int | None = None,
    recommendation_score: float | None = None,
    recommendation_reason: str | None = None,
) -> ProductCard:
    product_id = product.get("productId") or product.get("id")
    if not product_id:
        raise ValueError("catalog product missing productId")
    stock = int(product.get("stock", 0) or 0)
    in_stock = bool(product["inStock"]) if "inStock" in product else stock > 0
    return ProductCard(
        productId=product_id,
        name=product["name"],
        slug=product["slug"],
        category=product["category"],
        gender=product.get("gender", "unisex"),
        price=int(product["price"]),
        currency=product.get("currency", "VND"),
        imageUrl=product.get("imageUrl"),
        colors=list(product.get("colors") or []),
        sizes=list(product.get("sizes") or []),
        inStock=in_stock,
        stock=stock,
        reason=reason,
        recommendationRank=recommendation_rank,
        recommendationScore=recommendation_score,
        recommendationReason=recommendation_reason,
    )


def validate_product_payload(product: dict[str, Any]) -> bool:
    if not all(key in product for key in ("name", "slug", "category", "price")):
        return False
    if not product.get("productId") and not product.get("id"):
        return False
    try:
        int(product["price"])
        int(product.get("stock", 0) or 0)
    except (TypeError, ValueError):
        return False
    return isinstance(product.get("colors", []), list) and isinstance(product.get("sizes", []), list)
