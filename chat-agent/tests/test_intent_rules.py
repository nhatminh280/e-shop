from __future__ import annotations

import pytest

from app.utils.intent_rules import classify_intent


@pytest.mark.parametrize(
    "message",
    [
        "cash on delivery payment",
        "can i pay by bank transfer",
        "how long does refund timing take",
        "password reset link expired",
        "how do i update my account address",
        "how do i get notified when an item restocks",
        "how do color and size variants work",
        "how do i cancel my order",
        "how do i download an invoice",
        "what does shipped order status mean",
    ],
)
def test_policy_or_faq_routes_knowledge_questions(message: str) -> None:
    assert classify_intent(message) == "policy_or_faq"


@pytest.mark.parametrize(
    "message",
    [
        "check order ES123",
        "order ES123",
        "don hang gan nhat",
    ],
)
def test_specific_order_lookup_still_routes_order_status(message: str) -> None:
    assert classify_intent(message.lower()) == "order_status"


def test_product_search_still_routes_catalog_questions() -> None:
    assert classify_intent("ao size M mau den con hang khong") == "product_search"


@pytest.mark.parametrize(
    "message",
    [
        "latest order",
        "where is my order",
        "tracking shipment",
        "giao hang don hang cua toi",
        "I already signed in, check my order",
    ],
)
def test_order_lookup_phrases_route_order_status(message: str) -> None:
    assert classify_intent(message.lower()) == "order_status"


def test_cart_action_with_variant_does_not_route_to_faq() -> None:
    assert classify_intent("add this variant to my cart") == "cart_action"


def test_account_address_update_still_routes_policy_or_faq() -> None:
    assert classify_intent("how do i update my account address") == "policy_or_faq"
