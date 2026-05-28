from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from app.services.redaction_service import redact


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _STANDARD_LOG_RECORD_KEYS:
                continue
            payload[key] = value
            alias = _LOG_FIELD_ALIASES.get(key)
            if alias and alias not in payload:
                payload[alias] = value
        if record.exc_info:
            payload["errorClass"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["errorMessage"] = self.formatException(record.exc_info)
            payload["error_class"] = payload["errorClass"]
            payload["error_message"] = payload["errorMessage"]
        return json.dumps(redact(payload), ensure_ascii=False, default=str)


def configure_logging() -> None:
    if os.getenv("CHAT_AGENT_JSON_LOGS", "true").lower() not in {"1", "true", "yes"}:
        return
    logger = logging.getLogger("chat_agent")
    logger.setLevel(os.getenv("CHAT_AGENT_LOG_LEVEL", "INFO").upper())
    if any(getattr(handler, "_chat_agent_json", False) for handler in logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._chat_agent_json = True  # type: ignore[attr-defined]
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False


def log_event(event: str, **fields: Any) -> None:
    logging.getLogger("chat_agent").info(event, extra=redact(fields))


_STANDARD_LOG_RECORD_KEYS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
}


_LOG_FIELD_ALIASES = {
    "traceId": "trace_id",
    "requestId": "request_id",
    "sessionId": "session_id",
    "userId": "user_id",
    "toolName": "tool_name",
    "errorClass": "error_class",
    "errorMessage": "error_message",
    "intentConfidence": "intent_confidence",
    "routingConfidence": "routing_confidence",
    "needsReview": "needs_review",
    "latencyMs": "latency_ms",
    "fallbackCount": "fallback_count",
    "responseType": "response_type",
}
