from __future__ import annotations

import re
from typing import Any, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import NotRequired, TypedDict

from mock_catalog import lookup_order, search_products


Intent = Literal["product_search", "order_status", "cart_action", "handoff", "general"]


class ChatState(TypedDict):
    session_id: str
    message: str
    intent: NotRequired[Intent]
    slots: NotRequired[dict[str, Any]]
    products: NotRequired[list[dict[str, Any]]]
    order: NotRequired[dict[str, Any] | None]
    draft_action: NotRequired[dict[str, Any] | None]
    answer: NotRequired[str]
    trace: NotRequired[list[str]]


def _append_trace(state: ChatState, step: str) -> list[str]:
    return [*state.get("trace", []), step]


def classify_intent(state: ChatState) -> dict[str, Any]:
    text = state["message"].lower()
    if any(word in text for word in ("order", "don hang", "tracking", "ship", "giao hang")):
        intent: Intent = "order_status"
    elif any(word in text for word in ("cart", "gio hang", "add", "them vao gio")):
        intent = "cart_action"
    elif any(word in text for word in ("human", "support", "nhan vien", "tu van vien", "khieu nai")):
        intent = "handoff"
    elif any(word in text for word in ("ao", "quan", "shirt", "short", "jacket", "size", "mau", "con hang")):
        intent = "product_search"
    else:
        intent = "general"

    return {"intent": intent, "trace": _append_trace(state, f"classify_intent:{intent}")}


def collect_slots(state: ChatState) -> dict[str, Any]:
    message = state["message"]
    text = message.lower()
    slots: dict[str, Any] = {}

    size_match = re.search(r"\b(xs|s|m|l|xl|xxl)\b", text, re.IGNORECASE)
    if size_match:
        slots["size"] = size_match.group(1).upper()

    for color in ("black", "blue", "white", "green", "navy", "red", "den", "xanh", "trang", "do"):
        if color in text:
            slots["color"] = {
                "den": "black",
                "xanh": "blue",
                "trang": "white",
                "do": "red",
            }.get(color, color)
            break

    order_match = re.search(r"\bES\d{3,}\b", message, re.IGNORECASE)
    if order_match:
        slots["order_code"] = order_match.group(0).upper()

    product_words = []
    for word in ("shirt", "shorts", "jacket", "ao", "quan"):
        if word in text:
            product_words.append({"ao": "shirt", "quan": "shorts"}.get(word, word))
    slots["query"] = " ".join(product_words) if product_words else message

    return {"slots": slots, "trace": _append_trace(state, "collect_slots")}


def route_after_slots(state: ChatState) -> str:
    intent = state.get("intent", "general")
    return intent


def product_search_node(state: ChatState) -> dict[str, Any]:
    slots = state.get("slots", {})
    products = search_products(
        query=str(slots.get("query", state["message"])),
        size=slots.get("size"),
        color=slots.get("color"),
    )
    return {"products": products, "trace": _append_trace(state, f"search_products:{len(products)}")}


def order_status_node(state: ChatState) -> dict[str, Any]:
    order_code = state.get("slots", {}).get("order_code")
    order = lookup_order(order_code) if order_code else None
    return {"order": order, "trace": _append_trace(state, "lookup_order")}


def cart_action_node(state: ChatState) -> dict[str, Any]:
    products = search_products(query=state.get("slots", {}).get("query", state["message"]))
    draft_action = None
    if products:
        draft_action = {
            "type": "ADD_TO_CART_CONFIRMATION_REQUIRED",
            "productId": products[0]["id"],
            "productName": products[0]["name"],
        }
    return {"products": products[:1], "draft_action": draft_action, "trace": _append_trace(state, "prepare_cart_action")}


def handoff_node(state: ChatState) -> dict[str, Any]:
    return {
        "draft_action": {"type": "CREATE_SUPPORT_CONVERSATION"},
        "trace": _append_trace(state, "handoff"),
    }


def general_node(state: ChatState) -> dict[str, Any]:
    return {"trace": _append_trace(state, "general")}


def answer_node(state: ChatState) -> dict[str, Any]:
    intent = state.get("intent", "general")
    if intent == "product_search":
        products = state.get("products", [])
        if not products:
            answer = "I could not find a matching product. Try a category like shirt, shorts, or jacket."
        else:
            lines = [
                f"- {item['name']} | {item['price']:,} VND | stock {item['stock']} | sizes {', '.join(item['sizes'])}"
                for item in products
            ]
            answer = "Here are matching products:\n" + "\n".join(lines)
    elif intent == "order_status":
        order = state.get("order")
        if not order:
            answer = "Please send an order code like ES123 so I can check the status."
        else:
            answer = (
                f"Order {order['orderCode']} is {order['status']}, payment is "
                f"{order['paymentStatus']}, estimated delivery {order['eta']}."
            )
    elif intent == "cart_action":
        action = state.get("draft_action")
        if not action:
            answer = "I need the product name or category before preparing a cart action."
        else:
            answer = f"I found {action['productName']}. Please confirm before I add it to cart."
    elif intent == "handoff":
        answer = "I can create a support conversation and pass this to staff."
    else:
        answer = "I can help search products, check order status, prepare cart actions, or hand off to support."

    return {"answer": answer, "trace": _append_trace(state, "answer")}


def build_graph():
    builder = StateGraph(ChatState)
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("collect_slots", collect_slots)
    builder.add_node("product_search", product_search_node)
    builder.add_node("order_status", order_status_node)
    builder.add_node("cart_action", cart_action_node)
    builder.add_node("handoff", handoff_node)
    builder.add_node("general", general_node)
    builder.add_node("answer", answer_node)

    builder.add_edge(START, "classify_intent")
    builder.add_edge("classify_intent", "collect_slots")
    builder.add_conditional_edges(
        "collect_slots",
        route_after_slots,
        {
            "product_search": "product_search",
            "order_status": "order_status",
            "cart_action": "cart_action",
            "handoff": "handoff",
            "general": "general",
        },
    )
    builder.add_edge("product_search", "answer")
    builder.add_edge("order_status", "answer")
    builder.add_edge("cart_action", "answer")
    builder.add_edge("handoff", "answer")
    builder.add_edge("general", "answer")
    builder.add_edge("answer", END)

    return builder.compile(checkpointer=InMemorySaver())


chat_graph = build_graph()


def run_chat(message: str, session_id: str = "demo") -> ChatState:
    config = {"configurable": {"thread_id": session_id}}
    return chat_graph.invoke(
        {
            "session_id": session_id,
            "message": message,
            "trace": [],
        },
        config=config,
    )
