from __future__ import annotations

import os
import time
from collections.abc import Callable
from threading import Lock
from typing import Any

import httpx

from app.services.trace_context_service import get_trace_headers

from .base_client import BackendClient, BackendClientError


class SpringBackendClient(BackendClient):
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        retries: int | None = None,
        auth_token: str | None = None,
        circuit_failure_threshold: int | None = None,
        circuit_cooldown_seconds: float | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("BACKEND_BASE_URL") or "http://localhost:8080").rstrip("/")
        self.timeout_seconds = timeout_seconds or float(os.getenv("BACKEND_TIMEOUT_SECONDS", "2.0"))
        self.retries = retries if retries is not None else int(os.getenv("BACKEND_RETRIES", "1"))
        self.auth_token = auth_token
        self.circuit_failure_threshold = circuit_failure_threshold or int(os.getenv("BACKEND_CIRCUIT_FAILURE_THRESHOLD", "3"))
        self.circuit_cooldown_seconds = circuit_cooldown_seconds or float(os.getenv("BACKEND_CIRCUIT_COOLDOWN_SECONDS", "10.0"))
        self._clock = clock or time.monotonic
        self._circuit_lock = Lock()
        self._consecutive_failures = 0
        self._circuit_opened_at: float | None = None

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def _post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return self._request("POST", path, json=payload or {})

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        self._raise_if_circuit_open()
        headers = {"x-agent-client": "chat-agent", **get_trace_headers()}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        last_error: Exception | None = None
        for _ in range(self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.request(method, f"{self.base_url}{path}", params=params, json=json, headers=headers)
                if response.status_code in (401, 403):
                    self._record_circuit_success()
                    raise BackendClientError("backend request unauthorized", status="unauthorized")
                response.raise_for_status()
                self._record_circuit_success()
                return response.json()
            except httpx.TimeoutException as exc:
                last_error = exc
            except BackendClientError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc

        status = "timeout" if isinstance(last_error, httpx.TimeoutException) else "backend_error"
        self._record_circuit_failure()
        raise BackendClientError(str(last_error or "backend request failed"), status=status)

    def _raise_if_circuit_open(self) -> None:
        with self._circuit_lock:
            if self._circuit_opened_at is None:
                return
            elapsed = self._clock() - self._circuit_opened_at
            if elapsed < self.circuit_cooldown_seconds:
                raise BackendClientError("backend circuit open", status="backend_error")
            self._circuit_opened_at = None

    def _record_circuit_success(self) -> None:
        with self._circuit_lock:
            self._consecutive_failures = 0
            self._circuit_opened_at = None

    def _record_circuit_failure(self) -> None:
        with self._circuit_lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.circuit_failure_threshold:
                self._circuit_opened_at = self._clock()

    def catalog_search(self, query: str, filters: dict[str, Any] | None = None, limit: int = 4) -> list[dict[str, Any]]:
        payload = self._get("/api/catalog/products/search", {"q": query, "limit": limit, **(filters or {})})
        return _extract_list(payload, "products")

    def catalog_filter(self, filters: dict[str, Any], limit: int = 4) -> list[dict[str, Any]]:
        payload = self._get("/api/catalog/products/filter", {"limit": limit, **filters})
        return _extract_list(payload, "products")

    def catalog_detail(self, slug: str) -> dict[str, Any] | None:
        payload = self._get(f"/api/catalog/products/{slug}")
        return payload if isinstance(payload, dict) else None

    def recommend_similar(
        self,
        product_id: str | None = None,
        variant_id: str | None = None,
        recent_product_ids: list[str] | None = None,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        params = {
            "productId": product_id,
            "variantId": variant_id,
            "recentProductIds": recent_product_ids or [],
            "limit": limit,
        }
        payload = self._get("/api/recommendations/similar", {key: value for key, value in params.items() if value})
        return _extract_list(payload, "products")

    def recommend_personalized(
        self,
        user_id: str | None = None,
        recent_product_ids: list[str] | None = None,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        params = {
            "userId": user_id,
            "recentProductIds": recent_product_ids or [],
            "limit": limit,
        }
        payload = self._get("/api/recommendations/personalized", {key: value for key, value in params.items() if value})
        return _extract_list(payload, "products")

    def cart_get(self, user_id: str | None) -> dict[str, Any]:
        payload = self._get("/api/cart")
        return payload if isinstance(payload, dict) else {}

    def order_list(self, user_id: str | None) -> list[dict[str, Any]]:
        payload = self._get("/api/orders")
        return _extract_list(payload, "orders")

    def order_lookup(self, order_id: str, user_id: str | None) -> dict[str, Any] | None:
        payload = self._get(f"/api/orders/{order_id}")
        return payload if isinstance(payload, dict) else None

    def latest_purchased_item(self, product_id: str | None, user_id: str | None) -> dict[str, Any] | None:
        params = {"productId": product_id} if product_id else None
        payload = self._get("/api/orders/latest-purchased-item", params)
        return payload if isinstance(payload, dict) else None

    def knowledge_retrieve(self, query: str, limit: int = 2) -> list[dict[str, Any]]:
        payload = self._get("/api/knowledge/search", {"q": query, "limit": limit})
        return _extract_list(payload, "documents")

    def support_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._post("/api/support/conversations", payload)
        return response if isinstance(response, dict) else {}

    def confirm_draft_action(self, draft_action_id: str) -> dict[str, Any]:
        response = self._post(f"/api/chat/actions/{draft_action_id}/confirm")
        return response if isinstance(response, dict) else {}

    def cancel_draft_action(self, draft_action_id: str) -> dict[str, Any]:
        response = self._post(f"/api/chat/actions/{draft_action_id}/cancel")
        return response if isinstance(response, dict) else {}


def _extract_list(payload: Any, preferred_key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        value = payload.get(preferred_key) or payload.get("items") or payload.get("content") or payload.get("data")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []
