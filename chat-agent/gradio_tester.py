from __future__ import annotations

import json
import os
import uuid
from typing import Any

import gradio as gr
import httpx


AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "http://localhost:8010").rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("GRADIO_AGENT_TIMEOUT_SECONDS", "20"))


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _parse_context(raw_context: str) -> dict[str, Any]:
    if not raw_context.strip():
        return {}
    parsed = json.loads(raw_context)
    if not isinstance(parsed, dict):
        raise ValueError("pageContext must be a JSON object")
    return parsed


def check_agent_health() -> str:
    try:
        response = httpx.get(f"{AGENT_BASE_URL}/agent/health", timeout=5)
        response.raise_for_status()
        return _pretty_json(response.json())
    except Exception as exc:
        return f"Agent unavailable: {exc}"


def _product_rows(payload: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for card in payload.get("productCards") or []:
        if not isinstance(card, dict):
            continue
        rows.append(
            [
                card.get("name"),
                card.get("productId"),
                card.get("variantId"),
                card.get("slug"),
                card.get("price"),
                card.get("currency"),
                card.get("inStock"),
                ", ".join(str(size) for size in card.get("sizes") or []),
                ", ".join(str(color) for color in card.get("colors") or []),
                card.get("recommendationScore"),
            ]
        )
    return rows


def _tool_rows(payload: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for call in payload.get("toolCalls") or []:
        if not isinstance(call, dict):
            continue
        rows.append(
            [
                call.get("toolName"),
                call.get("status"),
                call.get("latencyMs"),
                call.get("requestSummary") or call.get("input"),
                call.get("responseSummary") or call.get("outputSummary"),
                call.get("error") or call.get("errorMessage"),
            ]
        )
    return rows


def _node_rows(payload: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for node in payload.get("nodeTraces") or []:
        if not isinstance(node, dict):
            continue
        rows.append(
            [
                node.get("nodeName"),
                node.get("status"),
                node.get("latencyMs"),
                node.get("intent"),
                node.get("intentConfidence"),
                node.get("routingConfidence"),
                node.get("outputSummary"),
                node.get("errorMessage"),
            ]
        )
    return rows


def _summary_markdown(payload: dict[str, Any]) -> str:
    draft = payload.get("draftAction") if isinstance(payload.get("draftAction"), dict) else None
    draft_line = "none"
    if draft:
        draft_line = f"{draft.get('actionType')} / {draft.get('status')} / {draft.get('draftActionId')}"
    return "\n".join(
        [
            f"### Response",
            f"- sessionId: `{payload.get('sessionId')}`",
            f"- traceId: `{payload.get('traceId')}`",
            f"- intent: `{payload.get('intent')}`",
            f"- responseType: `{payload.get('responseType')}`",
            f"- fallbackCount: `{payload.get('fallbackCount')}`",
            f"- latencyMs: `{payload.get('latencyMs')}`",
            f"- needsConfirmation: `{payload.get('needsConfirmation')}`",
            f"- draftAction: `{draft_line}`",
        ]
    )


def send_message(
    message: str,
    session_id: str,
    user_id: str,
    authenticated: bool,
    page_context: str,
    trace_id: str,
) -> tuple[str, str, list[list[Any]], list[list[Any]], list[list[Any]], str]:
    if not message.strip():
        raise gr.Error("Message is required")
    resolved_session_id = session_id.strip() or "gradio-demo"
    resolved_trace_id = trace_id.strip() or f"gradio-{uuid.uuid4()}"
    try:
        context = _parse_context(page_context)
    except Exception as exc:
        raise gr.Error(str(exc)) from exc

    payload = {
        "message": message.strip(),
        "sessionId": resolved_session_id,
        "traceId": resolved_trace_id,
        "userId": user_id.strip() or None,
        "authenticated": authenticated,
        "pageContext": context,
    }

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(f"{AGENT_BASE_URL}/agent/chat", json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as exc:
        details = exc.response.text
        raise gr.Error(f"Agent returned {exc.response.status_code}: {details}") from exc
    except Exception as exc:
        raise gr.Error(f"Cannot call chat agent: {exc}") from exc

    return (
        body.get("answer", ""),
        _summary_markdown(body),
        _product_rows(body),
        _tool_rows(body),
        _node_rows(body),
        _pretty_json(body),
    )


def clear_trace() -> str:
    return f"gradio-{uuid.uuid4()}"


with gr.Blocks(title="E-Shop Chat Agent Tester", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# E-Shop Chat Agent Tester")

    with gr.Row():
        health_output = gr.Textbox(label="Agent health", value=check_agent_health(), lines=4)
        refresh_health = gr.Button("Refresh")
        refresh_health.click(check_agent_health, outputs=health_output)

    with gr.Row():
        with gr.Column(scale=2):
            message_input = gr.Textbox(
                label="Message",
                placeholder="ao khoac den size M con hang khong?",
                lines=4,
            )
            page_context_input = gr.Textbox(
                label="pageContext JSON",
                value='{"locale":"vi-VN","page":"gradio-chat-agent"}',
                lines=4,
            )
        with gr.Column(scale=1):
            session_input = gr.Textbox(label="sessionId", value="gradio-demo")
            trace_input = gr.Textbox(label="traceId", value=clear_trace())
            user_input = gr.Textbox(label="userId", value="")
            authenticated_input = gr.Checkbox(label="authenticated", value=False)
            with gr.Row():
                send_button = gr.Button("Send", variant="primary")
                new_trace_button = gr.Button("New trace")

    answer_output = gr.Textbox(label="Answer", lines=5)
    summary_output = gr.Markdown()

    with gr.Tabs():
        with gr.Tab("Products"):
            products_output = gr.Dataframe(
                label="Product cards",
                headers=[
                    "name",
                    "productId",
                    "variantId",
                    "slug",
                    "price",
                    "currency",
                    "inStock",
                    "sizes",
                    "colors",
                    "recommendationScore",
                ],
                wrap=True,
            )
        with gr.Tab("Tool calls"):
            tools_output = gr.Dataframe(
                label="Tool calls",
                headers=["toolName", "status", "latencyMs", "request", "response", "error"],
                wrap=True,
            )
        with gr.Tab("Node traces"):
            nodes_output = gr.Dataframe(
                label="Node traces",
                headers=[
                    "nodeName",
                    "status",
                    "latencyMs",
                    "intent",
                    "intentConfidence",
                    "routingConfidence",
                    "outputSummary",
                    "error",
                ],
                wrap=True,
            )
        with gr.Tab("Raw JSON"):
            raw_output = gr.Code(label="Raw response", language="json", lines=28)

    send_button.click(
        send_message,
        inputs=[
            message_input,
            session_input,
            user_input,
            authenticated_input,
            page_context_input,
            trace_input,
        ],
        outputs=[
            answer_output,
            summary_output,
            products_output,
            tools_output,
            nodes_output,
            raw_output,
        ],
    )
    new_trace_button.click(clear_trace, outputs=trace_input)


if __name__ == "__main__":
    print(f"Chat agent URL: {AGENT_BASE_URL}")
    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("GRADIO_PORT", "7861")), share=False)
