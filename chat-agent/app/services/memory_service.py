from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.schemas import ProductCard


@dataclass
class SessionMemory:
    previous_products: list[ProductCard] = field(default_factory=list)
    previous_tool_results: list[dict[str, Any]] = field(default_factory=list)
    last_intent: str | None = None
    last_assistant_response: str | None = None
    last_selected_product: ProductCard | None = None
    last_selected_order: dict[str, Any] | None = None


def _ttl_seconds() -> int:
    return int(os.getenv("SESSION_MEMORY_TTL_SECONDS", "86400"))


def _max_size() -> int:
    return int(os.getenv("SESSION_MEMORY_MAX_SIZE", "10000"))


class MemoryService:
    def __init__(self) -> None:
        self._sessions: dict[str, tuple[SessionMemory, float]] = {}
        self._lock = threading.Lock()

    def _purge_expired_unlocked(self, now: float) -> None:
        expired = [k for k, (_, exp) in self._sessions.items() if exp < now]
        for k in expired:
            self._sessions.pop(k, None)

    def _evict_oldest_unlocked(self, count: int) -> None:
        oldest = sorted(self._sessions.items(), key=lambda kv: kv[1][1])[:count]
        for k, _ in oldest:
            self._sessions.pop(k, None)

    def get(self, session_id: str) -> SessionMemory:
        ttl = _ttl_seconds()
        max_size = _max_size()
        now = time.time()
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is not None and entry[1] >= now:
                memory, _ = entry
                self._sessions[session_id] = (memory, now + ttl)
                return memory
            self._purge_expired_unlocked(now)
            if len(self._sessions) >= max_size:
                self._evict_oldest_unlocked(max(1, max_size // 4))
            memory = SessionMemory()
            self._sessions[session_id] = (memory, now + ttl)
            return memory

    def update(
        self,
        session_id: str,
        *,
        products: list[ProductCard],
        tool_results: list[dict[str, Any]],
        intent: str,
        assistant_response: str,
        selected_product: ProductCard | None = None,
        selected_order: dict[str, Any] | None = None,
    ) -> None:
        memory = self.get(session_id)
        if products:
            memory.previous_products = products
            memory.last_selected_product = selected_product or products[0]
        if tool_results:
            memory.previous_tool_results = tool_results
        if selected_product:
            memory.last_selected_product = selected_product
        if selected_order:
            memory.last_selected_order = selected_order
        memory.last_intent = intent
        memory.last_assistant_response = assistant_response

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._sessions)


memory_service = MemoryService()
