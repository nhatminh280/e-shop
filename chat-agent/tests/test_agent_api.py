from __future__ import annotations

import pytest
from pydantic import ValidationError

import app.graph.nodes as graph_nodes
from app.clients.base_client import BackendClientError
from app.main import chat, health
from app.schemas import AgentChatRequest


def test_health() -> None:
    assert health() == {"status": "ok", "service": "chat-agent"}


def test_chat_schema() -> None:
    response = chat(AgentChatRequest(sessionId="schema-test", message="hello"))
    body = response.model_dump(by_alias=True)

    assert body["sessionId"] == "schema-test"
    assert body["traceId"].startswith("trace_")
    assert body["intent"] == "general"
    assert body["responseType"] == "answer"
    assert "answer" in body
    assert isinstance(body["productCards"], list)
    assert isinstance(body["toolCalls"], list)
    assert body["needsConfirmation"] is False


def test_product_search_returns_cards() -> None:
    response = chat(AgentChatRequest(sessionId="product-test", message="ao size M mau den con hang khong?"))
    body = response.model_dump(by_alias=True)

    assert body["intent"] == "product_search"
    assert body["responseType"] == "product_results"
    assert body["productCards"]
    assert body["productCards"][0]["productId"]
    assert body["productCards"][0]["inStock"] is True
    assert body["toolCalls"][0]["toolName"] == "catalog.search"


def test_cart_draft_needs_confirmation() -> None:
    response = chat(AgentChatRequest(sessionId="cart-test", message="add jacket size M to cart"))
    body = response.model_dump(by_alias=True)

    assert body["intent"] == "cart_action"
    assert body["responseType"] == "draft_action"
    assert body["needsConfirmation"] is True
    assert body["draftAction"]["actionType"] == "cart.add"
    assert body["draftAction"]["status"] == "pending"
    assert body["draftAction"]["expiresAt"]
    assert body["draftAction"]["needsConfirmation"] is True
    assert body["draftAction"]["payload"]["quantity"] == 1


def test_unauthenticated_order_requires_sign_in() -> None:
    response = chat(
        AgentChatRequest(
            sessionId="order-test",
            message="check order ES123",
            authenticated=False,
        )
    )
    body = response.model_dump(by_alias=True)

    assert body["intent"] == "order_status"
    assert body["responseType"] == "auth_required"
    assert "sign in" in body["answer"].lower()
    assert body["toolCalls"] == []


def test_empty_message_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentChatRequest(sessionId="empty-test", message="")


def test_recommendation_flow_uses_previous_products() -> None:
    session_id = "recommend-session"
    chat(AgentChatRequest(sessionId=session_id, message="ao khoac den size M"))

    response = chat(AgentChatRequest(sessionId=session_id, message="goi y san pham tuong tu"))
    body = response.model_dump(by_alias=True)

    assert body["intent"] == "recommendation"
    assert body["responseType"] == "recommendations"
    assert body["productCards"]
    assert body["toolCalls"][0]["toolName"] == "recommend.similar"


def test_follow_up_contextual_cart_reference() -> None:
    session_id = "context-cart-session"
    first = chat(AgentChatRequest(sessionId=session_id, message="ao khoac den size M"))
    first_body = first.model_dump(by_alias=True)

    response = chat(AgentChatRequest(sessionId=session_id, message="them cai dau tien vao gio"))
    body = response.model_dump(by_alias=True)

    assert body["responseType"] == "draft_action"
    assert body["draftAction"]["payload"]["productId"] == first_body["productCards"][0]["productId"]
    assert body["draftAction"]["needsConfirmation"] is True


def test_remove_cart_draft_contextual_reference() -> None:
    session_id = "remove-cart-session"
    first = chat(AgentChatRequest(sessionId=session_id, message="ao khoac den size M"))
    first_body = first.model_dump(by_alias=True)

    response = chat(AgentChatRequest(sessionId=session_id, message="xoa san pham nay"))
    body = response.model_dump(by_alias=True)

    assert body["responseType"] == "draft_action"
    assert body["draftAction"]["actionType"] == "cart.remove_item"
    assert body["draftAction"]["payload"]["productId"] == first_body["productCards"][0]["productId"]


def test_update_quantity_cart_draft_contextual_reference() -> None:
    session_id = "update-cart-session"
    first = chat(AgentChatRequest(sessionId=session_id, message="ao khoac den size M"))
    first_body = first.model_dump(by_alias=True)

    response = chat(AgentChatRequest(sessionId=session_id, message="tang so luong len 2"))
    body = response.model_dump(by_alias=True)

    assert body["responseType"] == "draft_action"
    assert body["draftAction"]["actionType"] == "cart.update_quantity"
    assert body["draftAction"]["payload"]["quantity"] == 2
    assert body["draftAction"]["payload"]["productId"] == first_body["productCards"][0]["productId"]


def test_current_product_reference_in_vietnamese() -> None:
    session_id = "current-product-session"
    first = chat(AgentChatRequest(sessionId=session_id, message="ao khoac den size M"))
    first_body = first.model_dump(by_alias=True)

    response = chat(AgentChatRequest(sessionId=session_id, message="them san pham do vao gio"))
    body = response.model_dump(by_alias=True)

    assert body["responseType"] == "draft_action"
    assert body["draftAction"]["payload"]["productId"] == first_body["productCards"][0]["productId"]


def test_pronoun_remove_reference() -> None:
    session_id = "pronoun-product-session"
    first = chat(AgentChatRequest(sessionId=session_id, message="ao khoac den size M"))
    first_body = first.model_dump(by_alias=True)

    response = chat(AgentChatRequest(sessionId=session_id, message="xoa no di"))
    body = response.model_dump(by_alias=True)

    assert body["responseType"] == "draft_action"
    assert body["draftAction"]["actionType"] == "cart.remove_item"
    assert body["draftAction"]["payload"]["productId"] == first_body["productCards"][0]["productId"]


def test_support_handoff_draft_needs_confirmation() -> None:
    response = chat(AgentChatRequest(sessionId="support-session", message="toi muon gap nhan vien ho tro"))
    body = response.model_dump(by_alias=True)

    assert body["intent"] == "support_handoff"
    assert body["responseType"] == "handoff"
    assert body["needsConfirmation"] is True
    assert body["draftAction"]["actionType"] == "support.handoff"
    assert body["draftAction"]["status"] == "pending"


def test_empty_result_handling() -> None:
    response = chat(AgentChatRequest(sessionId="empty-result", message="giay nam duoi 500k"))
    body = response.model_dump(by_alias=True)

    assert body["intent"] == "product_search"
    assert body["responseType"] == "empty_result"
    assert body["fallbackCount"] == 1


def test_tool_timeout_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    class TimeoutCatalog:
        def search(self, query, filters=None):
            raise BackendClientError("timeout", status="timeout")

    monkeypatch.setattr(graph_nodes.tools, "catalog", TimeoutCatalog())

    response = chat(AgentChatRequest(sessionId="timeout-session", message="ao den size M"))
    body = response.model_dump(by_alias=True)

    assert body["responseType"] == "tool_error"
    assert body["toolCalls"][0]["status"] == "timeout"
    assert body["toolCalls"][0]["requestSummary"]
    assert body["toolCalls"][0]["responseSummary"] == "backend client error"
    assert body["fallbackCount"] == 1
