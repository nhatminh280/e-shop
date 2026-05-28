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
