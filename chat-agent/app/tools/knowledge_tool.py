from __future__ import annotations

from app.clients import BackendClientError

from .base import BaseTool, ToolResult


class KnowledgeTool(BaseTool):
    def retrieve(self, query: str) -> ToolResult:
        try:
            docs = self.client.knowledge_retrieve(query=query)
        except BackendClientError as exc:
            return self.client_error(exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return self.unexpected_error(exc)
        if not docs:
            return ToolResult(status="empty_result", data=[], summary="0 knowledge documents")
        return ToolResult(status="success", data=docs, summary=f"{len(docs)} knowledge documents")
