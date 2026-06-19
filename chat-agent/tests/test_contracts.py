from __future__ import annotations

from app.clients import MockBackendClient
from app.clients.base_client import BackendClientError
from app.tools.cart_tool import CartTool
from app.tools.catalog_tool import CatalogTool
from app.tools.order_tool import OrderTool
from app.tools.recommendation_tool import RecommendationTool


def test_catalog_contract_validates_required_product_fields() -> None:
    tool = CatalogTool(MockBackendClient())
    result = tool.search("shirt")

    assert result.status == "success"
    product = result.data[0].model_dump(by_alias=True)
    assert {"productId", "name", "slug", "category", "price", "inStock"} <= set(product)


class ThinCatalogSummaryClient(MockBackendClient):
    def catalog_search(self, query, filters=None, limit=4):
        return [
            {
                "productId": "p-thin",
                "name": "Thin Search Product",
                "slug": "thin-search-product",
                "category": "tops",
                "price": 99,
                "currency": "VND",
                "inStock": True,
                "stock": 0,
                "colors": [],
                "sizes": [],
                "imageUrl": None,
            }
        ]

    def catalog_detail(self, slug):
        if slug != "thin-search-product":
            return None
        return {
            "productId": "p-thin",
            "name": "Thin Search Product",
            "slug": "thin-search-product",
            "category": "tops",
            "price": 99,
            "currency": "VND",
            "imageUrl": "https://cdn.example.com/thin.jpg",
            "colors": ["Black"],
            "sizes": ["M", "L"],
            "stock": 12,
            "inStock": True,
        }


def test_catalog_search_enriches_thin_summary_cards_from_detail() -> None:
    tool = CatalogTool(ThinCatalogSummaryClient())

    result = tool.search("shirt")

    assert result.status == "success"
    product = result.data[0].model_dump(by_alias=True)
    assert product["imageUrl"] == "https://cdn.example.com/thin.jpg"
    assert product["colors"] == ["Black"]
    assert product["sizes"] == ["M", "L"]
    assert product["stock"] == 12


def test_order_contract_validates_required_order_fields() -> None:
    tool = OrderTool(MockBackendClient())
    result = tool.lookup("ES123", user_id="user-1")

    assert result.status == "success"
    assert result.data["status"]
    assert result.data["orderNumber"] == "ES123"


def test_cart_contract_validates_shape() -> None:
    tool = CartTool(MockBackendClient())
    result = tool.get(user_id="user-1")

    assert result.status == "success"
    assert {"userId", "items", "itemCount"} <= set(result.data)


def test_personalized_recommendation_contract_returns_ranked_cards() -> None:
    tool = RecommendationTool(MockBackendClient())

    result = tool.personalized(user_id="user-1", recent_product_ids=["p003"])

    assert result.status == "success"
    assert result.data[0].recommendation_rank == 1
    assert result.data[0].recommendation_score > 0
    assert result.data[0].recommendation_reason
    assert "rankedRecommendations=" in result.summary


def test_mock_recommendation_handles_null_tags() -> None:
    client = MockBackendClient()
    product_with_null_tags = {**client.data["products"][0], "productId": "p-null", "slug": "null-tags", "tags": None}
    client.data["products"].append(product_with_null_tags)

    result = RecommendationTool(client).personalized(user_id="user-1", recent_product_ids=["p-null"])

    assert result.status == "success"


class InvalidCatalogClient(MockBackendClient):
    def catalog_search(self, query, filters=None, limit=4):
        return [{"name": "Broken Product"}]


def test_invalid_catalog_payload_returns_structured_error() -> None:
    tool = CatalogTool(InvalidCatalogClient())
    result = tool.search("broken")

    assert result.status == "validation_error"
    assert result.summary == "invalid catalog payload"


class WrongTypeCatalogClient(MockBackendClient):
    def catalog_search(self, query, filters=None, limit=4):
        product = super().catalog_search(query, filters, limit)[0]
        return [{**product, "price": "not-a-number"}]


def test_wrong_type_catalog_payload_returns_validation_error() -> None:
    tool = CatalogTool(WrongTypeCatalogClient())
    result = tool.search("shirt")

    assert result.status == "validation_error"


class EmptyCatalogClient(MockBackendClient):
    def catalog_search(self, query, filters=None, limit=4):
        return []


def test_empty_catalog_payload_returns_empty_result() -> None:
    tool = CatalogTool(EmptyCatalogClient())
    result = tool.search("missing")

    assert result.status == "empty_result"


class TimeoutCatalogClient(MockBackendClient):
    def catalog_search(self, query, filters=None, limit=4):
        raise BackendClientError("timeout", status="timeout")


def test_tool_timeout_is_structured() -> None:
    tool = CatalogTool(TimeoutCatalogClient())

    result = tool.search("shirt")

    assert result.status == "timeout"


class UnauthorizedOrderClient(MockBackendClient):
    def order_lookup(self, order_id, user_id):
        raise BackendClientError("unauthorized", status="unauthorized")


def test_backend_401_maps_to_unauthorized() -> None:
    tool = OrderTool(UnauthorizedOrderClient())
    result = tool.lookup("ES123", user_id="user-1")

    assert result.status == "unauthorized"


class ServerErrorOrderClient(MockBackendClient):
    def order_lookup(self, order_id, user_id):
        raise BackendClientError("server error", status="backend_error")


def test_backend_500_maps_to_backend_error() -> None:
    tool = OrderTool(ServerErrorOrderClient())
    result = tool.lookup("ES123", user_id="user-1")

    assert result.status == "backend_error"


class InvalidOrderClient(MockBackendClient):
    def order_lookup(self, order_id, user_id):
        return {"orderNumber": "ES123"}


def test_invalid_order_payload_returns_validation_error() -> None:
    tool = OrderTool(InvalidOrderClient())
    result = tool.lookup("ES123", user_id="user-1")

    assert result.status == "validation_error"
