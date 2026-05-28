from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    required_slots = expected.get("requiredSlots", {})
    slot_checks = {
        key: body.get("slots", {}).get(key) == value
        for key, value in required_slots.items()
    }
    expected_tools = expected.get("toolCalls", [])
    tool_selection_pass = all(tool in observed_tools for tool in expected_tools)
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
            "needsConfirmation": body.get("needsConfirmation"),
            "draftAction": body.get("draftAction"),
            "fallbackCount": body.get("fallbackCount", 0),
        },
        "slotChecks": slot_checks,
        "checks": checks,
        "passed": all(checks.values()),
        "error": error,
    }


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
