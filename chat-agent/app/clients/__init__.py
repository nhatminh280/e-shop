import os

from .base_client import BackendClient, BackendClientError
from .mock_backend_client import MockBackendClient
from .spring_client import SpringBackendClient


def create_backend_client() -> BackendClient:
    use_mock = _env_bool("MOCK_BACKEND", _env_bool("USE_MOCK_BACKEND", True))
    return MockBackendClient() if use_mock else SpringBackendClient()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes"}


__all__ = ["BackendClient", "BackendClientError", "MockBackendClient", "SpringBackendClient", "create_backend_client"]
