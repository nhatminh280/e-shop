from __future__ import annotations

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


class MemoryService:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionMemory] = {}

    def get(self, session_id: str) -> SessionMemory:
        return self._sessions.setdefault(session_id, SessionMemory())

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
        self._sessions.clear()


memory_service = MemoryService()
