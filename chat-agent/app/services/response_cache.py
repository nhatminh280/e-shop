from __future__ import annotations

import os
import threading
import time
from typing import Any

# Only cache responses for intents where the answer doesn't depend on
# real-time data. product_search / order_status / recommendation / cart_action
# all change based on inventory / orders, so they must NOT be cached.
CACHEABLE_INTENTS: set[str] = {"policy_or_faq", "general", "support_handoff"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes"}


def _ttl_seconds() -> int:
    return int(os.getenv("RESPONSE_CACHE_TTL_SECONDS", "3600"))


def _max_size() -> int:
    return int(os.getenv("RESPONSE_CACHE_MAX_SIZE", "512"))


def _enabled() -> bool:
    return _env_bool("RESPONSE_CACHE_ENABLED", True)


_lock = threading.Lock()
_store: dict[str, tuple[dict[str, Any], float]] = {}


def _key(message: str, authenticated: bool) -> str:
    normalized = " ".join(message.lower().strip().split())
    return f"{int(authenticated)}|{normalized}"


def get(message: str, authenticated: bool = False) -> dict[str, Any] | None:
    if not _enabled():
        return None
    key = _key(message, authenticated)
    now = time.time()
    with _lock:
        entry = _store.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if expires_at < now:
            _store.pop(key, None)
            return None
        return value


def put(
    message: str,
    intent: str,
    response: dict[str, Any],
    authenticated: bool = False,
) -> None:
    if not _enabled() or intent not in CACHEABLE_INTENTS:
        return
    key = _key(message, authenticated)
    ttl = _ttl_seconds()
    max_size = _max_size()
    now = time.time()
    with _lock:
        if len(_store) >= max_size:
            expired = [k for k, (_, exp) in _store.items() if exp < now]
            for k in expired[: max_size // 4 or 1]:
                _store.pop(k, None)
            if len(_store) >= max_size:
                for k in list(_store.keys())[: max_size // 4 or 1]:
                    _store.pop(k, None)
        _store[key] = (response, now + ttl)


def clear() -> None:
    with _lock:
        _store.clear()


def size() -> int:
    with _lock:
        return len(_store)
