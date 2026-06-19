from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.clients.base_client import BackendClientError
from app.clients.spring_client import SpringBackendClient


def test_spring_client_opens_circuit_after_consecutive_backend_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class FailingClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def request(self, method, url, params=None, json=None, headers=None):
            calls.append(url)
            raise httpx.ConnectError("backend down", request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "Client", FailingClient)
    client = SpringBackendClient(
        base_url="http://backend",
        retries=0,
        circuit_failure_threshold=2,
        circuit_cooldown_seconds=30,
    )

    with pytest.raises(BackendClientError, match="backend down"):
        client.catalog_search("shirt")
    with pytest.raises(BackendClientError, match="backend down"):
        client.catalog_search("shirt")
    with pytest.raises(BackendClientError, match="backend circuit open"):
        client.catalog_search("shirt")

    assert len(calls) == 2


def test_spring_client_allows_probe_after_circuit_cooldown_and_resets_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 1000.0
    responses: list[Any] = [
        httpx.ConnectError("backend down", request=httpx.Request("GET", "http://backend")),
        httpx.Response(200, json={"products": []}, request=httpx.Request("GET", "http://backend")),
        httpx.Response(200, json={"products": []}, request=httpx.Request("GET", "http://backend")),
    ]
    calls: list[str] = []

    class RecoveringClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def request(self, method, url, params=None, json=None, headers=None):
            calls.append(url)
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

    monkeypatch.setattr(httpx, "Client", RecoveringClient)
    client = SpringBackendClient(
        base_url="http://backend",
        retries=0,
        circuit_failure_threshold=1,
        circuit_cooldown_seconds=10,
        clock=lambda: now,
    )

    with pytest.raises(BackendClientError, match="backend down"):
        client.catalog_search("shirt")
    with pytest.raises(BackendClientError, match="backend circuit open"):
        client.catalog_search("shirt")

    now = 1011.0
    assert client.catalog_search("shirt") == []
    assert client.catalog_search("shirt") == []
    assert len(calls) == 3


def test_spring_client_unauthorized_does_not_open_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    class UnauthorizedClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def request(self, method, url, params=None, json=None, headers=None):
            nonlocal calls
            calls += 1
            return httpx.Response(401, json={"error": "unauthorized"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "Client", UnauthorizedClient)
    client = SpringBackendClient(
        base_url="http://backend",
        retries=0,
        circuit_failure_threshold=1,
        circuit_cooldown_seconds=30,
    )

    with pytest.raises(BackendClientError) as first:
        client.order_lookup("ES123", user_id="user-1")
    with pytest.raises(BackendClientError) as second:
        client.order_lookup("ES123", user_id="user-1")

    assert first.value.status == "unauthorized"
    assert second.value.status == "unauthorized"
    assert calls == 2


def test_spring_similar_recommendations_send_recent_product_ids_as_repeated_params(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_params: dict[str, Any] | None = None

    class CapturingClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def request(self, method, url, params=None, json=None, headers=None):
            nonlocal captured_params
            captured_params = params
            return httpx.Response(200, json={"products": []}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "Client", CapturingClient)
    client = SpringBackendClient(base_url="http://backend", retries=0)

    client.recommend_similar(variant_id="v001", recent_product_ids=["p001", "p002"])

    assert captured_params is not None
    assert captured_params["variantId"] == "v001"
    assert captured_params["recentProductIds"] == ["p001", "p002"]


def test_spring_client_returns_empty_similar_recommendations_when_backend_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnavailableRecommendationClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def request(self, method, url, params=None, json=None, headers=None):
            return httpx.Response(503, json={"error": "unavailable"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "Client", UnavailableRecommendationClient)
    client = SpringBackendClient(base_url="http://backend", retries=0)

    assert client.recommend_similar(variant_id="v001") == []


def test_spring_client_uses_backend_order_lookup_by_number(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_url = ""

    class CapturingClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def request(self, method, url, params=None, json=None, headers=None):
            nonlocal captured_url
            captured_url = url
            return httpx.Response(
                200,
                json={"orderNumber": "ES123", "orderStatus": "SHIPPED", "paymentStatus": "CAPTURED"},
                request=httpx.Request(method, url),
            )

    monkeypatch.setattr(httpx, "Client", CapturingClient)
    client = SpringBackendClient(base_url="http://backend", retries=0)

    order = client.order_lookup("ES123", user_id="user-1")

    assert captured_url == "http://backend/api/orders/by-number/ES123"
    assert order == {"orderNumber": "ES123", "orderStatus": "SHIPPED", "paymentStatus": "CAPTURED", "status": "SHIPPED"}


def test_spring_client_uses_backend_latest_purchased_item_path(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_url = ""

    class CapturingClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def request(self, method, url, params=None, json=None, headers=None):
            nonlocal captured_url
            captured_url = url
            return httpx.Response(200, json={"orderNumber": "ES123"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "Client", CapturingClient)
    client = SpringBackendClient(base_url="http://backend", retries=0)

    assert client.latest_purchased_item("product-1", user_id="user-1") == {"orderNumber": "ES123"}
    assert captured_url == "http://backend/api/orders/purchased-items/product-1/latest"


def test_spring_client_normalizes_backend_catalog_and_recommendation_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        httpx.Response(
            200,
            json={
                "content": [
                    {
                        "id": "p001",
                        "name": "Black Jacket",
                        "slug": "black-jacket",
                        "basePrice": 450000,
                        "category": {"slug": "jackets"},
                        "status": "ACTIVE",
                    }
                ]
            },
            request=httpx.Request("GET", "http://backend"),
        ),
        httpx.Response(
            200,
            json={
                "recommendations": [
                    {
                        "productId": "p002",
                        "variantId": "v002",
                        "productName": "White Hoodie",
                        "productSlug": "white-hoodie",
                        "price": 390000,
                        "similarityScore": 0.87,
                        "imageUrl": "https://cdn.local/white.jpg",
                    }
                ]
            },
            request=httpx.Request("GET", "http://backend"),
        ),
    ]

    class CapturingClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def request(self, method, url, params=None, json=None, headers=None):
            return responses.pop(0)

    monkeypatch.setattr(httpx, "Client", CapturingClient)
    client = SpringBackendClient(base_url="http://backend", retries=0)

    [catalog_product] = client.catalog_search("jacket")
    [recommendation] = client.recommend_similar(variant_id="v001")

    assert catalog_product["productId"] == "p001"
    assert catalog_product["price"] == 450000
    assert catalog_product["category"] == "jackets"
    assert recommendation["name"] == "White Hoodie"
    assert recommendation["slug"] == "white-hoodie"
    assert recommendation["recommendationScore"] == 0.87
