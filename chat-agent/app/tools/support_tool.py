from __future__ import annotations

from app.services import DraftService, draft_service

from .base import BaseTool, ToolResult


class SupportTool(BaseTool):
    def __init__(self, client, drafts: DraftService | None = None) -> None:
        super().__init__(client)
        self.drafts = drafts or draft_service

    def create_draft(self, summary: str, transcript: list[dict]) -> ToolResult:
        draft = self.drafts.create_draft_action(
            "support.handoff",
            {"summary": summary, "transcript": transcript},
        )
        return ToolResult(status="success", data=draft, summary="support.handoff draft")
