from __future__ import annotations

import logging
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models


logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

POINT_NAMESPACE = uuid.UUID("8dd4f7fd-9b3b-4a64-968e-7dfaa7c04f6f")


class QdrantConfig:
    """Runtime configuration for the Qdrant recommendation index."""

    BASE_DIR = Path(__file__).resolve().parent.parent
    EMBEDDINGS_PATH = Path(os.getenv("EMBEDDINGS_PATH", BASE_DIR / "data/processed/hybrid_embeddings.npy"))
    VARIANT_IDS_PATH = Path(os.getenv("VARIANT_IDS_PATH", BASE_DIR / "data/processed/hybrid_variant_ids.npy"))
    PRODUCT_METADATA_PATH = Path(os.getenv("PRODUCT_METADATA_PATH", BASE_DIR / "data/processed/item_features.csv"))

    HOST = os.getenv("QDRANT_HOST", "localhost")
    PORT = int(os.getenv("QDRANT_PORT", "6333"))
    API_KEY = os.getenv("QDRANT_API_KEY") or None
    COLLECTION = os.getenv("QDRANT_COLLECTION", "product_variants_v1")
    TIMEOUT_SECONDS = float(os.getenv("QDRANT_TIMEOUT_SECONDS", "30"))

    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "512"))
    UPSERT_BATCH_SIZE = int(os.getenv("QDRANT_UPSERT_BATCH_SIZE", "256"))
    READY_RETRIES = int(os.getenv("QDRANT_READY_RETRIES", "30"))
    READY_RETRY_DELAY_SECONDS = float(os.getenv("QDRANT_READY_RETRY_DELAY_SECONDS", "1"))


def point_id_for_variant(variant_id: str) -> str:
    """Qdrant string point IDs must be UUIDs; keep variant_id in payload."""
    return str(uuid.uuid5(POINT_NAMESPACE, str(variant_id)))


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    return value


