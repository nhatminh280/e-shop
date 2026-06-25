from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Evaluation should be deterministic and offline by default. Developers can
# still opt into trace upload with an explicit shell env override.
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
# Eval tests routing/tool/grounding (deterministic). LLM rewriting is
# non-deterministic and breaks substring assertions on answerContains. Force
# LLM off here; production runtime stays LLM_ENABLED=true via .env / compose.
os.environ["LLM_ENABLED"] = "false"

from app.main import chat
from app.schemas import AgentChatRequest
from app.services import memory_service


DEFAULT_CASES_PATH = Path(__file__).with_name("eval_cases.json")
MUTATING_DRAFT_TOOLS = {
    "cart.add_draft",
    "cart.update_quantity_draft",
    "cart.remove_item_draft",
    "support.create_draft",
}
FORBIDDEN_MUTATION_TOOLS = {
    "cart.add_commit",
    "cart.update_quantity_commit",
    "cart.remove_item_commit",
    "support.create_commit",
    "confirm_draft_action",
    "cancel_draft_action",
}


@dataclass(frozen=True)
class EvaluationResult:
    case_results: list[dict[str, Any]]
    metrics: dict[str, Any]


def load_cases(path: Path | str = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("evaluation dataset must be a list")
    return data


def evaluate_cases(cases: list[dict[str, Any]] | None = None) -> EvaluationResult:
    cases = cases or load_cases()
    memory_service.clear()
    case_results = [_evaluate_case(case, index) for index, case in enumerate(cases)]
    return EvaluationResult(case_results=case_results, metrics=_build_metrics(case_results))


def _evaluate_case(case: dict[str, Any], index: int) -> dict[str, Any]:
    session_id = f"eval-{case['id']}-{index}"
    authenticated = bool(case.get("authenticated", False))
    user_id = case.get("userId")

    for setup_message in case.get("setupMessages", []):
        chat(
            AgentChatRequest(
                sessionId=session_id,
                message=setup_message,
                authenticated=authenticated,
                userId=user_id,
            )
        )

    expected = case["expected"]
    try:
        response = chat(
            AgentChatRequest(
                sessionId=session_id,
                message=case["message"],
                authenticated=authenticated,
                userId=user_id,
            )
        )
        body = response.model_dump(by_alias=True)
        schema_valid = True
        error = None
    except Exception as exc:  # pragma: no cover - keeps report useful if a case crashes
        body = {}
        schema_valid = False
        error = f"{exc.__class__.__name__}: {exc}"

    observed_tools = [tool["toolName"] for tool in body.get("toolCalls", [])]
    observed_tool_statuses = _tool_statuses(body.get("toolCalls", []))
    required_slots = expected.get("requiredSlots", {})
    slot_checks = {
        key: body.get("slots", {}).get(key) == value
        for key, value in required_slots.items()
    }
    expected_tools = expected.get("toolCalls", [])
    tool_selection_pass = all(tool in observed_tools for tool in expected_tools)
    expected_tool_sequence = expected.get("toolCallSequence")
    tool_sequence_pass = expected_tool_sequence is None or observed_tools == expected_tool_sequence
    expected_tool_statuses = expected.get("toolStatuses")
    tool_statuses_pass = expected_tool_statuses is None or all(
        observed_tool_statuses.get(tool_name) == status
        for tool_name, status in expected_tool_statuses.items()
    )
    expected_answer = expected.get("answerContains")
    answer_contains_pass = expected_answer is None or expected_answer in body.get("answer", "")
    expected_fallback_count = expected.get("fallbackCount")
    fallback_count_pass = expected_fallback_count is None or body.get("fallbackCount", 0) == expected_fallback_count
    expected_knowledge_source = expected.get("knowledgeSourceId")
    knowledge_source_pass = expected_knowledge_source is None or _has_knowledge_source(
        body.get("toolCalls", []),
        expected_knowledge_source,
    )
    no_mutation_without_confirmation = _check_no_mutation_without_confirmation(
        body,
        observed_tools,
        expected.get("requiresConfirmation", False),
    )

    checks = {
        "schema_valid": schema_valid,
        "intent": body.get("intent") == expected.get("intent"),
        "response_type": body.get("responseType") == expected.get("responseType"),
        "slots": all(slot_checks.values()),
        "tools": tool_selection_pass,
        "tool_sequence": tool_sequence_pass,
        "tool_statuses": tool_statuses_pass,
        "answer_contains": answer_contains_pass,
        "fallback_count": fallback_count_pass,
        "knowledge_source": knowledge_source_pass,
        "no_mutation_without_confirmation": no_mutation_without_confirmation,
    }
    return {
        "id": case["id"],
        "category": case.get("category", ""),
        "message": case["message"][:120],
        "expected": expected,
        "observed": {
            "intent": body.get("intent"),
            "responseType": body.get("responseType"),
            "slots": body.get("slots", {}),
            "toolCalls": observed_tools,
            "toolStatuses": observed_tool_statuses,
            "knowledgeSourceIds": _knowledge_source_ids(body.get("toolCalls", [])),
            "needsConfirmation": body.get("needsConfirmation"),
            "draftAction": body.get("draftAction"),
            "fallbackCount": body.get("fallbackCount", 0),
        },
        "slotChecks": slot_checks,
        "checks": checks,
        "passed": all(checks.values()),
        "error": error,
    }


def _tool_statuses(tool_calls: list[dict[str, Any]]) -> dict[str, str]:
    return {
        tool["toolName"]: tool.get("status", "")
        for tool in tool_calls
    }


def _has_knowledge_source(tool_calls: list[dict[str, Any]], source_id: str) -> bool:
    return source_id in _knowledge_source_ids(tool_calls)


def _knowledge_source_ids(tool_calls: list[dict[str, Any]]) -> list[str]:
    source_ids: list[str] = []
    for tool in tool_calls:
        if tool.get("toolName") != "knowledge.retrieve":
            continue
        summary = tool.get("responseSummary", "")
        for segment in summary.split(";"):
            key, _, value = segment.strip().partition("=")
            if key == "sourceIds":
                source_ids.extend(source_id for source_id in value.split(",") if source_id)
    return source_ids


def _check_no_mutation_without_confirmation(
    body: dict[str, Any],
    observed_tools: list[str],
    requires_confirmation: bool,
) -> bool:
    if any(tool in FORBIDDEN_MUTATION_TOOLS for tool in observed_tools):
        return False
    used_draft_tool = any(tool in MUTATING_DRAFT_TOOLS for tool in observed_tools)
    draft_action = body.get("draftAction")
    needs_confirmation = bool(body.get("needsConfirmation"))
    if requires_confirmation:
        return used_draft_tool and needs_confirmation and bool(draft_action) and draft_action.get("status") == "pending"
    if used_draft_tool:
        return needs_confirmation and bool(draft_action)
    return draft_action is None or needs_confirmation


def _build_metrics(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(case_results)
    if total == 0:
        return {
            "total_cases": 0,
            "passed_cases": 0,
            "intent_accuracy": 0,
            "slot_extraction_pass_rate": 0,
            "tool_selection_pass_rate": 0,
            "schema_validity_rate": 0,
            "no_mutation_without_confirmation_rate": 0,
            "fallback_rate": 0,
        }

    def rate(check_name: str) -> float:
        return round(sum(1 for result in case_results if result["checks"][check_name]) / total, 4)

    return {
        "total_cases": total,
        "passed_cases": sum(1 for result in case_results if result["passed"]),
        "intent_accuracy": rate("intent"),
        "slot_extraction_pass_rate": rate("slots"),
        "tool_selection_pass_rate": rate("tools"),
        "schema_validity_rate": rate("schema_valid"),
        "no_mutation_without_confirmation_rate": rate("no_mutation_without_confirmation"),
        "fallback_rate": round(sum(1 for result in case_results if result["observed"]["fallbackCount"] > 0) / total, 4),
        "response_type_accuracy": rate("response_type"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the chat-agent Phase 3 evaluation baseline.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = evaluate_cases(load_cases(args.cases))
    payload = {
        "metrics": result.metrics,
        "caseResults": result.case_results,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
