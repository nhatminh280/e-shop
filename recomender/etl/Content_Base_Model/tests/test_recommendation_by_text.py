"""Unit tests for the /recommend/by-text endpoint.

These tests mock the CLIP encoder and the Qdrant vector store so they can run
on any machine without GPU / Qdrant. Run with:

    cd recomender && python -m pytest etl/Content_Base_Model/tests/ -v

Requires only: pytest, fastapi, pydantic, httpx (TestClient). No torch / CLIP.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _stub_heavy_modules(monkeypatch):
    """Stub out CLIP / torch / redis / qdrant so the module import is cheap."""
    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    fake_torch.no_grad = lambda: _NoGradCtx()
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    fake_clip = types.ModuleType("clip")
    fake_clip.tokenize = lambda *a, **k: MagicMock()
    fake_clip.load = lambda *a, **k: (MagicMock(), MagicMock())
    monkeypatch.setitem(sys.modules, "clip", fake_clip)

    fake_redis = types.ModuleType("redis")
    fake_redis.Redis = MagicMock()
    fake_redis.ConnectionPool = MagicMock()
    fake_redis.ConnectionError = type("ConnectionError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "redis", fake_redis)

    # Stub psycopg2 (used by clip_embedding_pipeline)
    fake_psycopg2 = types.ModuleType("psycopg2")
    fake_psycopg2.connect = MagicMock()
    fake_extras = types.ModuleType("psycopg2.extras")
    fake_extras.execute_values = MagicMock()
    monkeypatch.setitem(sys.modules, "psycopg2", fake_psycopg2)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", fake_extras)

    # Stub tqdm
    fake_tqdm = types.ModuleType("tqdm")
    fake_tqdm.tqdm = lambda x=None, **kw: x if x is not None else iter([])
    monkeypatch.setitem(sys.modules, "tqdm", fake_tqdm)

    # Stub PIL (used by clip_embedding_pipeline at import time)
    fake_pil = types.ModuleType("PIL")
    fake_pil.Image = MagicMock()
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)

    # Stub clip_embedding_pipeline so the lazy CLIPEmbedder import never runs.
    fake_pipeline = types.ModuleType("etl.clip_embedding_pipeline")
    fake_pipeline.CLIPEmbedder = MagicMock()
    monkeypatch.setitem(sys.modules, "etl.clip_embedding_pipeline", fake_pipeline)


class _NoGradCtx:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _make_app(monkeypatch, fake_store, fake_encoder_vector):
    """Build a TestClient with the recommendation_api `eshop` app and injected fakes."""
    from etl.Content_Base_Model import recommendation_api as api_mod

    # Replace the lazy CLIP encoder with one returning a fixed normalized vector.
    fake_encoder = MagicMock()
    fake_encoder.encode_text = MagicMock(return_value=fake_encoder_vector)
    api_mod._clip_text_encoder.cache_clear()
    monkeypatch.setattr(api_mod, "_clip_text_encoder", lambda: fake_encoder)

    # Replace the store accessor with our fake.
    monkeypatch.setattr(api_mod, "_store", lambda: fake_store)

    return TestClient(api_mod.eshop)


def _fake_store(rec_ids, rec_scores, metadata):
    store = MagicMock()
    store.search_by_vector = MagicMock(return_value=(rec_ids, rec_scores))
    store.product_metadata = metadata
    return store


def test_by_text_returns_top_k_after_product_dedup(monkeypatch):
    """Two variants of the same product collapse into one recommendation."""
    rec_ids = ["v1", "v2", "v3", "v4"]
    rec_scores = [0.9, 0.85, 0.7, 0.65]
    metadata = {
        "v1": {"product_id": "p1", "product_name": "Cool Lightweight Shirt"},
        "v2": {"product_id": "p1", "product_name": "Cool Lightweight Shirt"},  # same product
        "v3": {"product_id": "p2", "product_name": "Trail Quick-Dry Shirt"},
        "v4": {"product_id": "p3", "product_name": "Tropic Comfort Hoody"},
    }
    store = _fake_store(rec_ids, rec_scores, metadata)
    client = _make_app(monkeypatch, store, np.zeros(512, dtype=np.float32))

    response = client.post("/recommend/by-text", json={"query": "lightweight summer shirt", "k": 3})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["query"] == "lightweight summer shirt"
    assert body["total_results"] == 3
    variant_ids = [r["variant_id"] for r in body["recommendations"]]
    assert variant_ids == ["v1", "v3", "v4"], "Expected p1 to appear once (collapsed)"


def test_by_text_respects_min_similarity(monkeypatch):
    rec_ids = ["v1", "v2", "v3"]
    rec_scores = [0.4, 0.2, 0.05]
    metadata = {
        "v1": {"product_id": "p1", "product_name": "Shirt A"},
        "v2": {"product_id": "p2", "product_name": "Shirt B"},
        "v3": {"product_id": "p3", "product_name": "Shirt C"},
    }
    store = _fake_store(rec_ids, rec_scores, metadata)
    client = _make_app(monkeypatch, store, np.zeros(512, dtype=np.float32))

    response = client.post(
        "/recommend/by-text",
        json={"query": "shirt", "k": 5, "min_similarity": 0.3},
    )

    assert response.status_code == 200
    body = response.json()
    variant_ids = [r["variant_id"] for r in body["recommendations"]]
    assert variant_ids == ["v1"], "Items below 0.3 must be dropped"


def test_by_text_rejects_empty_query(monkeypatch):
    store = _fake_store([], [], {})
    client = _make_app(monkeypatch, store, np.zeros(512, dtype=np.float32))

    response = client.post("/recommend/by-text", json={"query": "   ", "k": 5})

    # Pydantic validation triggers a 422.
    assert response.status_code == 422


def test_by_text_handles_encoder_failure(monkeypatch):
    store = _fake_store(["v1"], [0.9], {"v1": {"product_id": "p1"}})

    from etl.Content_Base_Model import recommendation_api as api_mod

    api_mod._clip_text_encoder.cache_clear()

    fake_encoder = MagicMock()
    fake_encoder.encode_text = MagicMock(return_value=None)  # encoder returned None
    monkeypatch.setattr(api_mod, "_clip_text_encoder", lambda: fake_encoder)
    monkeypatch.setattr(api_mod, "_store", lambda: store)

    client = TestClient(api_mod.eshop)
    response = client.post("/recommend/by-text", json={"query": "test", "k": 5})

    assert response.status_code == 503
    assert "text_encoding_failed" in response.text


def test_by_text_passes_query_vector_to_qdrant(monkeypatch):
    """Verify the endpoint forwards the encoded vector (not the raw text) to Qdrant."""
    fixed_vector = np.array([0.1] * 512, dtype=np.float32)
    store = _fake_store(["v1"], [0.9], {"v1": {"product_id": "p1", "product_name": "X"}})
    client = _make_app(monkeypatch, store, fixed_vector)

    response = client.post("/recommend/by-text", json={"query": "anything", "k": 5})

    assert response.status_code == 200
    store.search_by_vector.assert_called_once()
    called_args = store.search_by_vector.call_args
    forwarded_vector = called_args[0][0] if called_args.args else called_args.kwargs.get("query_vector")
    assert len(forwarded_vector) == 512