class QdrantVectorStore:
    """
    Qdrant-backed vector store for product variant recommendations.

    Postgres remains the source of truth. This store indexes embeddings and
    lightweight payload only; API responses should still be enriched/validated
    from Postgres before user-facing mutations.
    """

    def __init__(self, config: type[QdrantConfig] = QdrantConfig):
        self.config = config
        self.client = QdrantClient(
            host=config.HOST,
            port=config.PORT,
            api_key=config.API_KEY,
            timeout=config.TIMEOUT_SECONDS,
        )
        self.product_metadata: dict[str, dict[str, Any]] = {}
        self.wait_until_ready()

    def wait_until_ready(self) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self.config.READY_RETRIES + 1):
            try:
                self.client.get_collections()
                return
            except Exception as exc:
                last_error = exc
                logger.info(
                    "Waiting for Qdrant at %s:%s (%s/%s)",
                    self.config.HOST,
                    self.config.PORT,
                    attempt,
                    self.config.READY_RETRIES,
                )
                time.sleep(self.config.READY_RETRY_DELAY_SECONDS)

        raise RuntimeError(f"Qdrant is not ready: {last_error}") from last_error

    def load_product_metadata(self) -> None:
        path = self.config.PRODUCT_METADATA_PATH
        if not path.exists():
            logger.warning("Metadata file not found: %s", path)
            self.product_metadata = {}
            return

        df = pd.read_csv(path)
        if "variant_id" not in df.columns:
            raise ValueError(f"Metadata file {path} does not contain variant_id")

        df["variant_id"] = df["variant_id"].astype(str)
        self.product_metadata = df.set_index("variant_id").to_dict("index")
        logger.info("Loaded metadata for %s product variants", len(self.product_metadata))

    def collection_exists(self) -> bool:
        try:
            self.client.get_collection(self.config.COLLECTION)
            return True
        except Exception:
            return False

    def collection_size(self) -> int:
        try:
            result = self.client.count(collection_name=self.config.COLLECTION, exact=True)
            return int(result.count)
        except Exception:
            return 0

    def ensure_collection(self, recreate: bool = False) -> None:
        if not self.product_metadata:
            self.load_product_metadata()

        should_build = recreate or not self.collection_exists() or self.collection_size() == 0
        if not should_build:
            logger.info(
                "Using existing Qdrant collection %s with %s points",
                self.config.COLLECTION,
                self.collection_size(),
            )
            return

        self.rebuild_collection()

    def rebuild_collection(self) -> None:
        embeddings, variant_ids = self.load_embeddings()
        dimension = int(embeddings.shape[1])

        logger.info("Recreating Qdrant collection %s", self.config.COLLECTION)
        self.client.recreate_collection(
            collection_name=self.config.COLLECTION,
            vectors_config=models.VectorParams(
                size=dimension,
                distance=models.Distance.COSINE,
            ),
        )

        self.upsert_embeddings(embeddings, variant_ids)
        logger.info(
            "Qdrant collection %s is ready with %s points",
            self.config.COLLECTION,
            self.collection_size(),
        )

    def load_embeddings(self) -> tuple[np.ndarray, np.ndarray]:
        embeddings_path = self.config.EMBEDDINGS_PATH
        variant_ids_path = self.config.VARIANT_IDS_PATH

        if not embeddings_path.exists():
            raise FileNotFoundError(f"Embeddings file not found: {embeddings_path}")
        if not variant_ids_path.exists():
            raise FileNotFoundError(f"Variant IDs file not found: {variant_ids_path}")

        embeddings = np.load(embeddings_path).astype("float32")
        variant_ids = np.load(variant_ids_path, allow_pickle=True).astype(str)

        if len(embeddings) != len(variant_ids):
            raise ValueError(
                f"Embedding count {len(embeddings)} does not match variant ID count {len(variant_ids)}"
            )

        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        if not np.allclose(norms, 1.0, atol=1e-3):
            logger.warning("Embeddings are not L2-normalized; normalizing before Qdrant upsert")
            embeddings = embeddings / norms

        logger.info("Loaded %s embeddings from %s", len(embeddings), embeddings_path)
        return embeddings, variant_ids

    def upsert_embeddings(self, embeddings: np.ndarray, variant_ids: np.ndarray) -> None:
        if not self.product_metadata:
            self.load_product_metadata()

        batch_size = self.config.UPSERT_BATCH_SIZE
        total = len(variant_ids)

        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            points = [
                models.PointStruct(
                    id=point_id_for_variant(variant_id),
                    vector=embeddings[idx].tolist(),
                    payload=self.payload_for_variant(variant_id),
                )
                for idx, variant_id in enumerate(variant_ids[start:end], start=start)
            ]
            self.client.upsert(collection_name=self.config.COLLECTION, points=points)
            logger.info("Upserted Qdrant points %s-%s/%s", start + 1, end, total)

    def payload_for_variant(self, variant_id: str) -> dict[str, Any]:
        metadata = self.product_metadata.get(str(variant_id), {})
        payload: dict[str, Any] = {"variant_id": str(variant_id)}

        for key in (
            "product_id",
            "product_name",
            "category_id",
            "category_name",
            "size",
            "color_id",
            "color_name",
            "gender",
            "price",
            "price_range",
            "quantity_in_stock",
            "is_active",
            "is_featured",
            "primary_image_url",
            "image_path",
            "popularity_score_normalized",
        ):
            if key in metadata:
                payload[key] = _json_safe(metadata[key])

        try:
            payload["in_stock"] = float(payload.get("quantity_in_stock") or 0) > 0
        except (TypeError, ValueError):
            payload["in_stock"] = False
        return payload

    def _query_vector(self, variant_id: str) -> list[float]:
        points = self.client.retrieve(
            collection_name=self.config.COLLECTION,
            ids=[point_id_for_variant(variant_id)],
            with_vectors=True,
            with_payload=False,
        )
        if not points:
            raise ValueError(f"Product variant {variant_id} not found in Qdrant collection")

        vector = points[0].vector
        if isinstance(vector, dict):
            vector = next(iter(vector.values()))
        if vector is None:
            raise ValueError(f"Product variant {variant_id} has no vector in Qdrant collection")

        return list(vector)

    def search(self, variant_id: str, k: int = 10) -> tuple[list[str], list[float]]:
        query_vector = self._query_vector(variant_id)
        if hasattr(self.client, "search"):
            results = self.client.search(
                collection_name=self.config.COLLECTION,
                query_vector=query_vector,
                limit=k + 1,
                with_payload=True,
            )
        else:
            results = self.client.query_points(
                collection_name=self.config.COLLECTION,
                query=query_vector,
                limit=k + 1,
                with_payload=True,
            ).points

        result_ids: list[str] = []
        result_scores: list[float] = []
        for point in results:
            payload = point.payload or {}
            result_variant_id = str(payload.get("variant_id", ""))
            if not result_variant_id or result_variant_id == variant_id:
                continue

            result_ids.append(result_variant_id)
            result_scores.append(float(point.score))
            if len(result_ids) >= k:
                break

        return result_ids, result_scores

    def batch_search(self, variant_ids: list[str], k: int = 10) -> dict[str, tuple[list[str], list[float]]]:
        results: dict[str, tuple[list[str], list[float]]] = {}
        for variant_id in variant_ids:
            try:
                results[variant_id] = self.search(variant_id, k)
            except ValueError:
                logger.warning("Skipping missing variant during batch search: %s", variant_id)
        return results
