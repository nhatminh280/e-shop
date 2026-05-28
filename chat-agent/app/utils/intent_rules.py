from __future__ import annotations

from app.schemas import Intent


def classify_intent(text: str) -> Intent:
    if any(term in text for term in ("order", "don hang", "tracking", "shipment", "giao hang", "gan nhat")):
        return "order_status"
    if any(term in text for term in ("human", "support", "nhan vien", "tu van vien", "khieu nai", "ho tro")):
        return "support_handoff"
    if any(term in text for term in ("add", "cart", "gio hang", "them", "xoa", "remove", "tang so luong", "cap nhat")):
        return "cart_action"
    if any(term in text for term in ("recommend", "goi y", "similar", "tuong tu")):
        return "recommendation"
    if any(term in text for term in ("return", "refund", "shipping", "policy", "size guide", "doi tra", "van chuyen")):
        return "policy_or_faq"
    if any(
        term in text
        for term in (
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
    ):
        return "product_search"
    return "general"
