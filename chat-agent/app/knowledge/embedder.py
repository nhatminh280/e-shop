from __future__ import annotations

import os
import threading
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sentence_transformers import SentenceTransformer


_MODEL_NAME = os.getenv("KNOWLEDGE_EMBEDDER_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_lock = threading.Lock()


@lru_cache(maxsize=1)
def get_embedder() -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer  # local import to keep startup fast

    with _lock:
        return SentenceTransformer(_MODEL_NAME)


def embed_text(text: str) -> list[float]:
    model = get_embedder()
    vector = model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
    return [float(v) for v in vector.tolist()]


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedder()
    vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=16)
    return [[float(v) for v in row] for row in vectors.tolist()]


def embedding_dim() -> int:
    return int(os.getenv("KNOWLEDGE_EMBEDDING_DIM", "384"))
