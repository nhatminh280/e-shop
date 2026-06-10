from __future__ import annotations

from app.clients import BackendClientError
from app.schemas import KnowledgeSearchResult
from pydantic import ValidationError

from .base import BaseTool, ToolResult


MIN_KNOWLEDGE_MATCHED_TOKENS = 1
MIN_VECTOR_SCORE = 0.7
MIN_HYBRID_SCORE = 0.7


class KnowledgeTool(BaseTool):
    def retrieve(self, query: str) -> ToolResult:
        try:
            docs = self.client.knowledge_retrieve(query=query)
        except BackendClientError as exc:
            return self.client_error(exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self.unexpected_error(exc)
        try:
            docs = _normalize_docs(docs)
        except ValidationError as exc:
            return ToolResult(status="validation_error", data=[], summary="invalid knowledge document", error=str(exc))
        docs = [doc for doc in docs if _is_confident_match(doc)]
        if not docs:
            return ToolResult(status="empty_result", data=[], summary="0 knowledge documents: low confidence")
        return ToolResult(status="success", data=docs, summary=_summarize_sources(docs))


def _normalize_docs(docs: list[dict]) -> list[dict]:
    return [KnowledgeSearchResult.model_validate(doc).model_dump(by_alias=True) for doc in docs]


def _is_confident_match(doc: dict) -> bool:
    if doc.get("scoreType") == "vector":
        return float(doc.get("score") or 0) >= MIN_VECTOR_SCORE
    if doc.get("scoreType") == "hybrid":
        return float(doc.get("score") or 0) >= MIN_HYBRID_SCORE
    if "matchedTokenCount" in doc:
        return int(doc.get("matchedTokenCount") or 0) >= MIN_KNOWLEDGE_MATCHED_TOKENS
    return float(doc.get("score") or 0) >= MIN_HYBRID_SCORE


def _summarize_sources(docs: list[dict]) -> str:
    source_ids = ",".join(str(doc.get("sourceId", "unknown")) for doc in docs)
    scores = ",".join(str(doc.get("score", "unknown")) for doc in docs)
    score_types = ",".join(str(doc.get("scoreType", "unknown")) for doc in docs)
    return f"{len(docs)} knowledge documents; sourceIds={source_ids}; scores={scores}; scoreTypes={score_types}"
