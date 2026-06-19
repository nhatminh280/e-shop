from __future__ import annotations

from typing import Any

from app.clients import MockBackendClient, SpringBackendClient, create_backend_client
from app.evaluation.backend_smoke import run_backend_smoke


def test_create_backend_client_uses_mock_backend_env_alias(monkeypatch) -> None:
    monkeypatch.delenv("USE_MOCK_BACKEND", raising=False)
    monkeypatch.setenv("MOCK_BACKEND", "false")

    assert isinstance(create_backend_client(), SpringBackendClient)


def test_create_backend_client_keeps_legacy_use_mock_backend_env(monkeypatch) -> None:
    monkeypatch.delenv("MOCK_BACKEND", raising=False)
    monkeypatch.setenv("USE_MOCK_BACKEND", "true")

    assert isinstance(create_backend_client(), MockBackendClient)


class SmokeClient:
    def catalog_search(self, query: str, filters: dict[str, Any] | None = None, limit: int = 4) -> list[dict[str, Any]]:
        return [
            {
                "productId": "p001",
                "variantId": "v001",
                "name": "Smoke Jacket",
                "slug": "smoke-jacket",
                "category": "jackets",
                "price": 100,
                "imageUrl": None,
                "colors": [],
                "sizes": [],
                "stock": 0,
                "inStock": True,
            }
        ]

    def catalog_detail(self, slug: str) -> dict[str, Any] | None:
        return {
            "productId": "p001",
            "variantId": "v001",
            "name": "Smoke Jacket",
            "slug": slug,
            "category": "jackets",
            "price": 100,
            "imageUrl": "https://cdn.example.com/smoke.jpg",
            "colors": ["Black"],
            "sizes": ["M"],
            "stock": 8,
            "inStock": True,
        }

    def recommend_similar(
        self,
        product_id: str | None = None,
        variant_id: str | None = None,
        recent_product_ids: list[str] | None = None,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        return []


def test_backend_smoke_reports_catalog_detail_and_recommendation_fallback() -> None:
    result = run_backend_smoke(client=SmokeClient(), query="jacket", limit=1)

    assert result["catalogSearch"]["ok"] is True
    assert result["catalogSearch"]["count"] == 1
    assert result["catalogDetail"]["ok"] is True
    assert result["catalogDetail"]["hasImage"] is True
    assert result["recommendSimilar"]["ok"] is True
    assert result["recommendSimilar"]["count"] == 0
