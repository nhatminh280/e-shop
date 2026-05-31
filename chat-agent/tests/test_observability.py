from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from typing import Any

import httpx

import app.graph.nodes as graph_nodes
import app.graph.workflow as workflow
from app.clients import BackendClientError
from app.clients.spring_client import SpringBackendClient
from app.main import chat, metrics
from app.schemas import AgentChatRequest
from app.services.env_service import load_local_env
from app.services import langsmith_service
from app.services.logging_service import JsonFormatter
from app.services.metrics_service import metrics_service
from app.services.node_trace_service import trace_node
from app.services.redaction_service import REDACTED, redact
from app.services.trace_service import call_tool
from app.services.trace_context_service import reset_trace_context, set_trace_context
from app.tools.base import ToolResult


def test_incoming_trace_id_is_reused_and_propagated_to_traces() -> None:
    trace_id = "trace-from-backend"
    response = chat(AgentChatRequest(sessionId="trace-session", traceId=trace_id, message="ao khoac den size M"))
    body = response.model_dump(by_alias=True)

    assert body["traceId"] == trace_id
    assert body["nodeTraces"]
    assert {"nodeName", "status", "latencyMs", "intent", "inputSummary", "outputSummary"} <= set(body["nodeTraces"][0])
    assert body["nodeTraces"][3]["intent"] == "product_search"
    assert body["toolCalls"]
    assert body["toolCalls"][0]["traceId"] == trace_id


def test_response_includes_confidence_and_review_flags() -> None:
    strong = chat(AgentChatRequest(sessionId="confidence-strong", message="ao khoac den size M"))
    strong_body = strong.model_dump(by_alias=True)

    assert strong_body["intentConfidence"] >= 0.8
    assert strong_body["routingConfidence"] >= 0.8
    assert strong_body["needsReview"] is False
    assert strong_body["nodeTraces"][3]["intentConfidence"] >= 0.8

    weak = chat(AgentChatRequest(sessionId="confidence-weak", message="hello"))
    weak_body = weak.model_dump(by_alias=True)

    assert weak_body["intent"] == "general"
    assert weak_body["intentConfidence"] < 0.7
    assert weak_body["routingConfidence"] < 0.7
    assert weak_body["needsReview"] is True


def test_metrics_endpoint_is_prometheus_compatible() -> None:
    metrics_service.reset()
    chat(AgentChatRequest(sessionId="metrics-session", message="ao khoac den size M"))

    response = metrics()
    body = response.body.decode()

    assert response.media_type == "text/plain; version=0.0.4"
    assert "# HELP agent_request_total" in body
    assert "# TYPE agent_request_total counter" in body
    assert "# TYPE agent_latency_ms summary" in body
    assert "agent_request_total" in body
    assert "agent_latency_ms_count" in body
    assert "agent_node_latency_ms_count" in body
    assert "agent_tool_latency_ms_count" in body
    assert "agent_intent_total" in body
    assert "agent_response_type_total" in body


def test_metrics_escape_labels_and_validate_names() -> None:
    metrics_service.reset()
    metrics_service.increment("agent_request_total", {"path": '/chat/"quoted"\nline\\slash'})

    body = metrics().body.decode()

    assert 'path="/chat/\\"quoted\\"\\nline\\\\slash"' in body

    try:
        metrics_service.increment("invalid metric name")
    except ValueError as exc:
        assert "invalid metric name" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("invalid metric name should fail")


def test_metrics_allow_same_name_with_different_label_sets() -> None:
    metrics_service.reset()

    metrics_service.increment("agent_request_total", {"intent": "product_search", "response_type": "product_results"})
    metrics_service.increment("agent_request_total", {"path": "/agent/chat"})

    body = metrics().body.decode()

    assert 'agent_request_total{intent="product_search",response_type="product_results"} 1.0' in body
    assert 'agent_request_by_path_total{path="/agent/chat"} 1.0' in body


