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

    def _get_optional_feature(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        fallback_status_codes: set[int] | None = None,
    ) -> Any | None:
        return self._request(
            "GET",
            path,
            params=params,
            fallback_status_codes=fallback_status_codes or {404, 501},
        )

    def _post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return self._request("POST", path, json=payload or {})

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        fallback_status_codes: set[int] | None = None,
    ) -> Any:
        self._raise_if_circuit_open()
        headers = {"x-agent-client": "chat-agent", **get_trace_headers()}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        last_error: Exception | None = None
        last_status_code: int | None = None
        for _ in range(self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.request(method, f"{self.base_url}{path}", params=params, json=json, headers=headers)
                if response.status_code in (401, 403):
                    self._record_circuit_success()
                    raise BackendClientError("backend request unauthorized", status="unauthorized")
                if fallback_status_codes and response.status_code in fallback_status_codes:
                    return None
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    last_status_code = response.status_code
                    continue
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
        raise BackendClientError(str(last_error or "backend request failed"), status=status, status_code=last_status_code)

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
        payload = self._get("/api/catalog/products/search", {"q": query, "size": limit, **(filters or {})})
        return [_normalize_product(product) for product in _extract_list(payload, "products")]

    def catalog_filter(self, filters: dict[str, Any], limit: int = 4) -> list[dict[str, Any]]:
        payload = self._get("/api/catalog/products/filter", {"size": limit, **filters})
        return [_normalize_product(product) for product in _extract_list(payload, "products")]

    def catalog_detail(self, slug: str) -> dict[str, Any] | None:
        payload = self._get(f"/api/catalog/products/{slug}")
        return _normalize_product(payload) if isinstance(payload, dict) else None

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
        if not variant_id:
            return []
        try:
            payload = self._get("/api/recommendations/similar", {key: value for key, value in params.items() if value})
        except BackendClientError:
            return []
        return [_normalize_product(product) for product in _extract_list(payload, "products")]

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
        payload = self._get_optional_feature(
            "/api/recommendations/personalized",
            {key: value for key, value in params.items() if value},
        )
        if payload is None:
            return []
        return [_normalize_product(product) for product in _extract_list(payload, "products")]

    def cart_get(self, user_id: str | None) -> dict[str, Any]:
        payload = self._get("/api/cart")
        return payload if isinstance(payload, dict) else {}

    def order_list(self, user_id: str | None) -> list[dict[str, Any]]:
        payload = self._get("/api/orders")
        return [_normalize_order(order) for order in _extract_list(payload, "orders")]

    def order_lookup(self, order_id: str, user_id: str | None) -> dict[str, Any] | None:
        payload = self._get(f"/api/orders/by-number/{order_id}")
        return _normalize_order(payload) if isinstance(payload, dict) else None

    def latest_purchased_item(self, product_id: str | None, user_id: str | None) -> dict[str, Any] | None:
        if not product_id:
            return None
        payload = self._get(f"/api/orders/purchased-items/{product_id}/latest")
        return payload if isinstance(payload, dict) else None

    def knowledge_retrieve(self, query: str, limit: int = 2) -> list[dict[str, Any]]:
        payload = self._get("/api/knowledge/search", {"q": query, "limit": limit})
        return _extract_list(payload, "documents")

    def support_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._post("/api/support/conversations", _support_payload(payload))
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
        value = payload.get(preferred_key) or payload.get("recommendations") or payload.get("items") or payload.get("content") or payload.get("data")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_product(product: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(product)
    variants = product.get("variants") if isinstance(product.get("variants"), list) else []
    first_variant = next((variant for variant in variants if isinstance(variant, dict)), None)

    normalized["productId"] = product.get("productId") or product.get("id")
    normalized["variantId"] = product.get("variantId") or (first_variant or {}).get("id") or (first_variant or {}).get("variantId")
    normalized["name"] = product.get("name") or product.get("productName") or ""
    normalized["slug"] = product.get("slug") or product.get("productSlug") or ""
    normalized["category"] = _category_value(product.get("category"))
    normalized["price"] = product.get("price") or product.get("basePrice") or (first_variant or {}).get("price") or 0
    normalized["currency"] = product.get("currency") or (first_variant or {}).get("currency") or "VND"
    normalized["imageUrl"] = product.get("imageUrl") or _image_url(product)
    normalized["colors"] = product.get("colors") if isinstance(product.get("colors"), list) else _variant_values(variants, "color")
    normalized["sizes"] = product.get("sizes") if isinstance(product.get("sizes"), list) else _variant_values(variants, "size")
    normalized["stock"] = product.get("stock") if product.get("stock") is not None else _stock(variants)
    normalized["inStock"] = product.get("inStock") if product.get("inStock") is not None else _in_stock(product, variants)
    if product.get("similarityScore") is not None and normalized.get("recommendationScore") is None:
        normalized["recommendationScore"] = product["similarityScore"]
    return normalized


def _normalize_order(order: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(order)
    normalized["status"] = order.get("status") or order.get("orderStatus")
    return normalized


def _support_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "message" in payload:
        return payload
    summary = str(payload.get("summary") or "Chat support handoff")
    transcript = payload.get("transcript")
    message = _transcript_message(transcript) or summary
    return {"subject": summary[:180], "message": message, "attachmentUrls": payload.get("attachmentUrls") or []}


def _category_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("slug") or value.get("name") or value.get("id") or "uncategorized")
    if value:
        return str(value)
    return "uncategorized"


def _image_url(product: dict[str, Any]) -> str | None:
    images = product.get("images")
    if not isinstance(images, list):
        return None
    valid_images = [image for image in images if isinstance(image, dict)]
    primary = next((image for image in valid_images if image.get("primary") is True), None)
    image = primary or (valid_images[0] if valid_images else None)
    return str(image.get("imageUrl")) if image and image.get("imageUrl") else None


def _variant_values(variants: list[Any], field: str) -> list[str]:
    values: list[str] = []
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        raw_value = variant.get(field)
        if isinstance(raw_value, dict):
            raw_value = raw_value.get("name") or raw_value.get("slug") or raw_value.get("value")
        if raw_value and str(raw_value) not in values:
            values.append(str(raw_value))
    return values


def _stock(variants: list[Any]) -> int:
    total = 0
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        raw_stock = variant.get("stock", variant.get("quantityInStock", 0))
        try:
            total += int(raw_stock or 0)
        except (TypeError, ValueError):
            continue
    return total


def _in_stock(product: dict[str, Any], variants: list[Any]) -> bool:
    if variants:
        return _stock(variants) > 0
    status = str(product.get("status") or "").upper()
    return status == "ACTIVE"


def _transcript_message(transcript: Any) -> str | None:
    if not isinstance(transcript, list):
        return None
    lines = []
    for entry in transcript:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role") or "user"
        content = entry.get("content")
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else None
