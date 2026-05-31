from __future__ import annotations

import logging
import time
from typing import Any, Callable

from app.clients import BackendClientError
from app.schemas import ToolCallTrace
from app.services.logging_service import log_event
from app.services.metrics_service import metrics_service
from app.services.redaction_service import redact
from app.tools.base import ToolResult


logger = logging.getLogger("chat_agent")


def call_tool(
    existing: list[ToolCallTrace],
    tool_name: str,
    tool_input: dict[str, Any],
    call: Callable[[], ToolResult],
    trace_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
) -> tuple[ToolResult, list[ToolCallTrace]]:
    start = time.perf_counter()
    try:
        result = call()
        status = result.status
        summary = result.summary
        error = result.error
        error_class = None
    except BackendClientError as exc:
        result = ToolResult(status=exc.status, data=None, summary="backend client error", error=str(exc))
        status = result.status
        summary = result.summary
        error = result.error
        error_class = exc.__class__.__name__
    except Exception as exc:  # pragma: no cover - defensive fallback path
        result = ToolResult(status="backend_error", data=None, summary="tool failed", error=exc.__class__.__name__)
        status = result.status
        summary = result.summary
        error = result.error
        error_class = exc.__class__.__name__

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    redacted_error = redact(error) if error else None
    redacted_summary = redact(summary)
    trace = ToolCallTrace(
        toolName=tool_name,
        status=status,
        latencyMs=latency_ms,
        traceId=trace_id,
        input=redact(tool_input),
        requestSummary=_summarize_request(tool_input),
        responseSummary=redacted_summary,
        outputSummary=redacted_summary,
        error=redacted_error,
        errorClass=error_class,
        errorMessage=redacted_error,
    )
    metrics_service.observe("agent_tool_latency_ms", latency_ms, {"tool": tool_name, "status": status})
    if status != "success":
        metrics_service.increment("agent_tool_error_total", {"tool": tool_name, "status": status})
    log_event(
        "agent_tool",
        traceId=trace_id,
        sessionId=session_id,
        userId=user_id,
        toolName=tool_name,
        status=status,
        latencyMs=latency_ms,
        errorClass=error_class,
        errorMessage=redacted_error,
    )
    return result, [*existing, trace]


def _summarize_request(tool_input: dict[str, Any]) -> str:
    if not tool_input:
        return ""
    keys = ", ".join(sorted(redact(tool_input)))
    return f"{len(tool_input)} fields: {keys}"
