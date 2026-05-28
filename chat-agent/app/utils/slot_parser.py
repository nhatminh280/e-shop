from __future__ import annotations

import re
from typing import Any


COLOR_MAP = {
    "black": "black",
    "den": "black",
    "blue": "blue",
    "xanh": "blue",
    "white": "white",
    "trang": "white",
    "red": "red",
    "do": "red",
    "green": "green",
    "gray": "gray",
    "navy": "navy",
    "khaki": "khaki",
}

CATEGORY_MAP = {
    "ao khoac": "jacket",
    "jacket": "jacket",
    "raincoat": "jacket",
    "ao": "shirt",
    "shirt": "shirt",
    "tee": "shirt",
    "short": "shorts",
    "shorts": "shorts",
    "quan short": "shorts",
    "quan dai": "pants",
    "pants": "pants",
    "giay": "shoes",
    "shoes": "shoes",
    "fleece": "fleece",
    "vest": "vest",
    "backpack": "backpack",
    "bag": "backpack",
    "balo": "backpack",
}

GENDER_MAP = {"nam": "men", "men": "men", "nu": "women", "women": "women", "unisex": "unisex"}

ORDINAL_MAP = {
    "first": 0,
    "dau tien": 0,
    "cai dau tien": 0,
    "san pham dau tien": 0,
    "second": 1,
    "thu hai": 1,
    "cai thu hai": 1,
    "third": 2,
    "thu ba": 2,
}

STOP_WORDS = {
    "add",
    "cart",
    "gio",
    "hang",
    "them",
    "vao",
    "size",
    "mau",
    "con",
    "khong",
    "toi",
    "muon",
    "can",
    "check",
    "order",
    "goi",
    "y",
    "tuong",
    "tu",
    "duoi",
    "tren",
}


def extract_slots(text: str, original_message: str) -> dict[str, Any]:
    slots: dict[str, Any] = {}

    size_match = re.search(r"\b(xs|s|m|l|xl|xxl|os)\b", text, flags=re.IGNORECASE)
    if size_match:
        slots["size"] = size_match.group(1).upper()

    for source, normalized in COLOR_MAP.items():
        if re.search(rf"\b{re.escape(source)}\b", text):
            slots["color"] = normalized
            break

    for source, normalized in sorted(CATEGORY_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = r"\b" + r"\s+".join(re.escape(part) for part in source.split()) + r"\b"
        if re.search(pattern, text):
            slots["category"] = normalized
            break

    for source, normalized in GENDER_MAP.items():
        if re.search(rf"\b{source}\b", text):
            slots["gender"] = normalized
            break

    for source, ordinal in ORDINAL_MAP.items():
        if source in text:
            slots["ordinal"] = ordinal
            break

    if any(
        term in text
        for term in (
            "san pham nay",
            "san pham do",
            "cai nay",
            "cai do",
            "no",
            "this product",
            "this item",
            "that product",
            "that item",
        )
    ):
        slots["product_reference"] = "current"

    order_match = re.search(r"\bES\d{3,}\b", original_message, flags=re.IGNORECASE)
    if order_match:
        slots["order_id"] = order_match.group(0).upper()
    elif "gan nhat" in text:
        slots["order_id"] = "latest"

    product_id_match = re.search(r"\bp\d{3,}\b", text, flags=re.IGNORECASE)
    if product_id_match:
        slots["product_id"] = product_id_match.group(0).lower()

    slug_match = re.search(r"\b[a-z0-9]+(?:-[a-z0-9]+){2,}\b", text)
    if slug_match:
        slots["product_slug"] = slug_match.group(0)

    quantity_match = re.search(r"\b(?:qty|quantity|so luong|len)\s*(\d{1,2})\b", text)
    slots["quantity"] = int(quantity_match.group(1)) if quantity_match else 1

    under_match = re.search(r"\b(?:duoi|under|below)\s*(\d+)\s*(k|tr|m|000)?\b", text)
    if under_match:
        slots["price_max"] = _parse_money(under_match.group(1), under_match.group(2))

    over_match = re.search(r"\b(?:tren|over|above)\s*(\d+)\s*(k|tr|m|000)?\b", text)
    if over_match:
        slots["price_min"] = _parse_money(over_match.group(1), over_match.group(2))

    if any(term in text for term in ("stock", "con hang", "available")):
        slots["in_stock"] = True

    if any(term in text for term in ("xoa", "remove")):
        slots["action_type"] = "remove"
    elif any(term in text for term in ("tang so luong", "cap nhat", "update")):
        slots["action_type"] = "update_quantity"
    else:
        slots["action_type"] = "add"

    tokens = [token for token in re.findall(r"[a-z0-9]+", text) if token not in STOP_WORDS]
    if slots.get("category"):
        slots["query"] = slots["category"]
    elif tokens:
        slots["query"] = " ".join(tokens)

    return slots


def _parse_money(amount: str, suffix: str | None) -> int:
    value = int(amount)
    if suffix == "k":
        return value * 1000
    if suffix in {"tr", "m"}:
        return value * 1_000_000
    if suffix == "000":
        return value * 1000
    return value
