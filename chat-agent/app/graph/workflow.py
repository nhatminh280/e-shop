from __future__ import annotations

import time
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    build_clarification_response,
    classify_intent,
    extract_slots,
    format_structured_response,
    ground_response_in_tool_results,
    input_guardrails,
    load_session_context,
    normalize_message,
    output_guardrails,
    refine_grounded_answer_with_llm,
    route_intent,
)
from app.graph.state import GraphState
from app.schemas import AgentChatRequest, AgentChatResponse
from app.services import memory_service
from app.services.langsmith_service import agent_trace_context
from app.services.logging_service import log_event
from app.services.metrics_service import metrics_service
from app.services.node_trace_service import trace_node
from app.services.trace_context_service import reset_trace_context, set_trace_context


def _next_after_route(state: GraphState) -> str:
    return "clarification" if state.get("route") == "clarification" else "tool"


def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("load_session_context", trace_node("load_session_context", load_session_context))
    builder.add_node("normalize_message", trace_node("normalize_message", normalize_message))
    builder.add_node("input_guardrails", trace_node("input_guardrails", input_guardrails))
    builder.add_node("classify_intent", trace_node("classify_intent", classify_intent))
    builder.add_node("extract_slots", trace_node("extract_slots", extract_slots))
    builder.add_node("route_intent", trace_node("route_intent", route_intent))
    builder.add_node("build_clarification_response", trace_node("build_clarification_response", build_clarification_response))
    builder.add_node("ground_response_in_tool_results", trace_node("ground_response_in_tool_results", ground_response_in_tool_results))
    builder.add_node("refine_grounded_answer_with_llm", trace_node("refine_grounded_answer_with_llm", refine_grounded_answer_with_llm))
    builder.add_node("output_guardrails", trace_node("output_guardrails", output_guardrails))
    builder.add_node("format_structured_response", trace_node("format_structured_response", format_structured_response))

    builder.add_edge(START, "load_session_context")
    builder.add_edge("load_session_context", "normalize_message")
    builder.add_edge("normalize_message", "input_guardrails")
    builder.add_edge("input_guardrails", "classify_intent")
    builder.add_edge("classify_intent", "extract_slots")
    builder.add_edge("extract_slots", "route_intent")
    builder.add_conditional_edges(
        "route_intent",
        _next_after_route,
        {
            "clarification": "build_clarification_response",
            "tool": "ground_response_in_tool_results",
        },
    )
    builder.add_edge("build_clarification_response", "output_guardrails")
    builder.add_edge("ground_response_in_tool_results", "refine_grounded_answer_with_llm")
    builder.add_edge("refine_grounded_answer_with_llm", "output_guardrails")
    builder.add_edge("output_guardrails", "format_structured_response")
    builder.add_edge("format_structured_response", END)
    return builder.compile()


chat_graph = build_graph()


def run_agent(request: AgentChatRequest) -> AgentChatResponse:
    start = time.perf_counter()
    trace_id = request.trace_id or f"trace_{uuid4().hex}"
    request_id = request.request_id or f"req_{uuid4().hex}"
    context_token = set_trace_context(
        trace_id=trace_id,
        session_id=request.session_id,
        request_id=request_id,
        traceparent=request.traceparent,
    )
    try:
        with agent_trace_context(
            trace_id=trace_id,
            request_id=request_id,
            session_id=request.session_id,
            user_id=request.user_id,
            intent="agent_chat",
        ):
            result = chat_graph.invoke(
                {
                    "session_id": request.session_id,
                    "trace_id": trace_id,
                    "user_id": request.user_id,
                    "authenticated": request.authenticated,
                    "message": request.message,
                    "page_context": request.page_context,
                    "intent": "general",
                    "intent_confidence": 0.0,
                    "routing_confidence": 0.0,
                    "needs_review": False,
                    "slots": {},
                    "tool_calls": [],
                    "product_cards": [],
                    "last_selected_product": None,
                    "last_selected_order": None,
                    "grounding_documents": [],
                    "grounding_order": None,
                    "draft_action": None,
                    "needs_confirmation": False,
                    "node_trace": [],
                    "fallback_count": 0,
                }
            )
    finally:
        reset_trace_context(context_token)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    response = AgentChatResponse(
        sessionId=result["session_id"],
        traceId=result["trace_id"],
        intent=result.get("intent", "fallback"),
        responseType=result.get("response_type", "fallback"),
        answer=result.get("answer", ""),
        productCards=result.get("product_cards", []),
        draftAction=result.get("draft_action"),
        needsConfirmation=result.get("needs_confirmation", False),
        toolCalls=result.get("tool_calls", []),
        nodeTraces=result.get("node_trace", []),
        slots=result.get("slots", {}),
        intentConfidence=result.get("intent_confidence", 0.0),
        routingConfidence=result.get("routing_confidence", 0.0),
        needsReview=result.get("needs_review", False),
        latencyMs=latency_ms,
        fallbackCount=result.get("fallback_count", 0),
    )
    memory_service.update(
        request.session_id,
        products=response.product_cards,
        tool_results=[tool.model_dump(by_alias=True) for tool in response.tool_calls],
        intent=response.intent,
        assistant_response=response.answer,
        selected_product=result.get("last_selected_product") or (response.product_cards[0] if response.product_cards else None),
        selected_order=result.get("last_selected_order"),
    )
    metrics_service.increment("agent_request_total", {"intent": response.intent, "response_type": response.response_type})
    metrics_service.observe("agent_latency_ms", latency_ms, {"intent": response.intent, "response_type": response.response_type})
    metrics_service.increment("agent_intent_total", {"intent": response.intent})
    metrics_service.increment("agent_response_type_total", {"response_type": response.response_type})
    if response.fallback_count:
        metrics_service.increment("agent_fallback_total", {"intent": response.intent}, response.fallback_count)
    if response.draft_action:
        metrics_service.increment("agent_draft_action_total", {"action_type": response.draft_action.action_type})
    log_event(
        "agent_request",
        traceId=response.trace_id,
        requestId=request_id,
        sessionId=response.session_id,
        userId=request.user_id,
        intent=response.intent,
        intentConfidence=response.intent_confidence,
        routingConfidence=response.routing_confidence,
        needsReview=response.needs_review,
        status="success",
        latencyMs=response.latency_ms,
        fallbackCount=response.fallback_count,
        responseType=response.response_type,
    )
    return response
