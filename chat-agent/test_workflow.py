from workflow import run_chat


def test_product_search_flow():
    state = run_chat("ao size M mau den con hang khong?", session_id="test-product")

    assert state["intent"] == "product_search"
    assert state["products"]
    assert "Here are matching products" in state["answer"]
    assert state["trace"][-1] == "answer"


def test_order_status_flow_needs_order_code():
    state = run_chat("check my order", session_id="test-order-missing")

    assert state["intent"] == "order_status"
    assert state["order"] is None
    assert "order code" in state["answer"]


def test_order_status_flow_with_order_code():
    state = run_chat("check order ES123", session_id="test-order")

    assert state["intent"] == "order_status"
    assert state["order"]["status"] == "SHIPPED"
    assert "ES123" in state["answer"]
