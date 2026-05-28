import os

from .base_client import BackendClient, BackendClientError
from .mock_backend_client import MockBackendClient
from .spring_client import SpringBackendClient


def create_backend_client() -> BackendClient:
    use_mock = os.getenv("USE_MOCK_BACKEND", "true").lower() in {"1", "true", "yes"}
    return MockBackendClient() if use_mock else SpringBackendClient()


__all__ = ["BackendClient", "BackendClientError", "MockBackendClient", "SpringBackendClient", "create_backend_client"]
