from __future__ import annotations

from fastapi import FastAPI, Request, Response

from app.graph import run_agent
from app.schemas import AgentChatRequest, AgentChatResponse
from app.services import response_cache
from app.services.env_service import load_local_env
from app.services.logging_service import configure_logging, log_event
from app.services.metrics_service import metrics_service
from app.services.trace_context_service import reset_auth_token, set_auth_token


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

    # Serve from response cache for stable FAQ/general/handoff queries — same
    # message returns the same answer, so we skip the whole graph (retrieval +
    # LLM synthesis + LLM grounding) and answer in <10ms.
    cached_payload = response_cache.get(request.message, request.authenticated)
    if cached_payload is not None:
        cached_response = AgentChatResponse.model_validate(cached_payload)
        # Rebind per-request identifiers so the cached body looks fresh.
        cached_response.session_id = request.session_id
        if request.trace_id:
            cached_response.trace_id = request.trace_id
        log_event(
            "response_cache_hit",
            sessionId=request.session_id,
            intent=cached_response.intent,
        )
        return cached_response

    # Forward the storefront's Authorization header to backend tool calls
    # (catalog / order / cart) so chat-agent acts on behalf of the signed-in user.
    bearer = http_request.headers.get("Authorization") or ""
    token_value = bearer.split(" ", 1)[1].strip() if bearer.lower().startswith("bearer ") else None
    auth_handle = set_auth_token(token_value)
    try:
        result = run_agent(request)
    finally:
        reset_auth_token(auth_handle)

    # Only cache "clean" answers — skip when needs_review (grounding flagged
    # or LLM failed) so we don't keep serving a flawed reply.
    if not result.needs_review:
        response_cache.put(
            message=request.message,
            intent=result.intent,
            response=result.model_dump(by_alias=False),
            authenticated=request.authenticated,
        )
    return result
