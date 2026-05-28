from __future__ import annotations

import re
from typing import Any


SENSITIVE_KEYS = {
    "authorization",
    "access_token",
    "accessToken",
    "api_key",
    "apiKey",
    "auth",
    "bank_account",
    "card",
    "card_number",
    "client_secret",
    "cookie",
    "cvc",
    "cvv",
    "refresh_token",
    "refreshToken",
    "id_token",
    "jwt",
    "secret",
    "set_cookie",
    "token",
    "password",
    "phone",
    "address",
    "payment",
    "email",
}
REDACTED = "[REDACTED]"


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED if _is_sensitive_key(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(sensitive.lower() in normalized for sensitive in SENSITIVE_KEYS)


def _redact_text(value: str) -> str:
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", f"Bearer {REDACTED}", value, flags=re.IGNORECASE)
    redacted = re.sub(r"Basic\s+[A-Za-z0-9+/=]+", f"Basic {REDACTED}", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", REDACTED, redacted)
    redacted = re.sub(
        r"(?i)\b(access_token|api_key|apikey|auth|client_secret|id_token|jwt|refresh_token|secret|token)=([^&\s]+)",
        lambda match: f"{match.group(1)}={REDACTED}",
        redacted,
    )
    redacted = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", REDACTED, redacted)
    redacted = re.sub(r"\b(?:\+?84|0)\d(?:[\s.-]?\d){7,9}\b", REDACTED, redacted)
    redacted = _redact_card_numbers(redacted)
    return redacted


def _redact_card_numbers(value: str) -> str:
    return re.sub(r"\b(?:\d[ -]?){13,19}\b", _redact_card_match, value)


def _redact_card_match(match: re.Match[str]) -> str:
    candidate = match.group(0)
    digits = re.sub(r"\D", "", candidate)
    if 13 <= len(digits) <= 19 and _passes_luhn(digits):
        return REDACTED
    return candidate


def _passes_luhn(digits: str) -> bool:
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0
