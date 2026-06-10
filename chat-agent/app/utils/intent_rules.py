from __future__ import annotations

import re

from app.schemas import Intent


ORDER_LOOKUP_TERMS = (
    "check order",
    "check my order",
    "where is my order",
    "don hang gan nhat",
    "latest order",
    "most recent order",
    "order es",
    "tracking",
    "shipment",
    "giao hang",
)
ORDER_FAQ_TERMS = ("cancel my order", "download an invoice", "order status mean", "what does shipped")
POLICY_OR_FAQ_TERMS = (
    "return",
    "refund",
    "shipping",
    "policy",
    "size guide",
    "doi tra",
    "van chuyen",
    "payment",
    "cash on delivery",
    "cod",
    "bank transfer",
    "pay by",
    "password",
    "reset link",
    "login",
    "sign in",
    "account",
    "address",
    "restock",
    "notified",
    "notify me",
    "variant",
    "invoice",
    "material",
    "fabric",
    "care",
    "wash",
    "waterproof",
    "water resistant",
    "best use",
)
CART_ACTION_TERMS = ("add", "cart", "gio hang", "them", "xoa", "remove", "tang so luong", "cap nhat")
PRODUCT_SEARCH_TERMS = (
    "ao",
    "quan",
    "giay",
    "jacket",
    "shirt",
    "short",
    "pants",
    "backpack",
    "balo",
    "size",
    "mau",
    "duoi",
    "tren",
    "con hang",
)


def classify_intent(text: str) -> Intent:
    if _contains_any(text, ORDER_FAQ_TERMS):
        return "policy_or_faq"
    if _contains_any(text, ORDER_LOOKUP_TERMS):
        return "order_status"
    if _contains_any(text, ("human", "support", "nhan vien", "tu van vien", "khieu nai", "ho tro")):
        return "support_handoff"
    if _contains_any(text, ("recommend", "goi y", "similar", "tuong tu")):
        return "recommendation"
    if _contains_any(text, CART_ACTION_TERMS):
        return "cart_action"
    if _contains_any(text, POLICY_OR_FAQ_TERMS):
        return "policy_or_faq"
    if _contains_any(text, PRODUCT_SEARCH_TERMS):
        return "product_search"
    return "general"


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_term(text, term) for term in terms)


def _contains_term(text: str, term: str) -> bool:
    if term == "variant":
        pattern = r"\bvariants?\b"
    elif term == "order es":
        pattern = r"\border\s+es\d+\b"
    else:
        pattern = r"\b" + r"\s+".join(re.escape(part) for part in term.split()) + r"\b"
    return re.search(pattern, text) is not None
