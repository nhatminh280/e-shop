from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.draft_service import DraftService


def test_draft_expiration() -> None:
    service = DraftService(ttl_minutes=15)
    draft = service.create_draft_action("cart.add", {"productId": "p001", "quantity": 1})

    assert service.validate_draft_action(draft.draft_action_id) is True
    draft.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    assert service.validate_draft_action(draft.draft_action_id) is False
    assert draft.status == "expired"


def test_draft_cancel_and_complete() -> None:
    service = DraftService(ttl_minutes=15)
    cancelled = service.create_draft_action("cart.remove_item", {"productId": "p001"})
    completed = service.create_draft_action("support.handoff", {"summary": "help"})

    assert service.cancel_draft_action(cancelled.draft_action_id).status == "cancelled"
    assert service.validate_draft_action(cancelled.draft_action_id) is False

    assert service.complete_draft_action(completed.draft_action_id).status == "completed"
    assert service.validate_draft_action(completed.draft_action_id) is False


def test_draft_fail() -> None:
    service = DraftService(ttl_minutes=15)
    draft = service.create_draft_action("cart.update_quantity", {"productId": "p001", "quantity": 2})

    assert service.fail_draft_action(draft.draft_action_id).status == "failed"
    assert service.validate_draft_action(draft.draft_action_id) is False
