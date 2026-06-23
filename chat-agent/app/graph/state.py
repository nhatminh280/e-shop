from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from app.schemas import DraftAction, Intent, NodeTrace, ProductCard, ToolCallTrace


class GraphState(TypedDict):
    session_id: str
    trace_id: str
    user_id: NotRequired[str | None]
    authenticated: bool
    message: str
    normalized_message: NotRequired[str]
    page_context: NotRequired[dict[str, Any]]
    intent: NotRequired[Intent]
    intent_confidence: NotRequired[float]
    routing_confidence: NotRequired[float]
    needs_review: NotRequired[bool]
    slots: NotRequired[dict[str, Any]]
    route: NotRequired[str]
    answer: NotRequired[str]
    response_type: NotRequired[str]
    product_cards: NotRequired[list[ProductCard]]
    draft_action: NotRequired[DraftAction | None]
    needs_confirmation: NotRequired[bool]
    tool_calls: NotRequired[list[ToolCallTrace]]
    node_trace: NotRequired[list[NodeTrace]]
    previous_products: NotRequired[list[ProductCard]]
    previous_tool_results: NotRequired[list[dict[str, Any]]]
    last_intent: NotRequired[str | None]
    last_assistant_response: NotRequired[str | None]
    last_selected_product: NotRequired[ProductCard | None]
    last_selected_order: NotRequired[dict[str, Any] | None]
    grounding_documents: NotRequired[list[dict[str, Any]]]
    grounding_order: NotRequired[dict[str, Any] | None]
    fallback_count: NotRequired[int]
