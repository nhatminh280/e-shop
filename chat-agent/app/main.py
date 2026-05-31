from __future__ import annotations

from fastapi import FastAPI, Request, Response

from app.graph import run_agent
from app.schemas import AgentChatRequest, AgentChatResponse
from app.services.env_service import load_local_env
from app.services.logging_service import configure_logging
from app.services.metrics_service import metrics_service


load_local_env()
configure_logging()
app = FastAPI(title="E-Shop AI Chat Agent", version="0.1.0")


@app.get("/agent/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "chat-agent"}


@app.get("/agent/metrics")
def metrics() -> Response:
    return Response(content=metrics_service.render_prometheus(), media_type="text/plain; version=0.0.4")


def chat(request: AgentChatRequest) -> AgentChatResponse:
    return run_agent(request)


@app.post("/agent/chat", response_model=AgentChatResponse, response_model_by_alias=True)
def chat_endpoint(request: AgentChatRequest, http_request: Request) -> AgentChatResponse:
    request.trace_id = request.trace_id or http_request.headers.get("x-trace-id")
    request.request_id = request.request_id or http_request.headers.get("x-request-id")
    request.traceparent = request.traceparent or http_request.headers.get("traceparent")
    request.session_id = request.session_id or http_request.headers.get("x-session-id") or request.session_id
    return run_agent(request)
