from __future__ import annotations

from app.clients.mock_backend_client import MockBackendClient
from app.graph.workflow import run_agent
from app.schemas import AgentChatRequest
from app.tools.knowledge_tool import KnowledgeTool


def test_knowledge_tool_returns_up_to_three_docs_for_policy_faq_queries() -> None:
    tool = KnowledgeTool(MockBackendClient())

    result = tool.retrieve("returns shipping refund", limit=3)

    assert result.status == "success"
    assert len(result.data) >= 2
    assert len(result.data) <= 3
    source_ids = {doc["sourceId"] for doc in result.data}
    assert "return-refund" in source_ids or "shipping" in source_ids


def test_policy_faq_route_pushes_multiple_grounding_documents() -> None:
    response = run_agent(
        AgentChatRequest(message="return policy and shipping cost", sessionId="rag-quickwin-1")
    )

    knowledge_calls = [t for t in response.tool_calls if t.tool_name == "knowledge.retrieve"]
    assert knowledge_calls, "knowledge.retrieve should be called for policy/FAQ"
    summary = knowledge_calls[0].response_summary
    assert "knowledge documents" in summary
    source_ids_part = [s for s in summary.split(";") if "sourceIds=" in s][0]
    matched_source_count = len(source_ids_part.split("=")[1].split(","))
    assert matched_source_count >= 2


def test_policy_faq_response_includes_structured_citations() -> None:
    response = run_agent(
        AgentChatRequest(message="how do I pay with cash on delivery", sessionId="rag-quickwin-2")
    )

    assert response.response_type == "answer"
    assert response.citations, "response should include at least one citation"
    citation = response.citations[0]
    assert citation.source_id is not None
    assert citation.title
    assert citation.snippet
    assert len(citation.snippet) <= 300


def test_query_rewrite_returns_original_when_llm_disabled(monkeypatch) -> None:
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    from app.services import query_rewrite_service

    rewritten = query_rewrite_service.rewrite_query_with_history(
        message="what about international?",
        last_assistant="We ship to all 63 provinces in Vietnam by Standard or Express.",
        last_intent="policy_or_faq",
    )

    assert rewritten == "what about international?"


def test_query_rewrite_uses_llm_when_enabled() -> None:
    import os
    from unittest.mock import patch

    from app.services import query_rewrite_service

    fake_response_body = {
        "choices": [
            {"message": {"content": "What are the international shipping options and delivery times?"}}
        ]
    }

    class _StubClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            class _Resp:
                def raise_for_status(self_inner):
                    return None

                def json(self_inner):
                    return fake_response_body

            return _Resp()

    with patch.dict(os.environ, {"LLM_ENABLED": "true", "OPENAI_API_KEY": "sk-test"}, clear=False):
        with patch.object(query_rewrite_service.httpx, "Client", _StubClient):
            rewritten = query_rewrite_service.rewrite_query_with_history(
                message="what about international?",
                last_assistant="We ship to all 63 provinces in Vietnam by Standard or Express.",
                last_intent="policy_or_faq",
            )

    assert "international" in rewritten.lower()
    assert "shipping" in rewritten.lower()


def test_rewrite_node_is_noop_when_llm_disabled(monkeypatch) -> None:
    monkeypatch.delenv("LLM_ENABLED", raising=False)

    response = run_agent(
        AgentChatRequest(message="how do I return an item?", sessionId="rag-quickwin-3")
    )

    node_names = [n.node_name for n in response.node_traces]
    assert "rewrite_query_for_retrieval" in node_names
    assert response.response_type == "answer"


def test_grounding_check_returns_true_when_llm_disabled(monkeypatch) -> None:
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    from app.services import grounding_check_service

    grounded, reason = grounding_check_service.is_answer_grounded(
        answer="Standard delivery takes 3 to 5 business days within Vietnam.",
        grounding_documents=[{"sourceId": "shipping", "body": "Standard. 3 to 5 business days within Vietnam."}],
    )

    assert grounded is True
    assert reason is None


def test_grounding_check_flags_ungrounded_claim() -> None:
    import os as _os
    from unittest.mock import patch

    from app.services import grounding_check_service

    fake_response_body = {
        "choices": [
            {"message": {"content": "UNGROUNDED: claim about free lifetime warranty is not in the documents."}}
        ]
    }

    class _StubClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            class _Resp:
                def raise_for_status(self_inner):
                    return None

                def json(self_inner):
                    return fake_response_body

            return _Resp()

    with patch.dict(_os.environ, {"LLM_ENABLED": "true", "OPENAI_API_KEY": "sk-test"}, clear=False):
        with patch.object(grounding_check_service.httpx, "Client", _StubClient):
            grounded, reason = grounding_check_service.is_answer_grounded(
                answer="We offer a free lifetime warranty on all jackets.",
                grounding_documents=[{"sourceId": "return-refund", "body": "Returns accepted within 30 days."}],
            )

    assert grounded is False
    assert reason and "warranty" in reason.lower()


def test_policy_faq_empty_result_lists_available_topics() -> None:
    response = run_agent(
        AgentChatRequest(
            message="policy on cosmic radiation during commute",
            sessionId="rag-quickwin-4",
        )
    )

    assert response.intent == "policy_or_faq"
    assert response.response_type == "empty_result"
    assert "Try one of" in response.answer
    candidates = [
        "Shipping Policy",
        "Return and Refund Policy",
        "Payment",
        "Size Guide",
        "Account",
        "Order",
        "Product",
    ]
    matches = [c for c in candidates if c in response.answer]
    assert len(matches) >= 3
