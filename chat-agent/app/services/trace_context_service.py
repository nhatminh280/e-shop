from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any


_trace_context: ContextVar[dict[str, str]] = ContextVar("trace_context", default={})
_auth_token: ContextVar[str | None] = ContextVar("auth_token", default=None)


def set_auth_token(token: str | None) -> Token[str | None]:
    return _auth_token.set(token)


def reset_auth_token(token: Token[str | None]) -> None:
    _auth_token.reset(token)


def get_auth_token() -> str | None:
    return _auth_token.get()


def set_trace_context(
    *,
    trace_id: str,
    session_id: str,
    request_id: str | None = None,
    traceparent: str | None = None,
) -> Token[dict[str, str]]:
    context = {
        "traceId": trace_id,
        "sessionId": session_id,
    }
    if request_id:
        context["requestId"] = request_id
    if traceparent:
        context["traceparent"] = traceparent
    return _trace_context.set(context)


def reset_trace_context(token: Token[dict[str, str]]) -> None:
    _trace_context.reset(token)


def get_trace_headers() -> dict[str, str]:
    context = _trace_context.get()
    headers: dict[str, str] = {}
    if context.get("traceId"):
        headers["x-trace-id"] = context["traceId"]
    if context.get("requestId"):
        headers["x-request-id"] = context["requestId"]
    if context.get("sessionId"):
        headers["x-session-id"] = context["sessionId"]
    if context.get("traceparent"):
        headers["traceparent"] = context["traceparent"]
    return headers


def get_trace_context() -> dict[str, Any]:
    return dict(_trace_context.get())
