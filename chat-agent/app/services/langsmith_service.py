from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import langsmith as ls


TRUE_VALUES = {"1", "true", "yes", "on"}
DEFAULT_PROJECT = "e-shop-chat-agent"


@contextmanager
def agent_trace_context(
    *,
    trace_id: str,
    request_id: str,
    session_id: str,
    user_id: str | None,
    intent: str,
) -> Iterator[None]:
    tracing_requested = _env_enabled("LANGSMITH_TRACING")
    has_api_key = bool(os.getenv("LANGSMITH_API_KEY"))
    project_name = os.getenv("LANGSMITH_PROJECT") or DEFAULT_PROJECT
    metadata = {
        "traceId": trace_id,
        "requestId": request_id,
        "sessionId": session_id,
        "userId": user_id,
        "intent": intent,
    }
    tags = ["chat-agent", "phase-4", intent]

    with ls.tracing_context(
        project_name=project_name,
        enabled=tracing_requested and has_api_key,
        metadata=metadata,
        tags=tags,
    ):
        yield


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES
