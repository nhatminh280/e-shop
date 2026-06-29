from __future__ import annotations

from app.graph.nodes import _infer_slots_from_memory
from app.schemas import ProductCard


def _product(pid: str, category: str = "jackets") -> ProductCard:
    return ProductCard(
        productId=pid,
        name=f"Test {pid}",
        slug=f"test-{pid}",
        category=category,
        gender="unisex",
        price=100,
        currency="USD",
        inStock=True,
    )


def test_infers_category_from_memory_when_missing():
    state = {
        "previous_products": [
            _product("p1", "jackets"),
            _product("p2", "jackets"),
            _product("p3", "jackets"),
        ]
    }
    slots = {"color": "blue"}
    augmented = _infer_slots_from_memory(slots, state)
    assert augmented["category"] == "jackets"
    assert augmented["color"] == "blue"


def test_does_not_override_existing_category():
    state = {"previous_products": [_product("p1", "jackets")]}
    slots = {"category": "shoes", "color": "blue"}
    augmented = _infer_slots_from_memory(slots, state)
    assert augmented["category"] == "shoes"


def test_no_inference_when_no_previous_products():
    state = {"previous_products": []}
    slots = {"color": "blue"}
    augmented = _infer_slots_from_memory(slots, state)
    assert "category" not in augmented


def test_picks_most_common_category_when_mixed():
    state = {
        "previous_products": [
            _product("p1", "jackets"),
            _product("p2", "jackets"),
            _product("p3", "shoes"),
        ]
    }
    augmented = _infer_slots_from_memory({}, state)
    assert augmented["category"] == "jackets"


def test_preserves_other_slots():
    state = {"previous_products": [_product("p1", "jackets")]}
    slots = {"color": "blue", "size": "M", "price_max": 200}
    augmented = _infer_slots_from_memory(slots, state)
    assert augmented["category"] == "jackets"
    assert augmented["color"] == "blue"
    assert augmented["size"] == "M"
    assert augmented["price_max"] == 200
