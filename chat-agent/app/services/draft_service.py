from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.schemas import DraftAction, DraftActionType


class DraftService:
    def __init__(self, ttl_minutes: int = 15) -> None:
        self.ttl_minutes = ttl_minutes
        self._drafts: dict[str, DraftAction] = {}

    def create_draft_action(self, action_type: DraftActionType, payload: dict) -> DraftAction:
        draft = DraftAction(
            draftActionId=f"draft_{uuid4().hex}",
            actionType=action_type,
            payload=payload,
            status="pending",
            expiresAt=datetime.now(UTC) + timedelta(minutes=self.ttl_minutes),
            needsConfirmation=True,
        )
        self._drafts[draft.draft_action_id] = draft
        return draft

    def expire_draft_action(self, draft_action_id: str) -> DraftAction | None:
        draft = self._drafts.get(draft_action_id)
        if draft and draft.status == "pending":
            draft.status = "expired"
        return draft

    def complete_draft_action(self, draft_action_id: str) -> DraftAction | None:
        draft = self._drafts.get(draft_action_id)
        if draft and self.validate_draft_action(draft_action_id):
            draft.status = "completed"
        return draft

    def cancel_draft_action(self, draft_action_id: str) -> DraftAction | None:
        draft = self._drafts.get(draft_action_id)
        if draft and draft.status == "pending":
            draft.status = "cancelled"
        return draft

    def fail_draft_action(self, draft_action_id: str) -> DraftAction | None:
        draft = self._drafts.get(draft_action_id)
        if draft and draft.status == "pending":
            draft.status = "failed"
        return draft

    def validate_draft_action(self, draft_action_id: str) -> bool:
        draft = self._drafts.get(draft_action_id)
        if not draft or draft.status != "pending":
            return False
        if draft.expires_at <= datetime.now(UTC):
            draft.status = "expired"
            return False
        return True


draft_service = DraftService()
