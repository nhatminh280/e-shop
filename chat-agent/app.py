from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from workflow import run_chat


app = FastAPI(title="E-Shop LangGraph Chat Agent")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str = Field(default="demo", min_length=1)


class ChatResponse(BaseModel):
    answer: str
    intent: str
    trace: list[str]
    products: list[dict[str, Any]] = []
    draft_action: dict[str, Any] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    state = run_chat(message=request.message, session_id=request.session_id)
    return ChatResponse(
        answer=state["answer"],
        intent=state.get("intent", "general"),
        trace=state.get("trace", []),
        products=state.get("products", []),
        draft_action=state.get("draft_action"),
    )
