from __future__ import annotations

import re
from threading import Lock
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Summary, generate_latest


_METRIC_NAME_PATTERN = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_METRIC_HELP = {
    "agent_request_total": "Total chat agent requests processed.",
    "agent_latency_ms": "Chat agent request latency in milliseconds.",
    "agent_node_latency_ms": "LangGraph node latency in milliseconds.",
    "agent_tool_latency_ms": "Backend tool call latency in milliseconds.",
    "agent_tool_error_total": "Total backend tool calls that did not return success.",
    "agent_fallback_total": "Total fallback outcomes produced by the chat agent.",
    "agent_intent_total": "Total classified intents.",
    "agent_response_type_total": "Total response types returned by the chat agent.",
    "agent_draft_action_total": "Total draft actions prepared by the chat agent.",
}
_METRIC_LABEL_VARIANT_NAMES = {
    ("agent_request_total", ("path",)): "agent_request_by_path_total",
}


class MetricsService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._reset_unlocked()

    def increment(self, name: str, labels: dict[str, Any] | None = None, amount: float = 1.0) -> None:
        _validate_metric_name(name)
        with self._lock:
            label_names, label_values = _label_parts(labels)
            counter = self._counter(name, label_names)
            if label_names:
                counter.labels(*label_values).inc(amount)
            else:
                counter.inc(amount)

    def observe(self, name: str, value: float, labels: dict[str, Any] | None = None) -> None:
        _validate_metric_name(name)
        with self._lock:
            label_names, label_values = _label_parts(labels)
            summary = self._summary(name, label_names)
            if label_names:
                summary.labels(*label_values).observe(value)
            else:
                summary.observe(value)

    def render_prometheus(self) -> str:
        with self._lock:
            return generate_latest(self._registry).decode("utf-8")

    def reset(self) -> None:
        with self._lock:
            self._reset_unlocked()

    def _reset_unlocked(self) -> None:
        self._registry = CollectorRegistry()
        self._counters: dict[tuple[str, tuple[str, ...]], Counter] = {}
        self._summaries: dict[tuple[str, tuple[str, ...]], Summary] = {}

    def _counter(self, name: str, label_names: tuple[str, ...]) -> Counter:
        metric_name = self._metric_name_for_labels(name, label_names)
        key = (metric_name, label_names)
        if key not in self._counters:
            self._counters[key] = Counter(
                metric_name,
                _METRIC_HELP.get(name, f"{metric_name} metric."),
                label_names,
                registry=self._registry,
            )
        return self._counters[key]

    def _summary(self, name: str, label_names: tuple[str, ...]) -> Summary:
        metric_name = self._metric_name_for_labels(name, label_names)
        key = (metric_name, label_names)
        if key not in self._summaries:
            self._summaries[key] = Summary(
                metric_name,
                _METRIC_HELP.get(name, f"{metric_name} metric."),
                label_names,
                registry=self._registry,
            )
        return self._summaries[key]

    def _metric_name_for_labels(self, name: str, label_names: tuple[str, ...]) -> str:
        if (name, label_names) in self._counters or (name, label_names) in self._summaries:
            return name
        if (name, label_names) in _METRIC_LABEL_VARIANT_NAMES:
            return _METRIC_LABEL_VARIANT_NAMES[(name, label_names)]
        return name


def _label_parts(labels: dict[str, Any] | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not labels:
        return (), ()
    items = tuple(sorted((str(key), str(value)) for key, value in labels.items()))
    return tuple(key for key, _ in items), tuple(value for _, value in items)


def _validate_metric_name(name: str) -> None:
    if not _METRIC_NAME_PATTERN.match(name):
        raise ValueError(f"invalid metric name: {name}")


metrics_service = MetricsService()
