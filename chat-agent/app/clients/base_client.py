from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BackendClientError(Exception):
    def __init__(self, message: str, status: str = "backend_error") -> None:
        super().__init__(message)
        self.status = status


class BackendClient(ABC):
    @abstractmethod
    def catalog_search(self, query: str, filters: dict[str, Any] | None = None, limit: int = 4) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def catalog_filter(self, filters: dict[str, Any], limit: int = 4) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def catalog_detail(self, slug: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def recommend_similar(
        self,
        product_id: str | None = None,
        variant_id: str | None = None,
        recent_product_ids: list[str] | None = None,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def recommend_personalized(
        self,
        user_id: str | None = None,
        recent_product_ids: list[str] | None = None,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def cart_get(self, user_id: str | None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def order_list(self, user_id: str | None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def order_lookup(self, order_id: str, user_id: str | None) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def latest_purchased_item(self, product_id: str | None, user_id: str | None) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def knowledge_retrieve(self, query: str, limit: int = 2) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def support_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def confirm_draft_action(self, draft_action_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def cancel_draft_action(self, draft_action_id: str) -> dict[str, Any]:
        raise NotImplementedError