def test_chat_flow_records_fallback_tool_error_and_draft_metrics(monkeypatch) -> None:
    metrics_service.reset()

    empty_response = chat(AgentChatRequest(sessionId="metrics-empty-result", message="giay nam duoi 500k"))
    assert empty_response.response_type == "empty_result"

    cart_response = chat(AgentChatRequest(sessionId="metrics-cart-draft", message="add jacket size M to cart"))
    assert cart_response.response_type == "draft_action"

    class TimeoutCatalog:
        def search(self, query, filters=None):
            raise BackendClientError("timeout", status="timeout")

    monkeypatch.setattr(graph_nodes.tools, "catalog", TimeoutCatalog())
    timeout_response = chat(AgentChatRequest(sessionId="metrics-timeout", message="ao den size M"))
    assert timeout_response.response_type == "tool_error"

    body = metrics().body.decode()

    assert 'agent_fallback_total{intent="product_search"} 2.0' in body
    assert 'agent_draft_action_total{action_type="cart.add"} 1.0' in body
    assert 'agent_tool_error_total{status="timeout",tool="catalog.search"} 1.0' in body
    assert 'agent_node_latency_ms_count{node="classify_intent",status="success"}' in body
    assert 'agent_tool_latency_ms_count{status="timeout",tool="catalog.search"}' in body


def test_redaction_removes_sensitive_fields_and_patterns() -> None:
    payload = {
        "Authorization": "Bearer secret-token",
        "x-api-key": "api-key-value",
        "password": "123456",
        "phone": "0912345678",
        "cardNumber": "4111 1111 1111 1111",
        "nested": {
            "email": "customer@example.com",
            "message": (
                "call me at 0912345678 with jwt "
                "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature "
                "and token=abc123"
            ),
        },
    }

    redacted = redact(payload)

    assert redacted["Authorization"] == REDACTED
    assert redacted["x-api-key"] == REDACTED
    assert redacted["password"] == REDACTED
    assert redacted["phone"] == REDACTED
    assert redacted["cardNumber"] == REDACTED
    assert redacted["nested"]["email"] == REDACTED
    assert REDACTED in redacted["nested"]["message"]
    assert "eyJ" not in redacted["nested"]["message"]
    assert "token=abc123" not in redacted["nested"]["message"]


def test_redaction_preserves_non_sensitive_trace_ids_and_numbers() -> None:
    payload = {
        "traceId": "trace-123",
        "requestId": "req-456",
        "orderNumber": "ES123",
        "message": "reference 1234567890123 is not a valid card",
    }

    assert redact(payload) == payload


def test_json_formatter_outputs_redacted_json() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="chat_agent",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="agent_request",
        args=(),
        exc_info=None,
    )
    record.traceId = "trace-1"
    record.sessionId = "session-1"
    record.userId = "user-1"
    record.toolName = "catalog.search"
    record.errorClass = "BackendClientError"
    record.errorMessage = "customer@example.com timed out"
    record.Authorization = "Bearer secret-token"

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "agent_request"
    assert payload["traceId"] == "trace-1"
    assert payload["trace_id"] == "trace-1"
    assert payload["sessionId"] == "session-1"
    assert payload["session_id"] == "session-1"
    assert payload["userId"] == "user-1"
    assert payload["user_id"] == "user-1"
    assert payload["toolName"] == "catalog.search"
    assert payload["tool_name"] == "catalog.search"
    assert payload["errorClass"] == "BackendClientError"
    assert payload["error_class"] == "BackendClientError"
    assert payload["errorMessage"] == f"{REDACTED} timed out"
    assert payload["error_message"] == f"{REDACTED} timed out"
    assert payload["Authorization"] == REDACTED


