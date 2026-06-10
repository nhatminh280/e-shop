from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str) -> str:
    lowered = value.lower().strip()
    ascii_text = "".join(
        character for character in unicodedata.normalize("NFD", lowered) if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"\s+", " ", ascii_text)
