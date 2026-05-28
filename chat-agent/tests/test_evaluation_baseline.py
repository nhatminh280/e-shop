from __future__ import annotations

from evaluation import evaluate_cases, load_cases


def test_phase3_evaluation_dataset_passes_baseline() -> None:
    result = evaluate_cases(load_cases())

    failed = [case for case in result.case_results if not case["passed"]]
    assert failed == []
    assert result.metrics["total_cases"] >= 8
    assert result.metrics["intent_accuracy"] == 1.0
    assert result.metrics["slot_extraction_pass_rate"] == 1.0
    assert result.metrics["tool_selection_pass_rate"] == 1.0
    assert result.metrics["schema_validity_rate"] == 1.0
    assert result.metrics["no_mutation_without_confirmation_rate"] == 1.0
    assert result.metrics["fallback_rate"] <= 0.2


def test_phase3_dataset_locks_required_categories() -> None:
    categories = {case["category"] for case in load_cases()}

    assert {
        "product_search",
        "filter_by_price",
        "recommendation",
        "order_status",
        "cart_draft",
        "support_handoff",
        "policy_or_faq",
        "unsafe_malformed",
    } <= categories