def test_load_local_env_reads_dotenv_without_overriding_runtime_env(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LANGSMITH_TRACING=true",
                "LANGSMITH_PROJECT=file-project",
                "LANGSMITH_API_KEY=file-key",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.setenv("LANGSMITH_PROJECT", "runtime-project")

    loaded = load_local_env(tmp_path)

    assert loaded is True
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "file-key"
    assert os.environ["LANGSMITH_PROJECT"] == "runtime-project"


def test_spring_client_forwards_trace_headers(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def request(self, method, url, params=None, json=None, headers=None):
            captured["method"] = method
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            return httpx.Response(200, json={"products": []}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "Client", FakeClient)
    token = set_trace_context(
        trace_id="trace-123",
        request_id="req-123",
        session_id="session-123",
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    )
    try:
        SpringBackendClient(base_url="http://backend", timeout_seconds=1, retries=0).catalog_search("shirt")
    finally:
        reset_trace_context(token)

    assert captured["headers"]["x-agent-client"] == "chat-agent"
    assert captured["headers"]["x-trace-id"] == "trace-123"
    assert captured["headers"]["x-request-id"] == "req-123"
    assert captured["headers"]["x-session-id"] == "session-123"
    assert captured["headers"]["traceparent"].startswith("00-")


def test_langsmith_trace_context_is_disabled_without_api_key(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    @contextmanager
    def fake_tracing_context(**kwargs):
        captured.update(kwargs)
        yield

    monkeypatch.setattr(langsmith_service.ls, "tracing_context", fake_tracing_context)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.setenv("LANGSMITH_PROJECT", "phase-4-test")

    with langsmith_service.agent_trace_context(
        trace_id="trace-langsmith-disabled",
        request_id="req-langsmith-disabled",
        session_id="session-langsmith-disabled",
        user_id="user-1",
        intent="product_search",
    ):
        pass

    assert captured["enabled"] is False
    assert captured["project_name"] == "phase-4-test"
    assert captured["metadata"]["traceId"] == "trace-langsmith-disabled"
    assert captured["metadata"]["requestId"] == "req-langsmith-disabled"
    assert captured["metadata"]["sessionId"] == "session-langsmith-disabled"
    assert captured["metadata"]["userId"] == "user-1"
    assert captured["metadata"]["intent"] == "product_search"
    assert "chat-agent" in captured["tags"]


def test_workflow_invocation_is_wrapped_in_langsmith_context(monkeypatch) -> None:
    metrics_service.reset()
    captured: dict[str, Any] = {}

    @contextmanager
    def fake_agent_trace_context(**kwargs):
        captured.update(kwargs)
        yield

    monkeypatch.setattr(workflow, "agent_trace_context", fake_agent_trace_context)

    response = chat(
        AgentChatRequest(
            sessionId="langsmith-workflow-session",
            traceId="trace-langsmith-workflow",
            requestId="req-langsmith-workflow",
            userId="user-1",
            message="ao khoac den size M",
        )
    )

    assert response.trace_id == "trace-langsmith-workflow"
    assert captured == {
        "trace_id": "trace-langsmith-workflow",
        "request_id": "req-langsmith-workflow",
        "session_id": "langsmith-workflow-session",
        "user_id": "user-1",
        "intent": "agent_chat",
    }


def test_tool_error_trace_includes_error_class_and_redacted_message() -> None:
    def failing_tool() -> ToolResult:
        raise BackendClientError("customer@example.com token=abc123 timed out", status="timeout")

    result, traces = call_tool(
        [],
        "catalog.search",
        {"Authorization": "Bearer secret-token", "query": "shirt"},
        failing_tool,
        trace_id="trace-tool-error",
        session_id="session-tool-error",
        user_id="user-1",
    )

    body = traces[0].model_dump(by_alias=True)

    assert result.status == "timeout"
    assert body["status"] == "timeout"
    assert body["errorClass"] == "BackendClientError"
    assert body["errorMessage"] == f"{REDACTED} token={REDACTED} timed out"
    assert body["input"]["Authorization"] == REDACTED
    assert "customer@example.com" not in body["errorMessage"]
    assert "abc123" not in body["errorMessage"]


def test_node_error_trace_includes_error_class_and_redacted_message(monkeypatch) -> None:
    captured = []

    def capture_node_trace(state, trace):
        captured.append(trace)

    def failing_node(state):
        raise RuntimeError("failed for phone 0912345678 and email customer@example.com")

    monkeypatch.setattr("app.services.node_trace_service._record_node", capture_node_trace)
    wrapped = trace_node("failing_node", failing_node)

    try:
        wrapped({"trace_id": "trace-node-error", "session_id": "session-node-error", "message": "hello"})
    except RuntimeError:
        pass
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("node failure should be re-raised")

    body = captured[0].model_dump(by_alias=True)

    assert body["nodeName"] == "failing_node"
    assert body["status"] == "error"
    assert body["errorClass"] == "RuntimeError"
    assert body["errorMessage"] == f"failed for phone {REDACTED} and email {REDACTED}"
    assert "0912345678" not in body["errorMessage"]
    assert "customer@example.com" not in body["errorMessage"]
