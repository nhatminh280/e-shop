from __future__ import annotations

from app.clients import MockBackendClient
from app.schemas import KnowledgeSearchResult
from app.tools.knowledge_tool import KnowledgeTool, _is_confident_match


class VectorKnowledgeClient:
    def knowledge_retrieve(self, query: str, limit: int = 2) -> list[dict]:
        return [
            {
                "sourceId": "shipping",
                "sourceType": "shipping",
                "title": "Shipping Policy",
                "locale": "en-US",
                "body": "Standard domestic delivery is available for eligible orders.",
                "score": 0.82,
                "scoreType": "vector",
            }
        ]


class InvalidKnowledgeClient:
    def knowledge_retrieve(self, query: str, limit: int = 2) -> list[dict]:
        return [{"title": "Shipping Policy"}]


def test_knowledge_search_result_accepts_vector_metadata() -> None:
    result = KnowledgeSearchResult(
        sourceId="shipping",
        sourceType="shipping",
        title="Shipping Policy",
        locale="en-US",
        body="Standard domestic delivery is available for eligible orders.",
        score=0.82,
        scoreType="vector",
    )

    body = result.model_dump(by_alias=True)
    assert body["sourceId"] == "shipping"
    assert body["score"] == 0.82
    assert body["scoreType"] == "vector"
    assert body["matchedTokenCount"] == 0
    assert body["matchedTokens"] == []


def test_mock_knowledge_retrieves_markdown_payment_document() -> None:
    result = KnowledgeTool(MockBackendClient()).retrieve("cash on delivery payment")

    assert result.status == "success"
    assert result.data[0]["sourceId"] == "payment"
    assert result.data[0]["sourceType"] == "payment"
    assert result.data[0]["title"] == "Payment Methods and Policy"
    assert "Cash on Delivery" in result.data[0]["body"]


def test_mock_knowledge_retrieves_markdown_account_document() -> None:
    result = KnowledgeTool(MockBackendClient()).retrieve("password reset link expired")

    assert result.status == "success"
    assert result.data[0]["sourceId"] == "faq-account"
    assert result.data[0]["sourceType"] == "faq_account"
    assert "reset link valid for 30 minutes" in result.data[0]["body"]


def test_one_word_policy_queries_pass_confidence_filter() -> None:
    client = MockBackendClient()

    assert KnowledgeTool(client).retrieve("shipping").status == "success"
    assert KnowledgeTool(client).retrieve("payment").status == "success"
    assert KnowledgeTool(client).retrieve("account").status == "success"


def test_mock_knowledge_empty_result_when_no_markdown_doc_matches() -> None:
    result = KnowledgeTool(MockBackendClient()).retrieve("warranty carbon bicycle frame")

    assert result.status == "empty_result"
    assert result.data == []


def test_mock_knowledge_results_include_keyword_retrieval_metadata() -> None:
    result = KnowledgeTool(MockBackendClient()).retrieve("shipping fees standard domestic")

    assert result.status == "success"
    assert result.data[0]["sourceId"] == "shipping"
    assert result.data[0]["scoreType"] == "hybrid"
    assert isinstance(result.data[0]["score"], float)
    assert result.data[0]["matchedTokenCount"] >= 2
    assert "shipping" in result.data[0]["matchedTokens"]


def test_mock_knowledge_retrieves_product_material_and_care_knowledge() -> None:
    result = KnowledgeTool(MockBackendClient()).retrieve("torrentshell jacket waterproof care")

    assert result.status == "success"
    assert result.data[0]["sourceId"] == "product-p003"
    assert result.data[0]["sourceType"] == "product"
    assert result.data[0]["scoreType"] == "hybrid"
    assert "Patagonia Torrentshell 3L Jacket" in result.data[0]["body"]


def test_vector_knowledge_payload_passes_confidence_threshold() -> None:
    result = KnowledgeTool(VectorKnowledgeClient()).retrieve("shipping policy")

    assert result.status == "success"
    assert result.data[0]["sourceId"] == "shipping"
    assert result.data[0]["score"] == 0.82
    assert result.data[0]["scoreType"] == "vector"
    assert "sourceIds=shipping" in result.summary
    assert "scoreTypes=vector" in result.summary


def test_invalid_knowledge_payload_returns_validation_error() -> None:
    result = KnowledgeTool(InvalidKnowledgeClient()).retrieve("shipping policy")

    assert result.status == "validation_error"
    assert result.data == []


def test_confidence_fallback_accepts_float_scores_without_token_metadata() -> None:
    assert _is_confident_match({"score": 0.8, "scoreType": "keyword"}) is True
