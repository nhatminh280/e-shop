from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    slug: str
    category: str
    gender: str
    colors: tuple[str, ...]
    sizes: tuple[str, ...]
    price: Decimal
    stock: int


PRODUCTS: tuple[Product, ...] = (
    Product(
        id="p001",
        name="Patagonia Cap Cool Daily Shirt",
        slug="patagonia-cap-cool-daily-shirt",
        category="shirt",
        gender="unisex",
        colors=("black", "blue", "white"),
        sizes=("S", "M", "L", "XL"),
        price=Decimal("890000"),
        stock=18,
    ),
    Product(
        id="p002",
        name="Patagonia Baggies Shorts",
        slug="patagonia-baggies-shorts",
        category="shorts",
        gender="men",
        colors=("green", "navy", "black"),
        sizes=("S", "M", "L"),
        price=Decimal("1250000"),
        stock=7,
    ),
    Product(
        id="p003",
        name="Patagonia Torrentshell 3L Jacket",
        slug="patagonia-torrentshell-3l-jacket",
        category="jacket",
        gender="women",
        colors=("red", "black"),
        sizes=("M", "L"),
        price=Decimal("3890000"),
        stock=3,
    ),
)


def search_products(query: str, size: str | None = None, color: str | None = None) -> list[dict]:
    normalized_query = query.lower().strip()
    normalized_size = size.upper().strip() if size else None
    normalized_color = color.lower().strip() if color else None

    matches: list[Product] = []
    for product in PRODUCTS:
        searchable = " ".join(
            [product.name, product.slug, product.category, product.gender, *product.colors, *product.sizes]
        ).lower()
        if normalized_query and normalized_query not in searchable:
            continue
        if normalized_size and normalized_size not in product.sizes:
            continue
        if normalized_color and normalized_color not in product.colors:
            continue
        matches.append(product)

    return [
        {
            "id": product.id,
            "name": product.name,
            "slug": product.slug,
            "category": product.category,
            "colors": list(product.colors),
            "sizes": list(product.sizes),
            "price": int(product.price),
            "stock": product.stock,
        }
        for product in matches[:3]
    ]


def lookup_order(order_code: str) -> dict | None:
    demo_orders = {
        "ES123": {
            "orderCode": "ES123",
            "status": "SHIPPED",
            "paymentStatus": "PAID",
            "eta": "2026-05-03",
        },
        "ES456": {
            "orderCode": "ES456",
            "status": "PROCESSING",
            "paymentStatus": "PENDING",
            "eta": "2026-05-05",
        },
    }
    return demo_orders.get(order_code.upper().strip())
