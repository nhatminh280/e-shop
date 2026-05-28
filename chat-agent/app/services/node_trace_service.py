from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.graph.state import GraphState
from app.schemas import NodeTrace
from app.services.logging_service import log_event
from app.services.metrics_service import metrics_service
from app.services.redaction_service import redact


def trace_node(node_name: str, node: Callable[[GraphState], dict[str, Any]]) -> Callable[[GraphState], dict[str, Any]]:
    def wrapped(state: GraphState) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            output = node(state)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            trace = NodeTrace(
                nodeName=node_name,
                status="success",
                latencyMs=latency_ms,
                intent=output.get("intent", state.get("intent", "general")),
                inputSummary=_summarize_state(state),
                outputSummary=_summarize_output(output),
                intentConfidence=output.get("intent_confidence", state.get("intent_confidence")),
                routingConfidence=output.get("routing_confidence", state.get("routing_confidence")),
            )
            output["node_trace"] = [*output.get("node_trace", state.get("node_trace", [])), trace]
            _record_node(state, trace)
            return output
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            trace = NodeTrace(
                nodeName=node_name,
                status="error",
                latencyMs=latency_ms,
                intent=state.get("intent", "general"),
                inputSummary=_summarize_state(state),
                outputSummary="",
                errorClass=exc.__class__.__name__,
                errorMessage=redact(str(exc)),
            )
            _record_node(state, trace)
            raise

    return wrapped


def _record_node(state: GraphState, trace: NodeTrace) -> None:
    metrics_service.observe("agent_node_latency_ms", trace.latency_ms, {"node": trace.node_name, "status": trace.status})
    log_event(
        "agent_node",
        traceId=state.get("trace_id"),
        sessionId=state.get("session_id"),
        userId=state.get("user_id"),
        node=trace.node_name,
        status=trace.status,
        intent=trace.intent,
        intentConfidence=trace.intent_confidence,
        routingConfidence=trace.routing_confidence,
        latencyMs=trace.latency_ms,
        errorClass=trace.error_class,
        errorMessage=trace.error_message,
    )


def _summarize_state(state: GraphState) -> str:
    summary = {
        "messageLength": len(state.get("message", "")),
        "intent": state.get("intent"),
        "intentConfidence": state.get("intent_confidence"),
        "routingConfidence": state.get("routing_confidence"),
        "route": state.get("route"),
        "slots": sorted(state.get("slots", {}).keys()),
        "toolCalls": len(state.get("tool_calls", [])),
    }
    return str(redact(summary))


def _summarize_output(output: dict[str, Any]) -> str:
    summary = {
        "keys": sorted(output.keys()),
        "intent": output.get("intent"),
        "intentConfidence": output.get("intent_confidence"),
        "routingConfidence": output.get("routing_confidence"),
        "needsReview": output.get("needs_review"),
        "responseType": output.get("response_type"),
        "toolCalls": len(output.get("tool_calls", [])),
        "fallbackCount": output.get("fallback_count"),
    }
    return str(redact(summary))
